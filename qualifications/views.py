from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, connection
from .serializers import QualificationSerializer
from qualifications.models import Learner, Assessor, IQA, EQA, ResourceFile, Message, MessageRecipient, IQADocumentRemark, WorkbookSubmission, IQAFeedback, LearnerDocsByAssessor, LearnerDocumentSubmission, DocumentRequirement, IQAFeedbackToAssessor, ResourceFolder, EvidenceSubmission, Feedback, Sampling, EvidenceFile, AC, LO, Unit, Notification
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from qualifications.models import Qual
from django.contrib import messages
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils.crypto import get_random_string
from django.contrib.auth.hashers import make_password
from users.models import CustomUser, UserBusiness, Business
from qualifications.forms import RoleSelectionForm, LearnerForm, DocumentCheckForm, AssessorForm, MessageForm, WorkbookSubmissionForm, LearnerDocsByAssessorForm, IQADocumentRemarkForm, LearnerDocumentSubmissionForm,IQAFeedbackToAssessorForm, IQAFeedbackForm, DocumentRequirementForm,  IQAForm, EQAForm, UserFilterForm, EditUserForm, ResourceFolderForm,  ResourceFileForm, FeedbackForm, EvidenceSubmissionForm
from django.template.loader import render_to_string
from django.http import JsonResponse
import json
from django.core.exceptions import ValidationError
import os
import mimetypes
from django.views.decorators.http import require_POST
from qualifications.utils import ROLE_TYPES
from django.http import FileResponse, Http404
import logging
from django.urls import reverse
from django.db.models import Count, Q
from django.utils import timezone
import uuid
from rest_framework import serializers
import traceback
from urllib.parse import quote
import boto3
from botocore.exceptions import ClientError
from django.db.models import Prefetch
from django.contrib.auth.models import AnonymousUser
from AssessEEZ.email_utils import send_welcome_email, send_message_notification_email, send_role_notification_email, send_document_submission_notification_email, send_non_conformance_email, send_notification_email




logger = logging.getLogger(__name__)


class QualificationAddEditView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, qualification_id=None):
        if qualification_id:
            try:
                logger.debug(f"Fetching qualification {qualification_id} for user {request.user.email}")
                qual_id = str(qualification_id).lower()
                logger.debug(f"Normalized qualification ID: {qual_id}")

                with connection.cursor() as cursor:
                    cursor.execute("SELECT id, business_id FROM qualifications_qual WHERE id = %s", [qual_id])
                    result = cursor.fetchone()
                    logger.debug(f"Raw query result for id {qual_id}: {result}")

                qualification = Qual.objects.prefetch_related(
                    'units__learning_outcomes__assessment_criteria'
                ).get(id=qual_id)
                logger.debug(f"Qualification found: {qualification.id}, business: {qualification.business.business_id}")

                self._check_business_access(request.user, qualification.business)

                serializer = QualificationSerializer(qualification)
                logger.info(f"Successfully fetched qualification {qual_id} for user {request.user.email}")
                return Response(serializer.data)

            except Qual.DoesNotExist:
                logger.error(f"Qualification {qual_id} not found in database")
                return Response({"error": "Qualification not found."}, status=status.HTTP_404_NOT_FOUND)
            except PermissionDenied as e:
                logger.warning(f"Permission denied for user {request.user.email}: {str(e)}")
                return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
            except Exception as e:
                logger.error(f"Unexpected error fetching qualification {qual_id}: {str(e)}", exc_info=True)
                return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        logger.debug("No qualification ID provided, returning empty response")
        return Response({})

    def _check_business_access(self, user, business):
        logger.debug(f"Checking business access for user: {user.email}, business: {business.business_id}")
        user_businesses = UserBusiness.objects.filter(user=user).values_list('business__business_id', flat=True)
        logger.debug(f"User {user.email} associated businesses: {list(user_businesses)}")
        if not UserBusiness.objects.filter(user=user, business=business).exists():
            logger.warning(f"User {user.email} denied access to business {business.business_id}")
            raise PermissionDenied("You do not have access to this business.")

    def post(self, request):
        with transaction.atomic():
            user_business = UserBusiness.objects.filter(user=request.user, user_type='admin').first()
            if not user_business:
                logger.warning(f"User {request.user.email} attempted to add qualification without admin privileges")
                return Response({"detail": "Only admins can add qualifications."}, status=status.HTTP_403_FORBIDDEN)
            try:
                business = Business.objects.get(business_id=user_business.business_id)
            except Business.DoesNotExist:
                logger.error(f"Business not found for user {request.user.email}")
                return Response({"detail": "Business not found for user."}, status=status.HTTP_400_BAD_REQUEST)
            data = request.data.copy()
            serializer = QualificationSerializer(data=data, context={'request': request, 'business': business})
            if serializer.is_valid():
                try:
                    qualification = serializer.save()
                    logger.info(f"Qualification {qualification.id} created by user {request.user.email}")
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                except Exception as e:
                    logger.error(f"Failed to save qualification: {str(e)}")
                    return Response({"detail": f"Failed to save qualification: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
            logger.debug(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, qualification_id):
        logger.debug(f"PUT request for qualification {qualification_id}")
        logger.debug(f"Request payload: {{qualification_id: {qualification_id}, units_count: {len(request.data.get('units', []))}}}")
        try:
            qualification = Qual.objects.prefetch_related(
                'units__learning_outcomes__assessment_criteria__evidence_submissions'
            ).get(id=qualification_id)
            self._check_business_access(request.user, qualification.business)
            with transaction.atomic():
                units_data = request.data.get('units', [])
                submitted_unit_ids = set([unit.get('id') for unit in units_data if unit.get('id')])
                for unit in qualification.units.all():
                    submission_count = EvidenceSubmission.objects.filter(
                        assessment_criterion__learning_outcome__unit=unit
                    ).count()
                    logger.debug(f"Pre-save: Checking unit {unit.id} (Title: {unit.unit_title}) for submissions: {submission_count} found")
                    if submission_count > 0 and str(unit.id) not in submitted_unit_ids:
                        raise serializers.ValidationError({
                            "units": "You cannot Edit this Qualification because there are Learners Submissions against this Qualification"
                        })
                    for lo in unit.learning_outcomes.all():
                        for ac in lo.assessment_criteria.all():
                            submission_count = EvidenceSubmission.objects.filter(assessment_criterion=ac).count()
                            logger.debug(f"Pre-save: Checking AC {ac.id} (Detail: {ac.ac_detail}) for submissions: {submission_count} found")
                            if submission_count > 0:
                                raise serializers.ValidationError({
                                    "assessment_criteria": "You cannot Edit this Qualification because there are Learners Submissions against this Qualification"
                                })

                serializer = QualificationSerializer(
                    qualification,
                    data=request.data,
                    partial=True,
                    context={'request': request, 'business': qualification.business}
                )
                if serializer.is_valid():
                    logger.debug(f"Validated serializer data: {serializer.validated_data}")
                    qualification = serializer.save()
                    logger.info(f"Qualification {qualification_id} updated successfully by user {request.user.email}")
                    return Response(serializer.data)
                logger.debug(f"Serializer errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Qual.DoesNotExist:
            logger.error(f"Qualification {qualification_id} not found")
            return Response({"error": "Qualification not found."}, status=status.HTTP_404_NOT_FOUND)
        except serializers.ValidationError as e:
            logger.debug(f"Validation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in PUT: {str(e)}")
            return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, qualification_id):
        logger.debug(f"DELETE request for qualification {qualification_id}")
        try:
            qualification = Qual.objects.prefetch_related('learners').get(id=qualification_id)
            self._check_business_access(request.user, qualification.business)
            with transaction.atomic():
                learner_count = qualification.learners.count()
                if learner_count > 0:
                    logger.warning(f"Cannot delete qualification {qualification_id} due to {learner_count} assigned learners")
                    return Response({
                        "error": "You cannot Delete this Qualification because there are Learners assigned with this qualification. First Delete the Learners if their Records are no more required and then Delete this Qualification."
                    }, status=status.HTTP_400_BAD_REQUEST)
                qualification.delete()
                logger.info(f"Qualification {qualification_id} deleted successfully by user {request.user.email}")
                return Response({"message": "Qualification deleted successfully."}, status=status.HTTP_200_OK)
        except Qual.DoesNotExist:
            logger.error(f"Qualification {qualification_id} not found")
            return Response({"error": "Qualification not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied as e:
            logger.warning(f"Permission denied for user {request.user.email}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"Unexpected error in DELETE: {str(e)}")
            return Response({"error": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@login_required
def render_add_qualification_view(request):
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to add qualifications.")
        return redirect('login')
    return render(request, 'add_qualification.html')

def edit_qualification_view(request):
    return render(request, 'edit_qualification.html')

@login_required
def view_qualification_view(request):
    qual_id = request.GET.get('id')
    if not qual_id:
        logger.error("No qualification ID provided in view_qualification_view")
        return render(request, 'view_qualification.html', {'error': 'No qualification ID provided'})
    
    try:
        # Fetch qualification with sorted related objects
        qualification = get_object_or_404(
            Qual.objects.prefetch_related(
                Prefetch(
                    'units',
                    queryset=Unit.objects.order_by('serial_number').prefetch_related(
                        Prefetch(
                            'learning_outcomes',
                            queryset=LO.objects.order_by('serial_number').prefetch_related(
                                Prefetch(
                                    'assessment_criteria',
                                    queryset=AC.objects.order_by('serial_number')
                                )
                            )
                        )
                    )
                )
            ),
            id=qual_id
        )
        
        context = {
            'qualification': qualification,
            'full_name': request.user.get_full_name() or request.user.email,
        }
        logger.info(f"Rendering qualification {qual_id} for user {request.user.email}")
        return render(request, 'view_qualification.html', context)
    except Exception as e:
        logger.error(f"Error viewing qualification {qual_id}: {str(e)}")
        return render(request, 'view_qualification.html', {'error': 'Error loading qualification'})
    
    

class QualificationSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        title = request.query_params.get('title', '')
        if not title:
            return Response({"error": "Title parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            qualifications = Qual.objects.filter(
                qualification_title__icontains=title
            ).prefetch_related('units__learning_outcomes__assessment_criteria')
            serializer = QualificationSerializer(qualifications, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error("Search error:", str(e))
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class QualificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user_business = UserBusiness.objects.get(user=request.user)
            business = user_business.business
            qualifications = Qual.objects.filter(business=business).prefetch_related('units__learning_outcomes__assessment_criteria')
            serializer = QualificationSerializer(qualifications, many=True)
            return render(request, 'qualification_list.html', {'qualifications': serializer.data})
        except UserBusiness.DoesNotExist:
            return Response({"error": "User is not associated with any business."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("List error:", str(e))
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        
@login_required
def add_user_role_select(request):
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    if request.method == 'POST':
        form = RoleSelectionForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data['role']
            if role == 'LEARNER':
                return redirect('qualifications:add_learner')
            elif role == 'ASSESSOR':
                return redirect('qualifications:add_assessor')
            elif role == 'IQA':
                return redirect('qualifications:add_iqa')
            elif role == 'EQA':
                return redirect('qualifications:add_eqa')
    else:
        form = RoleSelectionForm()
    logger.info("Rendering template: add_user.html")
    return render(request, 'add_user.html', {'form': form})

@login_required
def add_learner(request):
    """
    Allows an admin to add a new learner, creating a user and assigning them to a qualification.
    """
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
        logger.info(f"add_learner: Business ID = {business.business_id}, PK = {business.pk}")
        quals = Qual.objects.filter(business=business)
        logger.info(f"add_learner: Direct Qual count = {quals.count()}, Titles = {[q.qualification_title for q in quals]}")
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to add users.")
        return redirect('login')

    if request.method == 'POST':
        form = LearnerForm(request.POST, business=business)
        logger.info(f"add_learner POST: Form qualification queryset count = {form.fields['qualification'].queryset.count()}")
        if form.is_valid():
            email = form.cleaned_data['email'].lower()
            full_name = form.cleaned_data['full_name']
            qualification = form.cleaned_data['qualification']
            assessor = form.cleaned_data['assessor']
            iqa = form.cleaned_data['iqa']
            dob = form.cleaned_data['dob']
            disability = form.cleaned_data['disability']
            address = form.cleaned_data['address']
            batch_number = form.cleaned_data['batch_number']
            phone_number = form.cleaned_data['phone_number']
            date_of_registration = form.cleaned_data['date_of_registration']
            country = form.cleaned_data['country']
            ethnicity = form.cleaned_data['ethnicity']

            try:
                user, user_created = CustomUser.objects.get_or_create(
                    email__iexact=email, defaults={'email': email, 'full_name': full_name}
                )
                user_business, ub_created = UserBusiness.objects.get_or_create(
                    user=user, business=business, defaults={'user_type': 'user'}
                )
                if not user_created:
                    logger.debug(f"Existing user {user.email} password unchanged: {bool(user.password)}")
                # Check if learner already exists for this qualification
                if Learner.objects.filter(user=user_business, qualification=qualification).exists():
                    form.add_error('qualification', f"{full_name} is already registered for {qualification.qualification_title}.")
                    return render(request, 'add_learner.html', {'form': form})

                # Create learner
                learner = Learner.objects.create(
                    user=user_business,
                    qualification=qualification,
                    assessor=assessor,
                    iqa=iqa,
                    dob=dob,
                    disability=disability,
                    address=address,
                    batch_number=batch_number,
                    phone_number=phone_number,
                    date_of_registration=date_of_registration,
                    country=country,
                    ethnicity=ethnicity
                )

                # Send welcome email only if UserBusiness was newly created
                if ub_created:
                    password = get_random_string(length=12)
                    user.set_password(password)
                    user.save()
                    password_to_send = password if user_created else None
                    try:
                        send_welcome_email(
                            user.email, business.name, password_to_send, settings.LOGIN_URL, business.name,
                            role='Learner', qualification_title=qualification.qualification_title
                        )
                        logger.info(f"Sent welcome email to {user.email}")
                    except Exception as e:
                        logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
                        messages.warning(request, f"Learner added, but failed to send welcome email: {str(e)}")
                else:
                    # Send notification email for new qualification
                    try:
                        send_role_notification_email(
                            user.email, business.name, business.business_id,
                            action="Assigned as Learner",
                            role='Learner', qualification_titles=[qualification.qualification_title]
                        )
                        logger.info(f"Sent role notification email to {user.email}")
                    except Exception as e:
                        logger.error(f"Failed to send role notification email to {user.email}: {str(e)}")
                        messages.warning(request, f"Learner added, but failed to send role notification: {str(e)}")

                # Notify assessor and IQA of new learner assignment
                if assessor:
                    try:
                        send_role_notification_email(
                            assessor.user.email, business.name, business.business_id,
                            action="Assigned as Assessor",
                            role='Assessor', learner_name=full_name, qualification_titles=[qualification.qualification_title]
                        )
                        logger.info(f"Sent assessor notification email to {assessor.user.email}")
                    except Exception as e:
                        logger.error(f"Failed to send assessor notification email to {assessor.user.email}: {str(e)}")
                        messages.warning(request, f"Learner added, but failed to notify assessor: {str(e)}")
                if iqa:
                    try:
                        send_role_notification_email(
                            iqa.user.email, business.name, business.business_id,
                            action="Assigned as IQA",
                            role='IQA', learner_name=full_name, qualification_titles=[qualification.qualification_title]
                        )
                        logger.info(f"Sent IQA notification email to {iqa.user.email}")
                    except Exception as e:
                        logger.error(f"Failed to send IQA notification email to {iqa.user.email}: {str(e)}")
                        messages.warning(request, f"Learner added, but failed to notify IQA: {str(e)}")

                messages.success(request, f"Learner {full_name} added successfully.")
                return redirect('users:admin_dashboard')
            except ValidationError as e:
                logger.error(f"ValidationError in add_learner: {repr(e)}")
                if hasattr(e, 'message_dict'):
                    for field, error_messages in e.message_dict.items():
                        form.add_error(field if field != '__all__' else None, str(error_messages))
                else:
                    form.add_error(None, str(e))
    else:
        form = LearnerForm(business=business)
        logger.info(f"add_learner GET: Form qualification queryset count = {form.fields['qualification'].queryset.count()}")

    return render(request, 'add_learner.html', {'form': form})

@login_required
def add_assessor(request):
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to add users.")
        return redirect('login')

    if request.method == 'POST':
        form = AssessorForm(request.POST, business=business)
        if form.is_valid():
            email = form.cleaned_data['email'].lower()
            full_name = form.cleaned_data['full_name']
            qualifications = form.cleaned_data['qualifications']

            try:
                with transaction.atomic():
                    user, user_created = CustomUser.objects.get_or_create(
                        email__iexact=email, defaults={'email': email, 'full_name': full_name}
                    )
                    user_business, ub_created = UserBusiness.objects.get_or_create(
                        user=user, business=business, defaults={'user_type': 'user'}
                    )
                    if not user_created:
                        logger.debug(f"Existing user {user.email} password unchanged: {bool(user.password)}")
                    logger.debug(f"add_assessor: UserBusiness for {email} - Created: {ub_created}")

                    new_assignments = []
                    for qual in qualifications:
                        if not Assessor.objects.filter(user=user_business, qualification=qual).exists():
                            Assessor.objects.create(user=user_business, qualification=qual)
                            new_assignments.append(qual)
                            logger.debug(f"add_assessor: New assessor assignment for {email} - Qualification: {qual.qualification_title}")

                    if not new_assignments:
                        form.add_error('qualifications', f"{full_name} is already an assessor for all selected qualifications.")
                        return render(request, 'add_assessor.html', {'form': form})

                    # Send welcome email only if UserBusiness was newly created
                    if ub_created:
                        password = get_random_string(length=12)
                        user.set_password(password)
                        user.save()
                        password_to_send = password if user_created else None
                        qual_titles = ", ".join([qual.qualification_title for qual in new_assignments])
                        try:
                            send_welcome_email(
                                user.email, business.name, password_to_send, settings.LOGIN_URL, business.name,
                                role='Assessor', qualification_title=qual_titles or "None"
                            )
                            logger.info(f"Sent welcome email to {user.email}")
                        except Exception as e:
                            logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
                            messages.warning(request, f"Assessor added, but failed to send welcome email: {str(e)}")
                    else:
                        # Send notification email for new qualifications
                        qual_titles = [qual.qualification_title for qual in new_assignments]
                        try:
                            send_role_notification_email(
                                user.email, business.name, business.business_id,
                                action="Assigned as Assessor",
                                role='Assessor', qualification_titles=qual_titles
                            )
                            logger.info(f"Sent role notification email to {user.email}")
                        except Exception as e:
                            logger.error(f"Failed to send role notification email to {user.email}: {str(e)}")
                            messages.warning(request, f"Assessor added, but failed to send role notification: {str(e)}")

                    messages.success(request, f"Assessor {full_name} added successfully.")
                    return redirect('users:admin_dashboard')
            except ValidationError as e:
                logger.error(f"ValidationError in add_assessor: {repr(e)}")
                if hasattr(e, 'message_dict'):
                    for field, error_messages in e.message_dict.items():
                        form.add_error(field if field != '__all__' else None, str(error_messages))
                else:
                    form.add_error(None, str(e))
    else:
        form = AssessorForm(business=business)

    return render(request, 'add_assessor.html', {'form': form})

@login_required
def add_iqa(request):
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to add users.")
        return redirect('login')

    if request.method == 'POST':
        form = IQAForm(request.POST, business=business)
        if form.is_valid():
            email = form.cleaned_data['email'].lower()
            full_name = form.cleaned_data['full_name']
            qualifications = form.cleaned_data['qualifications']

            try:
                with transaction.atomic():
                    user, user_created = CustomUser.objects.get_or_create(
                        email__iexact=email, defaults={'email': email, 'full_name': full_name}
                    )
                    user_business, ub_created = UserBusiness.objects.get_or_create(
                        user=user, business=business, defaults={'user_type': 'user'}
                    )
                    if not user_created:
                        logger.debug(f"Existing user {user.email} password unchanged: {bool(user.password)}")
                    logger.debug(f"add_iqa: UserBusiness for {email} - Created: {ub_created}")

                    new_assignments = []
                    for qual in qualifications:
                        if not IQA.objects.filter(user=user_business, qualification=qual).exists():
                            IQA.objects.create(user=user_business, qualification=qual)
                            new_assignments.append(qual)
                            logger.debug(f"add_iqa: New IQA assignment for {email} - Qualification: {qual.qualification_title}")

                    if not new_assignments:
                        form.add_error('qualifications', f"{full_name} is already an IQA for all selected qualifications.")
                        return render(request, 'add_iqa.html', {'form': form})

                    # Send welcome email only if UserBusiness was newly created
                    if ub_created:
                        password = get_random_string(length=12)
                        user.set_password(password)
                        user.save()
                        password_to_send = password if user_created else None
                        qual_titles = ", ".join([qual.qualification_title for qual in new_assignments])
                        try:
                            send_welcome_email(
                                user.email, business.business_id, business.name, password_to_send, settings.LOGIN_URL,
                                sender_name=business.name, role='EQA', qualification_title=qual_titles or "None"
                            )
                            logger.info(f"Sent welcome email to {user.email}")
                        except Exception as e:
                            logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
                            messages.warning(request, f"IQA added, but failed to send welcome email: {str(e)}")
                    else:
                        # Send notification email for new qualifications
                        qual_titles = [qual.qualification_title for qual in new_assignments]
                        try:
                            send_role_notification_email(
                                user.email, business.name, business.business_id,
                                action="Assigned as IQA",
                                role='IQA', qualification_titles=qual_titles
                            )
                            logger.info(f"Sent role notification email to {user.email}")
                        except Exception as e:
                            logger.error(f"Failed to send role notification email to {user.email}: {str(e)}")
                            messages.warning(request, f"IQA added, but failed to send role notification: {str(e)}")

                    messages.success(request, f"IQA {full_name} added successfully.")
                    return redirect('users:admin_dashboard')
            except ValidationError as e:
                logger.error(f"ValidationError in add_iqa: {repr(e)}")
                if hasattr(e, 'message_dict'):
                    for field, error_messages in e.message_dict.items():
                        form.add_error(field if field != '__all__' else None, str(error_messages))
                else:
                    form.add_error(None, str(e))
    else:
        form = IQAForm(business=business)

    return render(request, 'add_iqa.html', {'form': form})

@login_required
def add_eqa(request):
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to add users.")
        return redirect('login')

    if request.method == 'POST':
        form = EQAForm(request.POST, business=business)
        logger.debug(f"add_eqa: POST data = {request.POST}")
        if form.is_valid():
            email = form.cleaned_data['email'].lower()
            full_name = form.cleaned_data['full_name']
            qualifications = form.cleaned_data['qualifications']
            learners = form.cleaned_data['learners']

            logger.debug(f"add_eqa: Valid form data - email = {email}, qualifications = {qualifications}, learners = {learners}")

            try:
                with transaction.atomic():
                    user, user_created = CustomUser.objects.get_or_create(
                        email__iexact=email, defaults={'email': email, 'full_name': full_name}
                    )
                    user_business, ub_created = UserBusiness.objects.get_or_create(
                        user=user, business=business, defaults={'user_type': 'user'}
                    )
                    if not user_created:
                        logger.debug(f"Existing user {user.email} password unchanged: {bool(user.password)}")
                    logger.debug(f"add_eqa: UserBusiness for {email} - Created: {ub_created}")

                    new_assignments = []
                    for qual in qualifications:
                        if not EQA.objects.filter(user=user_business, qualification=qual).exists():
                            eqa = EQA.objects.create(user=user_business, qualification=qual)
                            valid_learners = learners.filter(qualification=qual)
                            logger.debug(f"add_eqa: Assigning learners {valid_learners} to EQA for qualification {qual}")
                            eqa.learners.set(valid_learners)
                            new_assignments.append(qual)

                    if not new_assignments:
                        form.add_error('qualifications', f"{full_name} is already an EQA for all selected qualifications.")
                        return render(request, 'add_eqa.html', {'form': form})

                    # Send welcome email only if UserBusiness was newly created
                    if ub_created:
                        password = get_random_string(length=12)
                        user.set_password(password)
                        user.save()
                        password_to_send = password if user_created else None
                        qual_titles = ", ".join([qual.qualification_title for qual in new_assignments])
                        try:
                            send_welcome_email(
                                user.email, business.name, password_to_send, settings.LOGIN_URL, business.name,
                                role='EQA', qualification_title=qual_titles or "None"
                            )
                            logger.info(f"Sent welcome email to {user.email}")
                        except Exception as e:
                            logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
                            messages.warning(request, f"EQA added, but failed to send welcome email: {str(e)}")
                    else:
                        # Send notification email for new qualifications
                        qual_titles = [qual.qualification_title for qual in new_assignments]
                        try:
                            send_role_notification_email(
                                user.email, business.name, business.business_id,
                                action="Assigned as EQA",
                                role='EQA', qualification_titles=qual_titles
                            )
                            logger.info(f"Sent role notification email to {user.email}")
                        except Exception as e:
                            logger.error(f"Failed to send role notification email to {user.email}: {str(e)}")
                            messages.warning(request, f"EQA added, but failed to send role notification: {str(e)}")

                    messages.success(request, f"EQA {full_name} added successfully.")
                    return redirect('users:admin_dashboard')
            except ValidationError as e:
                logger.error(f"ValidationError in add_eqa: {repr(e)}")
                if hasattr(e, 'message_dict'):
                    for field, error_messages in e.message_dict.items():
                        form.add_error(field if field != '__all__' else None, str(error_messages))
                else:
                    form.add_error(None, str(e))
    else:
        form = EQAForm(business=business)

    return render(request, 'add_eqa.html', {'form': form})


@login_required
def get_learners(request):
    qual_ids = request.GET.get('qual_ids', '').split(',')
    logger.debug(f"get_learners: Raw qual_ids = {qual_ids}")

    # Filter out empty or invalid IDs
    qual_ids = [qid.strip() for qid in qual_ids if qid.strip()]
    logger.debug(f"get_learners: Filtered qual_ids = {qual_ids}")

    if not qual_ids:
        logger.warning("get_learners: No valid qualification IDs provided")
        return JsonResponse({'learners': []})

    try:
        # Validate UUIDs
        qual_uuids = []
        for qid in qual_ids:
            try:
                qual_uuids.append(str(uuid.UUID(qid)))
            except ValueError:
                logger.warning(f"get_learners: Invalid UUID skipped - {qid}")
                continue
        logger.debug(f"get_learners: Validated qual_uuids = {qual_uuids}")

        if not qual_uuids:
            logger.warning("get_learners: No valid UUIDs after validation")
            return JsonResponse({'learners': []})

        user_business = UserBusiness.objects.get(user=request.user)
        business = user_business.business
        logger.debug(f"get_learners: User = {request.user.email}, Business = {business.business_id}")

        learners = Learner.objects.filter(
            qualification__id__in=qual_uuids,
            qualification__business=business,
            is_active=True
        ).select_related('user__user', 'qualification')
        logger.debug(f"get_learners: Found {learners.count()} learners: {[str(l.id) for l in learners]}")

        learner_data = [
            {
                'id': str(learner.id),
                'user': {
                    'full_name': learner.user.user.full_name or learner.user.user.email
                },
                'qualification': {
                    'qualification_title': learner.qualification.qualification_title
                }
            } for learner in learners
        ]
        logger.debug(f"get_learners: Returning learner_data = {learner_data}")

        return JsonResponse({'learners': learner_data})
    except UserBusiness.DoesNotExist:
        logger.error("get_learners: User is not associated with a business")
        return JsonResponse({'error': 'User is not associated with a business'}, status=403)
    except Exception as e:
        logger.error(f"get_learners: Unexpected error - {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)

@login_required
def get_assessors(request):
    qual_id = request.GET.get('qualification')
    if qual_id:
        assessors = UserBusiness.objects.filter(assessor_assignments__qualification_id=qual_id).distinct()
        return JsonResponse({
            'assessors': [
                {'id': str(a.id), 'name': a.user.full_name or a.user.email}
                for a in assessors
            ]
        })
    return JsonResponse({'assessors': []})

@login_required
def get_iqas(request):
    qual_id = request.GET.get('qualification')
    if qual_id:
        iqas = UserBusiness.objects.filter(iqa_assignments__qualification_id=qual_id).distinct()
        return JsonResponse({
            'iqas': [
                {'id': str(i.id), 'name': i.user.full_name or i.user.email}
                for i in iqas
            ]
        })
    return JsonResponse({'iqas': []})

@login_required
def current_users(request):
    try:
        admin_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = admin_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    qualifications = request.GET.getlist('qualifications')
    user_type = request.GET.get('user_type', '').lower()

    users = []
    if user_type == 'learner':
        learners = Learner.objects.filter(user__business=business)
        if qualifications:
            learners = learners.filter(qualification_id__in=qualifications)
        for learner in learners:
            users.append({
                'name': learner.user.user.full_name,
                'qualification': learner.qualification.qualification_title,
                'user_business_id': str(learner.user.id),
                'type': 'learner',
                'custom_user_id': learner.user.user.id
            })
    elif user_type == 'assessor':
        assessors = Assessor.objects.filter(user__business=business)
        if qualifications:
            assessors = assessors.filter(qualification_id__in=qualifications)
        for assessor in assessors:
            users.append({
                'name': assessor.user.user.full_name,
                'qualification': assessor.qualification.qualification_title,
                'user_business_id': str(assessor.user.id),
                'type': 'assessor',
                'custom_user_id': assessor.user.user.id
            })
    elif user_type == 'iqa':
        iqas = IQA.objects.filter(user__business=business)
        if qualifications:
            iqas = iqas.filter(qualification_id__in=qualifications)
        for iqa in iqas:
            users.append({
                'name': iqa.user.user.full_name,
                'qualification': iqa.qualification.qualification_title,
                'user_business_id': str(iqa.user.id),
                'type': 'iqa',
                'custom_user_id': iqa.user.user.id
            })
    elif user_type == 'eqa':
        eqas = EQA.objects.filter(user__business=business)
        if qualifications:
            eqas = eqas.filter(qualification_id__in=qualifications)
        for eqa in eqas:
            users.append({
                'name': eqa.user.user.full_name,
                'qualification': eqa.qualification.qualification_title,
                'user_business_id': str(eqa.user.id),
                'type': 'eqa',
                'custom_user_id': eqa.user.user.id
            })

    return render(request, 'current_users.html', {
        'users': users,
        'business': business,
        'selected_qualifications': qualifications,
        'user_type': user_type
    })

@login_required
def selected_user(request, user_id, role_type):
    try:
        admin_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = admin_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    try:
        user = CustomUser.objects.get(id=user_id)
        user_business = UserBusiness.objects.get(user=user, business=business)
    except (CustomUser.DoesNotExist, UserBusiness.DoesNotExist):
        messages.error(request, "User not found or not associated with this business.")
        return redirect('qualifications:current_users')

    qualifications_with_roles = []
    if role_type.lower() == 'learner':
        learners = Learner.objects.filter(user=user_business).select_related('assessor__user', 'iqa__user')
        for learner in learners:
            qualifications_with_roles.append({
                'qualification': learner.qualification.qualification_title,
                'qualification_id': learner.qualification.id,
                'assessor_name': learner.assessor.user.full_name or learner.assessor.user.email if learner.assessor else None,
                'iqa_name': learner.iqa.user.full_name or learner.iqa.user.email if learner.iqa else None,
                'role': 'Learner',
                'is_active': learner.is_active,
                'learner_id': learner.id,
                'learner_count': 0  # N/A for learners
            })
    elif role_type.lower() == 'assessor':
        assessors = Assessor.objects.filter(user=user_business).select_related('qualification')
        for assessor in assessors:
            learner_count = Learner.objects.filter(
                assessor=user_business,
                qualification=assessor.qualification,
                is_active=True
            ).count()
            qualifications_with_roles.append({
                'qualification': assessor.qualification.qualification_title,
                'qualification_id': assessor.qualification.id,
                'assessor_name': None,
                'iqa_name': None,
                'role': 'Assessor',
                'record_id': assessor.id,
                'learner_count': learner_count
            })
    elif role_type.lower() == 'iqa':
        iqas = IQA.objects.filter(user=user_business).select_related('qualification')
        for iqa in iqas:
            learner_count = Learner.objects.filter(
                iqa=user_business,
                qualification=iqa.qualification,
                is_active=True
            ).count()
            qualifications_with_roles.append({
                'qualification': iqa.qualification.qualification_title,
                'qualification_id': iqa.qualification.id,
                'assessor_name': None,
                'iqa_name': None,
                'role': 'IQA',
                'record_id': iqa.id,
                'learner_count': learner_count
            })
    elif role_type.lower() == 'eqa':
        eqas = EQA.objects.filter(user=user_business).select_related('qualification')
        for eqa in eqas:
            learner_count = eqa.learners.filter(
                qualification=eqa.qualification,
                is_active=True
            ).count()
            qualifications_with_roles.append({
                'qualification': eqa.qualification.qualification_title,
                'qualification_id': eqa.qualification.id,
                'assessor_name': None,
                'iqa_name': None,
                'role': 'EQA',
                'record_id': eqa.id,
                'learner_count': learner_count
            })
    else:
        messages.error(request, "Invalid role type.")
        return redirect('qualifications:current_users')

    return render(request, 'selected_user.html', {
        'name': user.full_name,
        'email': user.email,
        'role_type': role_type.lower(),
        'qualifications_with_roles': qualifications_with_roles,
        'user': user,
        'qualifications': qualifications_with_roles,
        'user_business': user_business  # Pass user_business for URL
    })

@require_POST
@login_required
def toggle_learner_access(request):
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unauthorized access.'}, status=403)

    learner_id = request.POST.get('learner_id')
    is_active = request.POST.get('is_active') == 'true'

    try:
        learner = Learner.objects.get(id=learner_id, user__business=business)
        learner.is_active = is_active
        learner.save()
        logger.info(f"Toggled learner {learner_id} to is_active={is_active}")
        return JsonResponse({'success': True})
    except Learner.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Learner not found.'}, status=404)
    except Exception as e:
        logger.error(f"Error toggling learner {learner_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_POST
@login_required
def delete_learner_qualification(request):
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unauthorized access.'}, status=403)

    learner_id = request.POST.get('learner_id')
    qualification_id = request.POST.get('qualification_id')

    if not learner_id or not qualification_id:
        return JsonResponse({'success': False, 'error': 'Missing learner_id or qualification_id.'}, status=400)

    try:
        learner = Learner.objects.get(
            id=learner_id,
            user__business=business,
            qualification__id=qualification_id
        )
        with transaction.atomic():
            learner.delete()
        return JsonResponse({'success': True, 'message': f'Learner record for {learner.qualification.qualification_title} deleted successfully.'})
    except Learner.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Learner not found or not associated with this qualification.'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting learner {learner_id} for qualification {qualification_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def edit_user_search(request):
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    return render(request, 'edit_user_search.html', {'business': business})

@login_required
def search_users(request):
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        return JsonResponse({'error': 'Unauthorized access.'}, status=403)

    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'users': []})

    users = UserBusiness.objects.filter(
        business=business,
        user__email__icontains=query
    ) | UserBusiness.objects.filter(
        business=business,
        user__full_name__icontains=query
    )

    user_data = []
    for ub in users.distinct():
        roles = []
        if Learner.objects.filter(user=ub).exists():
            roles.append('Learner')
        if Assessor.objects.filter(user=ub).exists():
            roles.append('Assessor')
        if IQA.objects.filter(user=ub).exists():
            roles.append('IQA')
        if EQA.objects.filter(user=ub).exists():
            roles.append('EQA')

        user_data.append({
            'user_business_id': str(ub.id),
            'email': ub.user.email,
            'full_name': ub.user.full_name,
            'roles': roles
        })

    return JsonResponse({'users': user_data})

@login_required
def edit_user(request, user_id):
    try:
        admin_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = admin_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    try:
        user_business = UserBusiness.objects.get(id=user_id, business=business)
        user = user_business.user
    except UserBusiness.DoesNotExist:
        messages.error(request, "User not found or not associated with this business.")
        return redirect('qualifications:edit_user_search')

    if request.method == 'POST':
        form = EditUserForm(request.POST, user_business=user_business, business=business)
        if form.is_valid():
            with transaction.atomic():
                # Update CustomUser
                email = form.cleaned_data['email'].lower()
                user.full_name = form.cleaned_data['full_name']
                user.save()

                # Update Learner if applicable
                if form.has_learner_role:
                    learner = Learner.objects.filter(user=user_business).first()
                    if learner:
                        learner.qualification = form.cleaned_data['qualification']
                        learner.assessor = form.cleaned_data['assessor']
                        learner.iqa = form.cleaned_data['iqa']
                        learner.dob = form.cleaned_data['learner_dob']
                        learner.disability = form.cleaned_data['learner_disability']
                        learner.address = form.cleaned_data['learner_address']
                        learner.batch_number = form.cleaned_data['learner_batch_number']
                        learner.phone_number = form.cleaned_data['learner_phone_number']
                        learner.date_of_registration = form.cleaned_data['learner_date_of_registration']
                        learner.country = form.cleaned_data['learner_country']
                        learner.ethnicity = form.cleaned_data['learner_ethnicity']
                        learner.save()

                messages.success(request, f"User {user.email} updated successfully.")
                return redirect('qualifications:edit_user_search')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = EditUserForm(user_business=user_business, business=business)

    return render(request, 'edit_user.html', {
        'form': form,
        'user': user,
        'business': business
    })

@require_POST
@login_required
def remove_role_qualification(request):
    try:
        admin_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = admin_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to perform this action.")
        return redirect('login')

    role_type = request.POST.get('role_type')
    record_id = request.POST.get('record_id')

    if not role_type or not record_id:
        messages.error(request, "Invalid request parameters.")
        return redirect('qualifications:current_users')

    try:
        if role_type.lower() == 'assessor':
            assessor = Assessor.objects.get(id=record_id, user__business=business)
            assessor.delete()
            messages.success(request, "Assessor role removed successfully.")
        elif role_type.lower() == 'iqa':
            iqa = IQA.objects.get(id=record_id, user__business=business)
            iqa.delete()
            messages.success(request, "IQA role removed successfully.")
        elif role_type.lower() == 'eqa':
            eqa = EQA.objects.get(id=record_id, user__business=business)
            eqa.delete()
            messages.success(request, "EQA role removed successfully.")
        else:
            messages.error(request, "Invalid role type.")
            return redirect('qualifications:current_users')
    except (Assessor.DoesNotExist, IQA.DoesNotExist, EQA.DoesNotExist):
        messages.error(request, "Record not found or not associated with this business.")
        return redirect('qualifications:current_users')

    return JsonResponse({
        'success': True,
        'message': f"{role_type.title()} role removed successfully."
    })


@require_POST
@login_required
def change_learner_assessor(request):
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unauthorized access.'}, status=403)

    learner_id = request.POST.get('learner_id')
    qualification_id = request.POST.get('qualification_id')
    assessor_id = request.POST.get('assessor_id')

    if not learner_id or not qualification_id or not assessor_id:
        return JsonResponse({'success': False, 'error': 'Missing required parameters.'}, status=400)

    try:
        learner = Learner.objects.get(
            id=learner_id,
            user__business=business,
            qualification__id=qualification_id
        )
        assessor = UserBusiness.objects.get(
            id=assessor_id,
            assessor_assignments__qualification_id=qualification_id
        )
        with transaction.atomic():
            # Update learner's assessor
            learner.assessor = assessor
            learner.save()
            # Log the change
            logger.info(f"Assessor changed for learner {learner_id} to {assessor.id} for qualification {qualification_id}")
        return JsonResponse({'success': True, 'message': 'Assessor updated successfully.'})
    except Learner.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Learner not found or not associated with this qualification.'}, status=404)
    except UserBusiness.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Assessor not found or not assigned to this qualification.'}, status=404)
    except Exception as e:
        logger.error(f"Error changing assessor for learner {learner_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_POST
@login_required
def change_learner_iqa(request):
    try:
        user_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unauthorized access.'}, status=403)

    learner_id = request.POST.get('learner_id')
    qualification_id = request.POST.get('qualification_id')
    iqa_id = request.POST.get('iqa_id')

    if not learner_id or not qualification_id or not iqa_id:
        return JsonResponse({'success': False, 'error': 'Missing required parameters.'}, status=400)

    try:
        learner = Learner.objects.get(
            id=learner_id,
            user__business=business,
            qualification__id=qualification_id
        )
        iqa = UserBusiness.objects.get(
            id=iqa_id,
            iqa_assignments__qualification_id=qualification_id
        )
        with transaction.atomic():
            learner.iqa = iqa
            learner.save()
        return JsonResponse({'success': True, 'message': 'IQA updated successfully.'})
    except Learner.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Learner not found or not associated with this qualification.'}, status=404)
    except UserBusiness.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'IQA not found or not assigned to this qualification.'}, status=404)
    except Exception as e:
        logger.error(f"Error changing IQA for learner {learner_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def resources(request):
    try:
        admin_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = admin_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    folders = ResourceFolder.objects.filter(business=business).prefetch_related('qualifications')
    folder_data = []
    for folder in folders:
        folder_data.append({
            'id': folder.id,
            'name': folder.name,
            'qualifications': ', '.join(qual.qualification_title for qual in folder.qualifications.all()),
            'roles': ', '.join([dict(ROLE_TYPES).get(role, role) for role in folder.visible_to_roles])
        })

    return render(request, 'resources.html', {
        'folders': folder_data,
        'business': business
    })

@login_required
def folder_detail(request, folder_id):
    try:
        admin_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = admin_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    try:
        folder = ResourceFolder.objects.get(id=folder_id, business=business)
    except ResourceFolder.DoesNotExist:
        messages.error(request, "Folder not found.")
        return redirect('qualifications:resources')

    if request.method == 'POST':
        form = ResourceFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    ResourceFile.objects.create(
                        folder=folder,
                        title=form.cleaned_data['title'],
                        file=form.cleaned_data['file']
                    )
                messages.success(request, "File added successfully.")
                return redirect('qualifications:folder_detail', folder_id=folder.id)
            except Exception as e:
                messages.error(request, f"Error adding file: {str(e)}")
    else:
        form = ResourceFileForm()

    files = folder.files.all()
    return render(request, 'folder_detail.html', {
        'folder': folder,
        'files': files,
        'form': form,
        'business': business
    })

@login_required
def add_folder(request):
    try:
        admin_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = admin_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    if request.method == 'POST':
        form = ResourceFolderForm(request.POST, business=business)
        if form.is_valid():
            try:
                with transaction.atomic():
                    folder = ResourceFolder.objects.create(
                        name=form.cleaned_data['name'],
                        business=business,
                        visible_to_roles=form.cleaned_data['visible_to_roles']
                    )
                    folder.qualifications.set(form.cleaned_data['qualifications'])
                messages.success(request, f"Folder '{folder.name}' created successfully.")
                return redirect('qualifications:resources')
            except Exception as e:
                messages.error(request, f"Error creating folder: {str(e)}")
    else:
        form = ResourceFolderForm(business=business)

    return render(request, 'add_folder.html', {
        'form': form,
        'business': business
    })

@require_POST
@login_required
def delete_file(request):
    try:
        admin_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = admin_business.business
    except UserBusiness.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Unauthorized access.'}, status=403)

    file_id = request.POST.get('file_id')
    if not file_id:
        return JsonResponse({'success': False, 'error': 'Missing file_id.'}, status=400)

    try:
        file = ResourceFile.objects.get(id=file_id, folder__business=business)
        with transaction.atomic():
            file.file.delete()
            file.delete()
        return JsonResponse({'success': True, 'message': 'File deleted successfully.'})
    except ResourceFile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'File not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def serve_file(request, file_id):
    resource_file = get_object_or_404(ResourceFile, id=file_id)
    user_business = request.user.userbusiness_set.first()
    if not user_business or resource_file.folder.business != user_business.business:
        raise Http404("You do not have permission to access this file.")

    # Initialize boto3 client for Spaces
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )

    file_key = resource_file.file.name
    mime_types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.mp4': 'video/mp4',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    }

    ext = os.path.splitext(file_key)[1].lower()
    mime_type = mime_types.get(ext, mimetypes.guess_type(file_key)[0])
    if mime_type is None:
        mime_type = 'application/octet-stream'

    filename = quote(os.path.basename(file_key))
    logger.debug(f"Serving file: {file_key}, MIME type: {mime_type}, Filename: {filename}")

    try:
        # Fetch file from Spaces
        s3_response = s3_client.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file_key)
        file_content = s3_response['Body']
        logger.debug(f"Fetched file {file_key} with content length: {s3_response.get('ContentLength', 'unknown')}")

        # Create FileResponse
        response = FileResponse(file_content, content_type=mime_type)
        if ext in ['.doc', '.docx', '.ppt', '.pptx']:
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        else:
            response['Content-Disposition'] = f'inline; filename="{filename}"'

        response['Content-Length'] = str(s3_response['ContentLength'])
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        return response
    except ClientError as e:
        logger.error(f"Error fetching file {file_key} from Spaces: {str(e)}")
        raise Http404("File not found.")

@login_required
def edit_folder(request, folder_id):
    folder = get_object_or_404(ResourceFolder, id=folder_id)
    user_business = request.user.userbusiness_set.first()
    if not user_business or folder.business != user_business.business:
        raise Http404("You do not have permission to edit this folder.")
    
    if request.method == 'POST':
        form = ResourceFolderForm(request.POST, instance=folder, business=folder.business)
        if form.is_valid():
            form.save()
            return redirect('qualifications:resources')
    else:
        form = ResourceFolderForm(instance=folder, business=folder.business)
    
    return render(request, 'edit_folder.html', {
        'form': form,
        'folder': folder,
        'business': folder.business
    })

@login_required
def user_dashboard(request):
    business_id = request.session.get('business_id')
    if not business_id:
        messages.error(request, "No business selected. Please select a business.")
        return redirect('users:main_page')

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not associated with this business.")
        return redirect('users:main_page')

    role_priority = {
        'Learner': 1,
        'Assessor': 2,
        'IQA': 3,
        'EQA': 4
    }

    roles = []
    
    learners = Learner.objects.filter(user=user_business, is_active=True).select_related('qualification', 'assessor__user')
    for learner in learners:
        assessor_name = learner.assessor.user.full_name or learner.assessor.user.email if learner.assessor else None
        assessor_email = learner.assessor.user.email if learner.assessor else 'No Assessor Assigned'
        roles.append({
            'qualification': learner.qualification,
            'role': 'Learner',
            'business': business,
            'action_url': reverse('qualifications:learner_view', args=[str(learner.qualification.id)]),
            'assessor_name': assessor_name,
            'assessor_email': assessor_email
        })

    assessors = Assessor.objects.filter(user=user_business).select_related('qualification')
    for assessor in assessors:
        roles.append({
            'qualification': assessor.qualification,
            'role': 'Assessor',
            'business': business,
            'action_url': reverse('qualifications:assessor_view', args=[str(assessor.qualification.id)])
        })

    iqas = IQA.objects.filter(user=user_business).select_related('qualification')
    for iqa in iqas:
        roles.append({
            'qualification': iqa.qualification,
            'role': 'IQA',
            'business': business,
            'action_url': reverse('qualifications:iqa_view', args=[str(iqa.qualification.id)])
        })

    eqas = EQA.objects.filter(user=user_business).select_related('qualification')
    for eqa in eqas:
        roles.append({
            'qualification': eqa.qualification,
            'role': 'EQA',
            'business': business,
            'action_url': reverse('qualifications:eqa_learner_list', args=[str(eqa.qualification.id)])
        })

    roles.sort(key=lambda x: (role_priority[x['role']], x['qualification'].qualification_title))

    is_learner = Learner.objects.filter(user=user_business, is_active=True).exists()
    is_assessor = Assessor.objects.filter(user=user_business).exists()
    is_iqa = IQA.objects.filter(user=user_business).exists()
    is_eqa = EQA.objects.filter(user=user_business).exists()
    unread_notifications = 0
    learner_details = None
    if is_learner:
        unread_notifications = Notification.objects.filter(user=user_business, is_read=False).count()
        learner = Learner.objects.filter(user=user_business, is_active=True).first()
        if learner:
            learner_details = {
                'full_name': user_business.user.full_name or user_business.user.email,
                'email': user_business.user.email,
                'dob': learner.dob,
                'phone_number': learner.phone_number or 'N/A',
                'ethnicity': learner.ethnicity or 'N/A',
            }

    unread_count = MessageRecipient.objects.filter(
        recipient=user_business,
        is_read=False,
        message__recipients__recipient__business__business_id=business_id
    ).count()

    feedback_qualification_id = None
    if iqas.exists():
        feedback_qualification_id = str(iqas.first().qualification.id)
    elif assessors.exists():
        feedback_qualification_id = str(assessors.first().qualification.id)

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'roles': roles,
        'is_learner': is_learner,
        'is_assessor': is_assessor,
        'is_iqa': is_iqa,
        'is_eqa': is_eqa,
        'unread_notifications': unread_notifications,
        'feedback_qualification_id': feedback_qualification_id,
        'learner_details': learner_details,
        'unread_count': unread_count,
    }

    return render(request, 'user_dashboard.html', context)


@login_required
def learner_evidence_view(request, qualification_id, learner_id, ac_id=None):
    """
    Displays a learner's evidence and workbook submissions for a specific assessment criterion.
    Includes the assessor who accepted or rejected each submission.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    try:
        learner = Learner.objects.get(
            id=learner_id,
            user__business=business,
            qualification__id=qualification_id,
            is_active=True
        )
        learner_user = learner.user
    except Learner.DoesNotExist:
        raise Http404("Invalid learner or not associated with this qualification.")

    # Check user roles
    is_learner = Learner.objects.filter(
        user=user_business,
        qualification__id=qualification_id,
        is_active=True
    ).exists()
    is_assessor = Assessor.objects.filter(
        user=user_business,
        qualification__id=qualification_id
    ).exists()
    is_iqa = IQA.objects.filter(
        user=user_business,
        qualification__id=qualification_id
    ).exists()
    is_eqa = EQA.objects.filter(
        user=user_business,
        qualification__id=qualification_id
    ).exists()
    is_admin = UserBusiness.objects.filter(
        user=request.user,
        business=business,
        user_type='admin'
    ).exists()

    if not (is_learner or is_assessor or is_iqa or is_eqa or is_admin):
        raise Http404("You are not authorized to view this learner's evidence.")

    # Role-based access checks
    if is_learner and learner_user != user_business:
        raise Http404("You can only view your own evidence.")
    if is_assessor and learner.assessor != user_business:
        raise Http404("This learner is not assigned to you.")
    if is_iqa and learner.iqa != user_business:
        raise Http404("This learner is not assigned to you.")
    if is_eqa and not Learner.objects.filter(
        user=learner_user,
        qualification__id=qualification_id
    ).exists():
        raise Http404("This learner is not associated with your assigned qualification.")

    try:
        assessment_criterion = AC.objects.get(id=ac_id, learning_outcome__unit__qualification__id=qualification_id)
    except AC.DoesNotExist:
        raise Http404("Invalid assessment criterion.")

    submissions = EvidenceSubmission.objects.filter(
        user=learner_user,
        assessment_criterion=assessment_criterion
    ).select_related('assessment_criterion').prefetch_related('feedbacks', 'files').order_by('-submitted_at')

    submission_data = []
    for submission in submissions:
        status = submission.status
        if status == 'REJECTED':
            status = 'Resubmission Required'
        assessor_name = '-'
        if submission.status in ['ACCEPTED', 'REJECTED'] and submission.assessor:
            assessor_name = submission.assessor.user.full_name or submission.assessor.user.email
        file_urls = [file.evidence_file.url for file in submission.files.all() if file.evidence_file]
        submission_data.append({
            'file_urls': file_urls,
            'submitted_at': submission.submitted_at,
            'evidence_detail': submission.evidence_detail or submission.assessment_criterion.ac_detail,
            'status': status,
            'assessor_name': assessor_name
        })

    workbooks = WorkbookSubmission.objects.filter(
        user=learner_user,
        learning_outcome=assessment_criterion.learning_outcome
    ).order_by('-submitted_at')

    workbook_data = []
    for workbook in workbooks:
        status = workbook.status
        if status == 'REJECTED':
            status = 'Resubmission Required'
        assessor_name = '-'
        if workbook.status in ['ACCEPTED', 'REJECTED'] and workbook.assessor:
            assessor_name = workbook.assessor.user.full_name or workbook.assessor.user.email
        workbook_data.append({
            'file_url': workbook.workbook_file.url if workbook.workbook_file else None,
            'submitted_at': workbook.submitted_at,
            'status': status,
            'assessor_name': assessor_name
        })

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': learner.qualification,
        'learner': learner,
        'learner_name': learner_user.user.full_name or learner_user.user.email,
        'assessment_criterion': assessment_criterion,
        'submissions': submission_data,
        'workbooks': workbook_data,
        'is_learner': is_learner
    }

    return render(request, 'learner_evidence_view.html', context)


@login_required
def assessor_view(request, qualification_id):
    """
    Displays a list of learners assigned to the assessor for a specific qualification.
    Shows learner name, progress percentage, pending assessment status, IQA name, and IQA sampling ratio.
    Learners with pending assessments are listed first, followed by others.
    Learners with 100% progress are shown in a separate table toggled by a button.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    try:
        assessor = Assessor.objects.get(
            user=user_business,
            qualification__id=qualification_id
        )
        qualification = assessor.qualification
    except Assessor.DoesNotExist:
        raise Http404("You are not an assessor for this qualification.")

    learners = Learner.objects.filter(
        assessor=user_business,
        qualification=qualification,
        is_active=True
    ).select_related('user__user', 'iqa__user')

    active_learners = []
    completed_learners = []
    total_ac = AC.objects.filter(learning_outcome__unit__qualification=qualification).count()
    total_units = Unit.objects.filter(qualification=qualification).count()

    for learner in learners:
        accepted_ac = EvidenceSubmission.objects.filter(
            user=learner.user,
            assessment_criterion__learning_outcome__unit__qualification=qualification,
            status='ACCEPTED'
        ).count()
        progress = (accepted_ac / total_ac * 100) if total_ac > 0 else 0
        pending_submissions = EvidenceSubmission.objects.filter(
            user=learner.user,
            assessment_criterion__learning_outcome__unit__qualification=qualification,
            status='SUBMITTED'
        ).exists()

        # Calculate IQA Sampling Ratio
        sampled_units = Sampling.objects.filter(
            iqa=learner.iqa,
            evidence_submission__user=learner.user,
            evidence_submission__assessment_criterion__learning_outcome__unit__qualification=qualification
        ).values('evidence_submission__assessment_criterion__learning_outcome__unit').distinct().count()
        sampling_ratio = (sampled_units / total_units * 100) if total_units > 0 else 0

        # Get IQA name
        iqa_name = (
            learner.iqa.user.full_name or learner.iqa.user.email
            if learner.iqa else ""
        )

        learner_data = {
            'name': learner.user.user.full_name or learner.user.user.email,
            'progress': round(progress, 2),
            'pending_assessment': 'Yes' if pending_submissions else 'No',
            'has_pending': pending_submissions,
            'learner_id': str(learner.id),
            'iqa_name': iqa_name,
            'sampling_ratio': round(sampling_ratio, 2)
        }
        if progress >= 100:
            completed_learners.append(learner_data)
        else:
            active_learners.append(learner_data)

    active_learners.sort(key=lambda x: (-x['has_pending'], x['name']))

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': qualification,
        'active_learners': active_learners,
        'completed_learners': completed_learners,
    }

    return render(request, 'assessor_view.html', context)


@login_required
def assessor_feedback_view(request, qualification_id, learner_id):
    """
    Allows an assessor to review a learner's evidence and workbook submissions, provide LO-specific feedback, and update AC statuses.
    Includes IQA feedback history and View Workbook links.
    Sends email notification to learner for accepted or rejected evidence.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        logger.error(f"No business_id in session for user {request.user.email}")
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
        logger.debug(f"UserBusiness found: {user_business.user.email}, Business: {business.name}")
    except UserBusiness.DoesNotExist:
        logger.error(f"UserBusiness not found for user {request.user.email}, business_id {business_id}")
        raise Http404("You are not associated with this business.")

    try:
        assessor = Assessor.objects.get(
            user=user_business,
            qualification__id=qualification_id
        )
        qualification = assessor.qualification
        logger.debug(f"Assessor found for qualification {qualification_id}")
    except Assessor.DoesNotExist:
        logger.error(f"Assessor not found for user {user_business.user.email}, qualification {qualification_id}")
        raise Http404("You are not an assessor for this qualification.")

    try:
        learner = Learner.objects.get(
            id=learner_id,
            qualification=qualification,
            assessor=user_business,
            is_active=True
        )
        learner_user = learner.user
        logger.debug(f"Learner found: {learner_user.user.email}, Qualification: {qualification.qualification_title}")
    except Learner.DoesNotExist:
        logger.error(f"Learner not found for id {learner_id}, qualification {qualification_id}")
        raise Http404("Invalid learner or not assigned to you for this qualification.")

    units = Unit.objects.filter(qualification=qualification).prefetch_related(
        'learning_outcomes__assessment_criteria__evidence_submissions',
        'learning_outcomes__workbook_submissions'
    )

    structured_data = []
    feedback_forms = {}
    for unit in units:
        latest_sampling = Sampling.objects.filter(
            evidence_submission__user=learner_user,
            evidence_submission__assessment_criterion__learning_outcome__unit=unit
        ).order_by('-created_at').first()
        unit_data = {
            'id': str(unit.id),
            'title': unit.unit_title,
            'number': unit.unit_number,
            'learning_outcomes': [],
            'has_iqa_feedback': Sampling.objects.filter(
                evidence_submission__user=learner_user,
                evidence_submission__assessment_criterion__learning_outcome__unit=unit
            ).exists(),
            'is_non_conformance': latest_sampling.outcome == 'NON_CONFORMANCE' if latest_sampling else False
        }
        for lo in unit.learning_outcomes.all():
            lo_data = {
                'detail': lo.lo_detail,
                'id': str(lo.id),
                'assessment_criteria': [],
                'can_provide_feedback': False,
                'latest_feedback': None,
                'workbook_url': None
            }
            latest_submission = EvidenceSubmission.objects.filter(
                user=learner_user,
                assessment_criterion__learning_outcome=lo
            ).order_by('-submitted_at').first()
            if latest_submission and latest_submission.feedbacks.exists():
                lo_data['latest_feedback'] = latest_submission.feedbacks.order_by('-created_at').first()
            
            workbook_submission = WorkbookSubmission.objects.filter(
                user=learner_user,
                learning_outcome=lo
            ).order_by('-submitted_at').first()
            if workbook_submission and workbook_submission.workbook_file:
                lo_data['workbook_url'] = workbook_submission.workbook_file.url

            for ac in lo.assessment_criteria.all():
                submission = EvidenceSubmission.objects.filter(
                    user=learner_user,
                    assessment_criterion=ac
                ).order_by('-submitted_at').first()
                status = submission.status if submission else 'Not Submitted'
                if status == 'REJECTED':
                    status = 'Resubmission Required'
                lo_data['assessment_criteria'].append({
                    'detail': ac.ac_detail,
                    'id': str(ac.id),
                    'status': status,
                    'submission_id': submission.id if submission else None,
                    'evidence_url': reverse('qualifications:learner_evidence', args=[str(qualification_id), str(learner_id), str(ac.id)]) if submission else None
                })
                if submission:
                    lo_data['can_provide_feedback'] = True
            
            assessment_criteria = AC.objects.filter(learning_outcome=lo)
            form = FeedbackForm(assessment_criteria=assessment_criteria)
            feedback_forms[str(lo.id)] = form.as_p()
            
            unit_data['learning_outcomes'].append(lo_data)
        structured_data.append(unit_data)

    if request.method == 'POST':
        lo_id = request.POST.get('lo_id')
        try:
            lo = LO.objects.get(id=lo_id, unit__qualification=qualification)
            logger.debug(f"Processing feedback for LO: {lo.lo_detail}, ID: {lo_id}")
            assessment_criteria = AC.objects.filter(learning_outcome=lo)
            form = FeedbackForm(request.POST, assessment_criteria=assessment_criteria)
            if form.is_valid():
                feedback_detail = form.cleaned_data['feedback_detail']
                logger.debug(f"Form valid, feedback_detail: {feedback_detail}")
                with transaction.atomic():
                    feedback_saved = False
                    for ac in lo.assessment_criteria.all():
                        submission = EvidenceSubmission.objects.filter(
                            user=learner_user,
                            assessment_criterion=ac
                        ).order_by('-submitted_at').first()
                        if submission:
                            status_field = f'status_{ac.id}'
                            new_status = form.cleaned_data[status_field]
                            old_status = submission.status
                            logger.debug(f"AC: {ac.ac_detail}, Old Status: {old_status}, New Status: {new_status}")
                            if new_status != 'PENDING':
                                submission.status = new_status
                                if new_status in ['ACCEPTED', 'REJECTED']:
                                    submission.assessor = user_business
                                submission.save()
                            if new_status in ['ACCEPTED', 'REJECTED'] and new_status != old_status:
                                status_text = 'Accepted' if new_status == 'ACCEPTED' else 'Declined'
                                message = f"Your latest Submission for '{ac.ac_detail}' has been {status_text}."
                                notification = Notification.objects.create(
                                    user=learner_user,
                                    evidence_submission=submission,
                                    message=message
                                )
                                try:
                                    if not learner_user.user.email:
                                        raise ValueError("Learner email is empty")
                                    send_notification_email(
                                        recipient_email=learner_user.user.email,
                                        learner_name=learner_user.user.full_name or learner_user.user.email,
                                        business_name=business.name,
                                        notification_message=message,
                                        notification_date=notification.created_at
                                    )
                                    logger.info(f"Sent notification email to {learner_user.user.email} for AC: {ac.ac_detail}")
                                except Exception as e:
                                    logger.error(f"Failed to send notification email to {learner_user.user.email}: {str(e)}")
                                    messages.warning(request, f"Feedback updated, but failed to notify learner: {str(e)}")
                            if feedback_detail and not feedback_saved:
                                Feedback.objects.create(
                                    evidence_submission=submission,
                                    feedback_detail=feedback_detail,
                                    assessor=user_business
                                )
                                feedback_saved = True
                                logger.debug(f"Feedback saved for submission: {submission.id}")
                messages.success(request, f"Feedback and statuses updated for Learning Outcome: {lo.lo_detail}")
                return redirect('qualifications:assessor_feedback', qualification_id=qualification_id, learner_id=learner_id)
            else:
                logger.error(f"Form invalid: {form.errors}")
                messages.error(request, "Error in feedback form. Please check the input.")
                feedback_forms[str(lo.id)] = form.as_p()
        except LO.DoesNotExist:
            logger.error(f"Learning Outcome not found: ID {lo_id}")
            messages.error(request, "Invalid learning outcome.")
        except Exception as e:
            logger.error(f"Error submitting feedback: {str(e)}")
            messages.error(request, f"Error submitting feedback: {str(e)}")

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': qualification,
        'learner': learner,
        'learner_name': learner_user.user.full_name or learner_user.user.email,
        'learner_disability': learner.disability,
        'structured_data': structured_data,
        'feedback_forms': feedback_forms,
    }
    return render(request, 'assessor_feedback_view.html', context)
@login_required
def provide_feedback(request, qualification_id, learner_id, lo_id):
    """
    Renders a template for providing feedback on a specific Learning Outcome.
    Allows assessors to accept or reject evidence submissions and provide feedback.
    Sends email notification to learner for accepted or rejected evidence.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        logger.error(f"No business_id in session for user {request.user.email}")
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
        logger.debug(f"UserBusiness found: {user_business.user.email}, Business: {business.name}")
    except UserBusiness.DoesNotExist:
        logger.error(f"UserBusiness not found for user {request.user.email}, business_id {business_id}")
        raise Http404("You are not associated with this business.")

    try:
        assessor = Assessor.objects.get(
            user=user_business,
            qualification__id=qualification_id
        )
        qualification = assessor.qualification
        logger.debug(f"Assessor found for qualification {qualification_id}")
    except Assessor.DoesNotExist:
        logger.error(f"Assessor not found for user {user_business.user.email}, qualification {qualification_id}")
        raise Http404("You are not an assessor for this qualification.")

    try:
        learner = Learner.objects.get(
            id=learner_id,
            qualification=qualification,
            assessor=user_business,
            is_active=True
        )
        learner_user = learner.user
        logger.debug(f"Learner found: {learner_user.user.email}, Qualification: {qualification.qualification_title}")
    except Learner.DoesNotExist:
        logger.error(f"Learner not found for id {learner_id}, qualification {qualification_id}")
        raise Http404("Invalid learner or not assigned to you for this qualification.")

    try:
        lo = LO.objects.get(id=lo_id, unit__qualification=qualification)
        logger.debug(f"Learning Outcome found: {lo.lo_detail}, ID: {lo_id}")
    except LO.DoesNotExist:
        logger.error(f"Learning Outcome not found: ID {lo_id}")
        raise Http404("Invalid learning outcome.")

    assessment_criteria = AC.objects.filter(learning_outcome=lo)
    latest_submission = EvidenceSubmission.objects.filter(
        user=learner_user,
        assessment_criterion__learning_outcome=lo
    ).order_by('-submitted_at').first()
    latest_feedback = latest_submission.feedbacks.order_by('-created_at').first() if latest_submission and latest_submission.feedbacks.exists() else None

    # Prepare initial statuses for ACs
    initial_statuses = {}
    for ac in assessment_criteria:
        submission = EvidenceSubmission.objects.filter(
            user=learner_user,
            assessment_criterion=ac
        ).order_by('-submitted_at').first()
        initial_statuses[str(ac.id)] = submission.status if submission else 'PENDING'

    if request.method == 'POST':
        form = FeedbackForm(request.POST, assessment_criteria=assessment_criteria, initial_statuses=initial_statuses)
        if form.is_valid():
            feedback_detail = form.cleaned_data['feedback_detail']
            logger.debug(f"Form valid, feedback_detail: {feedback_detail}")
            with transaction.atomic():
                feedback_saved = False
                for ac in lo.assessment_criteria.all():
                    submission = EvidenceSubmission.objects.filter(
                        user=learner_user,
                        assessment_criterion=ac
                    ).order_by('-submitted_at').first()
                    if submission:
                        status_field = f'status_{ac.id}'
                        new_status = form.cleaned_data[status_field]
                        old_status = submission.status
                        logger.debug(f"AC: {ac.ac_detail}, Old Status: {old_status}, New Status: {new_status}")
                        if new_status != 'PENDING':
                            submission.status = new_status
                            if new_status in ['ACCEPTED', 'REJECTED']:
                                submission.assessor = user_business
                            submission.save()
                        if new_status in ['ACCEPTED', 'REJECTED'] and new_status != old_status:
                            status_text = 'Accepted' if new_status == 'ACCEPTED' else 'Declined'
                            message = f"Your latest Submission for '{ac.ac_detail}' has been {status_text}."
                            notification = Notification.objects.create(
                                user=learner_user,
                                evidence_submission=submission,
                                message=message
                            )
                            try:
                                if not learner_user.user.email:
                                    raise ValueError("Learner email is empty")
                                send_notification_email(
                                    recipient_email=learner_user.user.email,
                                    learner_name=learner_user.user.full_name or learner_user.user.email,
                                    business_name=business.name,
                                    notification_message=message,
                                    notification_date=notification.created_at
                                )
                                logger.info(f"Sent notification email to {learner_user.user.email} for AC: {ac.ac_detail}")
                            except Exception as e:
                                logger.error(f"Failed to send notification email to {learner_user.user.email}: {str(e)}")
                                messages.warning(request, f"Feedback updated, but failed to notify learner: {str(e)}")
                        if feedback_detail and not feedback_saved:
                            Feedback.objects.create(
                                evidence_submission=submission,
                                feedback_detail=feedback_detail,
                                assessor=user_business
                            )
                            feedback_saved = True
                            logger.debug(f"Feedback saved for submission: {submission.id}")
            messages.success(request, f"Feedback and statuses updated for Learning Outcome: {lo.lo_detail}")
            return redirect('qualifications:assessor_feedback', qualification_id=qualification_id, learner_id=learner_id)
        else:
            logger.error(f"Form invalid: {form.errors}")
            messages.error(request, f"Error in feedback form: {form.errors.as_text()}")
    else:
        form = FeedbackForm(assessment_criteria=assessment_criteria, initial_statuses=initial_statuses)

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': qualification,
        'learner': learner,
        'learner_name': learner_user.user.full_name or learner_user.user.email,
        'lo': lo,
        'form': form,
        'latest_feedback': latest_feedback,
    }
    return render(request, 'provide_feedback.html', context)


@login_required
def feedback_history_view(request, qualification_id, learner_id, lo_id):
    """
    Displays the history of feedback for a specific Learning Outcome for a learner.
    Accessible by Learners, Assessors, IQAs, EQAs, and Admins.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    try:
        qualification = Qual.objects.get(id=qualification_id)
        lo = LO.objects.get(id=lo_id, unit__qualification=qualification)
    except (Qual.DoesNotExist, LO.DoesNotExist):
        raise Http404("Invalid qualification or learning outcome.")

    # Check user roles for access
    is_learner = Learner.objects.filter(
        user=user_business,
        qualification=qualification,
        is_active=True
    ).exists()
    is_assessor = Assessor.objects.filter(
        user=user_business,
        qualification=qualification
    ).exists()
    is_iqa = IQA.objects.filter(
        user=user_business,
        qualification=qualification
    ).exists()
    is_eqa = EQA.objects.filter(
        user=user_business,
        qualification=qualification
    ).exists()
    is_admin = UserBusiness.objects.filter(
        user=request.user,
        business=business,
        user_type='admin'
    ).exists()

    if not (is_learner or is_assessor or is_iqa or is_eqa or is_admin):
        raise Http404("You are not authorized to view this feedback history.")

    try:
        learner = Learner.objects.get(
            id=learner_id,
            qualification=qualification,
            is_active=True
        )
        learner_user = learner.user
    except Learner.DoesNotExist:
        raise Http404("Invalid learner or not associated with this qualification.")

    # Verify role-specific access
    if is_learner and learner_user != user_business:
        raise Http404("You can only view your own feedback history.")
    if is_assessor and learner.assessor != user_business:
        raise Http404("This learner is not assigned to you.")
    if is_iqa and learner.iqa != user_business:
        raise Http404("This learner is not assigned to you.")
    if is_eqa and not Learner.objects.filter(
        user=learner_user,
        qualification=qualification
    ).exists():
        raise Http404("This learner is not associated with your assigned qualification.")
    if is_admin and learner_user.business != business:
        raise Http404("This learner is not associated with your business.")

    # Fetch all feedback for submissions under this LO, deduplicated
    feedback_data = Feedback.objects.filter(
        evidence_submission__assessment_criterion__learning_outcome=lo,
        evidence_submission__user=learner_user
    ).select_related('evidence_submission', 'assessor__user').order_by('-created_at')

    # Client-side deduplication to handle existing duplicates
    seen = set()
    unique_feedback = []
    for feedback in feedback_data:
        feedback_key = (feedback.feedback_detail, feedback.created_at, feedback.assessor_id)
        if feedback_key not in seen:
            seen.add(feedback_key)
            unique_feedback.append({
                'detail': feedback.feedback_detail,
                'created_at': feedback.created_at,
                'assessor_name': feedback.assessor.user.full_name or feedback.assessor.user.email
            })

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': qualification,
        'learner': learner,
        'learning_outcome': lo,
        'feedback_data': unique_feedback,
        'is_assessor': is_assessor,
    }

    return render(request, 'feedback_history.html', context)


@login_required
def notification_view(request):
    """
    Displays notifications for the logged-in Learner. Only Learners can access this view.
    Shows unread notifications first, followed by read notifications, ordered by creation date (newest first).
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    # Check if the user is a Learner for any qualification
    is_learner = Learner.objects.filter(user=user_business, is_active=True).exists()
    if not is_learner:
        raise Http404("Only Learners can access the notification view.")

    # Fetch notifications for the user, ordered by is_read (False first) and created_at (newest first)
    notifications = Notification.objects.filter(user=user_business).order_by('is_read', '-created_at')

    # Mark all unread notifications as read when the view is accessed via POST
    if request.method == 'POST':
        Notification.objects.filter(user=user_business, is_read=False).update(is_read=True)
        return redirect('qualifications:notification_view')

    context = {
        'full_name': request.user.full_name or request.user.email,
        'notifications': notifications,
    }

    return render(request, 'notification_view.html', context)

@login_required
def iqa_view(request, qualification_id):
       """
       Displays a list of learners assigned to the IQA for a specific qualification.
       Shows learner name, progress percentage, IQA sampling ratio, and assigned assessor.
       Allows filtering by assessor and progress range.
       Learners are sorted by name.
       """
       business_id = request.session.get('business_id')
       if not business_id:
           raise Http404("No business selected. Please log in again.")

       try:
           user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
           business = user_business.business
       except UserBusiness.DoesNotExist:
           raise Http404("You are not associated with this business.")

       # Check if user is IQA or EQA
       is_iqa = IQA.objects.filter(
           user=user_business,
           qualification__id=qualification_id
       ).exists()
       is_eqa = EQA.objects.filter(
           user=user_business,
           qualification__id=qualification_id
       ).exists()

       if not is_iqa:
           if is_eqa:
               return redirect('qualifications:user_dashboard')
           raise Http404("You are not an IQA for this qualification.")

       try:
           iqa = IQA.objects.get(
               user=user_business,
               qualification__id=qualification_id
           )
           qualification = iqa.qualification
       except IQA.DoesNotExist:
           raise Http404("You are not an IQA for this qualification.")

       # Fetch assessors for the qualification
       assessors = Assessor.objects.filter(
           qualification=qualification
       ).select_related('user').order_by('user__user__full_name', 'user__user__email')

       # Process filter parameters
       assessor_id = request.GET.get('assessor_id')
       progress_min = request.GET.get('progress_min')
       progress_max = request.GET.get('progress_max')

       # Validate and convert filter values
       try:
           progress_min = float(progress_min) if progress_min else None
           progress_max = float(progress_max) if progress_max else None
       except (ValueError, TypeError):
           progress_min = None
           progress_max = None

       # Fetch learners with related data
       learners = Learner.objects.filter(
           iqa=user_business,
           qualification=qualification,
           is_active=True
       ).select_related('user__user', 'assessor__user')

       # Apply assessor filter
       if assessor_id:
           try:
               uuid.UUID(assessor_id)  # Validate UUID
               learners = learners.filter(assessor__id=assessor_id)
           except (ValueError, TypeError):
               pass  # Ignore invalid UUID

       learner_data = []
       total_ac = AC.objects.filter(learning_outcome__unit__qualification=qualification).count()
       total_units = Unit.objects.filter(qualification=qualification).count()

       for learner in learners:
           accepted_ac = EvidenceSubmission.objects.filter(
               user=learner.user,
               assessment_criterion__learning_outcome__unit__qualification=qualification,
               status='ACCEPTED'
           ).count()
           progress = (accepted_ac / total_ac * 100) if total_ac > 0 else 0

           # Calculate IQA Sampling Ratio
           sampled_units = Sampling.objects.filter(
               iqa=user_business,
               evidence_submission__user=learner.user,
               evidence_submission__assessment_criterion__learning_outcome__unit__qualification=qualification
           ).values('evidence_submission__assessment_criterion__learning_outcome__unit').distinct().count()
           sampling_ratio = (sampled_units / total_units * 100) if total_units > 0 else 0

           # Apply progress filter
           if progress_min is not None and progress < progress_min:
               continue
           if progress_max is not None and progress > progress_max:
               continue

           # Get assessor name
           assessor_name = (
               learner.assessor.user.full_name or learner.assessor.user.email
               if learner.assessor else ""
           )

           learner_data.append({
               'name': learner.user.user.full_name or learner.user.user.email,
               'progress': round(progress, 2),
               'sampling_ratio': round(sampling_ratio, 2),
               'learner_id': str(learner.id),
               'assessor_name': assessor_name
           })

       learner_data.sort(key=lambda x: x['name'])

       # Prepare assessors for dropdown
       assessor_list = [
           {
               'id': str(assessor.id),
               'name': assessor.user.user.full_name or assessor.user.email
           }
           for assessor in assessors
       ]

       # Context for filter form
       filter_values = {
           'assessor_id': assessor_id,
           'progress_min': progress_min,
           'progress_max': progress_max
       }

       context = {
           'full_name': request.user.full_name or request.user.email,
           'business': business,
           'qualification': qualification,
           'learners': learner_data,
           'assessors': assessor_list,
           'filter_values': filter_values
       }

       return render(request, 'iqa_view.html', context)

@login_required
def iqa_feedback_history_view(request, qualification_id, learner_id):
    """
    Displays a learner's evidence and workbook submissions for a qualification, organized by units, learning outcomes, and assessment criteria, for IQA users.
    Includes IQA Feedback, IQA Feedback History, and View Workbook buttons.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    try:
        learner = Learner.objects.get(
            id=learner_id,
            user__business=business,
            qualification__id=qualification_id,
            is_active=True
        )
        learner_user = learner.user
    except Learner.DoesNotExist:
        raise Http404("Invalid learner or not associated with this qualification.")

    # Check if user is IQA for the qualification
    if not IQA.objects.filter(
        user=user_business,
        qualification__id=qualification_id
    ).exists():
        raise Http404("You are not authorized to view this learner's evidence as an IQA.")

    # Role-based access check
    if learner.iqa != user_business:
        raise Http404("This learner is not assigned to you.")

    units = Unit.objects.filter(qualification__id=qualification_id).prefetch_related(
        'learning_outcomes__assessment_criteria__evidence_submissions',
        'learning_outcomes__workbook_submissions'
    )

    structured_data = []
    for unit in units:
        unit_data = {
            'id': str(unit.id),
            'unit_title': unit.unit_title,
            'unit_number': unit.unit_number,
            'learning_outcomes': [],
            'has_iqa_feedback': Sampling.objects.filter(
                iqa=user_business,
                evidence_submission__user=learner_user,
                evidence_submission__assessment_criterion__learning_outcome__unit=unit
            ).exists(),
            'all_ac_accepted': True
        }
        for lo in unit.learning_outcomes.all():
            lo_data = {
                'detail': lo.lo_detail,
                'id': str(lo.id),
                'has_feedback': Feedback.objects.filter(
                    evidence_submission__user=learner_user,
                    evidence_submission__assessment_criterion__learning_outcome=lo,
                    evidence_submission__assessment_criterion__learning_outcome__unit__qualification__id=qualification_id
                ).exists(),
                'assessment_criteria': [],
                'workbook_url': None
            }
            workbook_submission = WorkbookSubmission.objects.filter(
                user=learner_user,
                learning_outcome=lo
            ).order_by('-submitted_at').first()
            if workbook_submission and workbook_submission.workbook_file:
                lo_data['workbook_url'] = workbook_submission.workbook_file.url
            for ac in lo.assessment_criteria.all():
                submission = EvidenceSubmission.objects.filter(
                    user=learner_user,
                    assessment_criterion=ac
                ).order_by('-submitted_at').first()
                status = submission.status if submission else 'Not Submitted'
                if status == 'REJECTED':
                    status = 'Resubmission Required'
                if status != 'ACCEPTED':
                    unit_data['all_ac_accepted'] = False
                lo_data['assessment_criteria'].append({
                    'detail': ac.ac_detail,
                    'id': str(ac.id),
                    'status': status,
                    'evidence_url': reverse('qualifications:learner_evidence', args=[str(qualification_id), str(learner_id), str(ac.id)]) if submission else None
                })
            unit_data['learning_outcomes'].append(lo_data)
        structured_data.append(unit_data)

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': learner.qualification,
        'learner': learner,
        'learner_name': learner_user.user.full_name or learner_user.user.email,
        'structured_data': structured_data,
    }

    return render(request, 'iqa_feedback_history_view.html', context)



@login_required
def iqa_feedback_history(request, qualification_id, learner_id, unit_id):
    """
    Displays the history of IQA feedback for a specific unit and learner.
    Accessible by admins (unrestricted), IQAs, EQAs, and assessors assigned to the learner.
    Learners are denied access.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    # Check if user is a learner
    if user_business.user_type == 'learner':
        raise Http404("Learners are not authorized to view this feedback history.")

    # Check if user is an admin (unrestricted access)
    is_admin = user_business.user_type == 'admin'

    try:
        learner = Learner.objects.get(
            id=learner_id,
            user__business=business,
            qualification__id=qualification_id,
            is_active=True
        )
        learner_user = learner.user
    except Learner.DoesNotExist:
        raise Http404("Invalid learner or not associated with this qualification.")

    try:
        unit = Unit.objects.get(id=unit_id, qualification__id=qualification_id)
    except Unit.DoesNotExist:
        raise Http404("Invalid unit.")

    # Check if user is IQA, EQA, or assessor for the qualification
    is_iqa = IQA.objects.filter(
        user=user_business,
        qualification__id=qualification_id
    ).exists()
    is_eqa = EQA.objects.filter(
        user=user_business,
        qualification__id=qualification_id,
        learners__id=learner_id
    ).exists()
    is_assessor = Assessor.objects.filter(
        user=user_business,
        qualification__id=qualification_id
    ).exists()

    # If not admin, verify user is IQA, EQA, or assessor and learner is assigned
    if not is_admin:
        if not (is_iqa or is_eqa or is_assessor):
            raise Http404("You are not authorized to view this feedback history.")
        if is_iqa and learner.iqa != user_business:
            raise Http404("This learner is not assigned to you as an IQA.")
        if is_assessor and learner.assessor != user_business:
            raise Http404("This learner is not assigned to you as an assessor.")
        # For EQA, learner assignment is already checked in is_eqa query

    feedback_data = Sampling.objects.filter(
        evidence_submission__user=learner_user,
        evidence_submission__assessment_criterion__learning_outcome__unit=unit
    ).select_related('iqa__user').order_by('-created_at')

    feedback_list = [
        {
            'sampling_type': sampling.sampling_type,
            'outcome': sampling.outcome,
            'comments': sampling.comments or "No comments provided",
            'iqa_name': sampling.iqa.user.full_name or sampling.iqa.user.email,
            'created_at': sampling.created_at
        }
        for sampling in feedback_data
    ]

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': learner.qualification,
        'learner': learner,
        'learner_name': learner_user.user.full_name or learner_user.user.email,
        'unit': unit,
        'feedback_data': feedback_list,
    }

    return render(request, 'iqa_feedback_history.html', context)

@login_required
def iqa_feedback_to_assessor_view(request, qualification_id):
       """
       Allows an IQA to provide feedback to an assessor who shares learners.
       Saves feedback in IQAFeedbackToAssessor without creating notifications.
       """
       business_id = request.session.get('business_id')
       if not business_id:
           raise Http404("No business selected. Please log in again.")

       try:
           user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
           business = user_business.business
       except UserBusiness.DoesNotExist:
           raise Http404("You are not associated with this business.")

       # Check if user is IQA or EQA
       is_iqa = IQA.objects.filter(
           user=user_business,
           qualification__id=qualification_id
       ).exists()
       is_eqa = EQA.objects.filter(
           user=user_business,
           qualification__id=qualification_id
       ).exists()

       if not is_iqa:
           if is_eqa:
               return redirect('qualifications:user_dashboard')
           raise Http404("You are not an IQA for this qualification.")

       if request.method == 'POST':
           form = IQAFeedbackToAssessorForm(request.POST, iqa_user=user_business)
           if form.is_valid():
               with transaction.atomic():
                   # Create IQAFeedbackToAssessor record
                   feedback = IQAFeedbackToAssessor.objects.create(
                       iqa=user_business,
                       assessor=form.cleaned_data['assessor'],
                       sampling_type=form.cleaned_data['sampling_type'],
                       sampling_date=form.cleaned_data['sampling_date'],
                       comments=form.cleaned_data['comments']
                   )
                   # Removed notification creation as per requirement
               messages.success(request, "Feedback submitted successfully.")
               return redirect('qualifications:user_dashboard')
           else:
               messages.error(request, "Error in feedback form. Please check the input.")
       else:
           form = IQAFeedbackToAssessorForm(iqa_user=user_business)

       context = {
           'full_name': request.user.full_name or request.user.email,
           'business': business,
           'qualification_id': qualification_id,
           'form': form,
       }

       return render(request, 'iqa_feedback_to_assessor.html', context)


@login_required
def iqa_feedback_to_assessor_records_view(request, qualification_id=None):
    """
    Displays a list of IQA feedback records for Admins (all records), IQAs (given by them), or Assessors (received by them).
    Includes multi-select filters for Feedback Given By (IQA) and Feedback Given To (Assessor).
    Admins see all records for the business; Assessors see only their records with a locked filter.
    Users with both IQA and Assessor roles see both given and received feedback.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    # Check user roles
    is_iqa = IQA.objects.filter(user=user_business).exists() if qualification_id is None else IQA.objects.filter(
        user=user_business,
        qualification__id=qualification_id
    ).exists()
    is_assessor = Assessor.objects.filter(user=user_business).exists() if qualification_id is None else Assessor.objects.filter(
        user=user_business,
        qualification__id=qualification_id
    ).exists()
    is_admin = user_business.user_type == 'admin'

    if not (is_iqa or is_assessor or is_admin):
        raise Http404("You are not authorized to view this feedback history.")

    # Fetch feedback records based on user role
    if is_admin:
        # Admins see all feedback records for the business
        feedback_records = IQAFeedbackToAssessor.objects.filter(
            iqa__business=business
        ).select_related('iqa__user', 'assessor__user').order_by('-created_at')
    else:
        # For IQA, Assessor, or both, fetch records where user is either IQA or Assessor
        feedback_records = IQAFeedbackToAssessor.objects.filter(
            Q(iqa=user_business) | Q(assessor=user_business)
        ).select_related('iqa__user', 'assessor__user').order_by('-created_at')

    # Prepare feedback data
    feedback_data = [
        {
            'id': str(feedback.id),
            'iqa_name': feedback.iqa.user.full_name or feedback.iqa.user.email,
            'iqa_id': str(feedback.iqa.id),
            'assessor_name': feedback.assessor.user.full_name or feedback.assessor.user.user.email,
            'assessor_id': str(feedback.assessor.id),
            'sampling_type': feedback.sampling_type,
            'sampling_date': feedback.sampling_date,
            'feedback_date': feedback.created_at,
            'comments': feedback.comments
        }
        for feedback in feedback_records
    ]

    # Get lists of IQAs and assessors for filters
    iqa_users = UserBusiness.objects.filter(
        id__in=IQAFeedbackToAssessor.objects.filter(iqa__business=business).values('iqa_id').distinct()
    ).select_related('user').order_by('user__full_name')

    if is_assessor and not is_admin:
        # Lock assessor filter to current user for non-admin Assessors
        assessor_users = UserBusiness.objects.filter(id=user_business.id).select_related('user')
    else:
        # Admins and IQAs see all assessors
        assessor_users = UserBusiness.objects.filter(
            id__in=IQAFeedbackToAssessor.objects.filter(iqa__business=business).values('assessor_id').distinct()
        ).select_related('user').order_by('user__full_name')

    # Debug prints
    logger.debug(f"Feedback Data: {[(f['iqa_id'], f['assessor_id']) for f in feedback_data]}")
    logger.info(f"IQA Users: {[(str(u.id), u.user.full_name or u.user.email) for u in iqa_users]}")
    logger.info(f"Assessor Users: {[(str(u.id), u.user.full_name or u.user.email) for u in assessor_users]}")

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification_id': qualification_id,
        'feedback_data': feedback_data,
        'iqa_users': [
            {'id': str(user.id), 'name': user.user.full_name or user.user.email}
            for user in iqa_users
        ],
        'assessor_users': [
            {'id': str(user.id), 'name': user.user.full_name or user.user.email}
            for user in assessor_users
        ],
        'is_assessor': is_assessor,
        'is_admin': is_admin,
        'user_business_id': str(user_business.id),
    }

    return render(request, 'iqa_feedback_to_assessor_records.html', context)

@login_required
def doc_requirement(request):
    # Check if user is admin
    business_id = request.session.get('business_id')
    if not business_id:
        messages.error(request, "Business ID not found in session.")
        return redirect('login')

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        if user_business.user_type != 'admin':
            messages.error(request, "You are not authorized to access this page.")
            return redirect('login')
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not associated with this business.")
        return redirect('login')

    # Get qualification
    qual_id = request.GET.get('id')
    qualification = get_object_or_404(Qual, id=qual_id)

    # Get existing document requirements
    document_requirements = DocumentRequirement.objects.filter(qualification=qualification)

    # Handle edit mode
    edit_id = request.GET.get('edit')
    doc = None
    if edit_id:
        doc = get_object_or_404(DocumentRequirement, id=edit_id, qualification=qualification)
        form = DocumentRequirementForm(instance=doc)
    else:
        form = DocumentRequirementForm()

    # Handle form submission (create/edit/delete)
    if request.method == 'POST':
        if 'delete' in request.POST:
            # Handle deletion
            doc_id = request.POST.get('delete')
            doc_to_delete = get_object_or_404(DocumentRequirement, id=doc_id, qualification=qualification)
            doc_to_delete.delete()
            messages.success(request, "Document requirement deleted successfully.")
            return redirect(f"{reverse('qualifications:doc_requirement')}?id={qual_id}")
        else:
            # Handle create/edit
            if edit_id:
                # Update existing instance
                form = DocumentRequirementForm(request.POST, request.FILES, instance=doc)
            else:
                # Create new instance
                form = DocumentRequirementForm(request.POST, request.FILES)
                
            if form.is_valid():
                doc = form.save(commit=False)
                doc.qualification = qualification
                doc.save()
                messages.success(request, "Document requirement saved successfully.")
                return redirect(f"{reverse('qualifications:doc_requirement')}?id={qual_id}")
            else:
                messages.error(request, "Please correct the errors in the form.")

    return render(request, 'doc_requirement.html', {
        'qualification': qualification,
        'form': form,
        'document_requirements': document_requirements,
    })

@login_required
def iqa_feedback_view(request, qualification_id, learner_id, unit_id):
    """
    Allows an IQA to provide feedback for a specific unit, including Sampling Type, Outcome, and Comments.
    Sends email notification to assessor if outcome is Non-Conformance.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    try:
        learner = Learner.objects.get(
            id=learner_id,
            user__business=business,
            qualification__id=qualification_id,
            is_active=True
        )
        learner_user = learner.user
    except Learner.DoesNotExist:
        raise Http404("Invalid learner or not associated with this qualification.")

    try:
        unit = Unit.objects.get(id=unit_id, qualification__id=qualification_id)
    except Unit.DoesNotExist:
        raise Http404("Invalid unit.")

    # Check if user is IQA for the qualification
    if not IQA.objects.filter(
        user=user_business,
        qualification__id=qualification_id
    ).exists():
        raise Http404("You are not authorized to provide feedback as an IQA.")

    # Role-based access check
    if learner.iqa != user_business:
        raise Http404("This learner is not assigned to you.")

    # Check if all assessment criteria for the unit are ACCEPTED
    all_ac_accepted = True
    for lo in unit.learning_outcomes.all():
        for ac in lo.assessment_criteria.all():
            submission = EvidenceSubmission.objects.filter(
                user=learner_user,
                assessment_criterion=ac
            ).order_by('-submitted_at').first()
            if not submission or submission.status != 'ACCEPTED':
                all_ac_accepted = False
                break
        if not all_ac_accepted:
            break

    if not all_ac_accepted:
        raise Http404("Cannot provide feedback until all assessment criteria are accepted.")

    # Fetch a representative evidence submission for the unit
    evidence_submission = EvidenceSubmission.objects.filter(
        user=learner_user,
        assessment_criterion__learning_outcome__unit=unit
    ).order_by('-submitted_at').first()

    if not evidence_submission:
        raise Http404("No evidence submissions found for this unit.")

    if request.method == 'POST':
        form = IQAFeedbackForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Create Sampling record
                sampling = Sampling.objects.create(
                    evidence_submission=evidence_submission,
                    iqa=user_business,
                    sampling_type=form.cleaned_data['sampling_type'],
                    outcome=form.cleaned_data['outcome'],
                    comments=form.cleaned_data['comments']
                )
                # Create IQAFeedback record
                IQAFeedback.objects.create(
                    sampling=sampling,
                    assessor=learner.assessor,
                    feedback=form.cleaned_data['comments'] or f"{form.cleaned_data['sampling_type']} sampling: {form.cleaned_data['outcome']}"
                )
                # Send email notification to assessor if outcome is Non-Conformance
                if form.cleaned_data['outcome'] == 'NON_CONFORMANCE' and learner.assessor:
                    try:
                        send_non_conformance_email(
                            recipient_email=learner.assessor.user.email,
                            iqa_name=user_business.user.full_name or user_business.user.email,
                            learner_name=learner_user.user.full_name or learner_user.user.email,
                            qualification_title=learner.qualification.qualification_title,
                            unit_title=unit.unit_title,
                            business_name=business.name,
                            business_id=business.business_id
                        )
                        logger.info(f"Sent non-conformance notification to {learner.assessor.user.email}")
                    except Exception as e:
                        logger.error(f"Failed to send non-conformance notification to {learner.assessor.user.email}: {str(e)}")
                        messages.warning(request, f"Feedback submitted, but failed to notify assessor: {str(e)}")
                    # Create in-system notification for assessor
                    feedback_url = reverse('qualifications:iqa_feedback_history', args=[qualification_id, learner_id, unit_id])
                    message = (
                        f"{learner_user.user.full_name or learner_user.user.email}'s {unit.unit_title} "
                        f"has been marked unsatisfactory by {user_business.user.full_name or user_business.user.email}. "
                        f"View details: {request.build_absolute_uri(feedback_url)}"
                    )
                    Notification.objects.create(
                        user=learner.assessor,
                        evidence_submission=evidence_submission,
                        message=message
                    )
            messages.success(request, "IQA feedback submitted successfully.")
            return redirect('qualifications:iqa_feedback_history_view', qualification_id=qualification_id, learner_id=learner_id)
        else:
            messages.error(request, "Error in feedback form. Please check the input.")
    else:
        form = IQAFeedbackForm()

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': learner.qualification,
        'learner': learner,
        'learner_name': learner_user.user.full_name or learner_user.user.email,
        'unit': unit,
        'form': form,
    }

    return render(request, 'iqa_feedback.html', context)

@login_required
def submit_docs(request, qualification_id):
    """
    Displays mandatory document requirements for a qualification and allows learners to submit documents.
    Only active learners for the qualification can access this view.
    Allows uploads for Not Submitted, Pending, or Rejected statuses, locking only for Accepted.
    Updates existing Pending or Rejected submissions, replacing files and comments if provided.
    Sends notification email to assessor or admin on submission or update.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        messages.error(request, "Business ID not found in session.")
        return redirect('login')

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = Business.objects.get(business_id=business_id)
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not associated with this business.")
        return redirect('login')
    except Business.DoesNotExist:
        messages.error(request, "Business not found.")
        return redirect('login')

    qualification = get_object_or_404(Qual, id=qualification_id)
    try:
        learner = Learner.objects.get(user=user_business, qualification=qualification, is_active=True)
    except Learner.DoesNotExist:
        messages.error(request, "You are not an active learner for this qualification.")
        return redirect('qualifications:user_dashboard')

    # Get document requirements and submissions
    document_requirements = DocumentRequirement.objects.filter(qualification=qualification)
    submissions = LearnerDocumentSubmission.objects.filter(learner=learner, document_requirement__qualification=qualification)
    submission_dict = {str(s.document_requirement_id): s for s in submissions}
    logger.debug(f"submission_dict type: {type(submission_dict)}")
    logger.debug(f"submission_dict keys: {list(submission_dict.keys())}")
    logger.debug(f"submission_dict contents: {[(k, str(v.document_file) if v.document_file else 'None', v.document_file.name if v.document_file else 'None', v.document_file.url if v.document_file else 'None', v.status) for k, v in submission_dict.items()]}")
    logger.debug(f"document_requirements IDs: {[str(doc.id) for doc in document_requirements]}")
    null_files = [(k, v.status) for k, v in submission_dict.items() if not v.document_file]
    if null_files:
        logger.warning(f"WARNING: Null document_file found for submissions: {null_files}")

    form = LearnerDocumentSubmissionForm()

    if request.method == 'POST':
        doc_id = request.POST.get('doc_id')
        document_requirement = get_object_or_404(DocumentRequirement, id=doc_id, qualification=qualification)
        form = LearnerDocumentSubmissionForm(request.POST, request.FILES)
        logger.info(f"POST data: {request.POST}")
        logger.info(f"FILES: {request.FILES}")
        form.instance.learner = learner
        form.instance.document_requirement = document_requirement
        if form.is_valid():
            # Check if a submission exists
            existing_submission = submission_dict.get(str(document_requirement.id))
            logger.info(f"Existing submission: {existing_submission}, Status: {existing_submission.status if existing_submission else 'None'}, File: {existing_submission.document_file if existing_submission else 'None'}")
            if existing_submission and existing_submission.status == 'ACCEPTED':
                messages.error(request, "This document has been accepted and cannot be resubmitted.")
            else:
                with transaction.atomic():
                    if existing_submission and existing_submission.status in ['PENDING', 'REJECTED']:
                        # Update existing submission
                        if 'document_file' in request.FILES:
                            existing_submission.document_file = request.FILES['document_file']
                        existing_submission.comments = form.cleaned_data.get('comments', existing_submission.comments)
                        existing_submission.status = 'PENDING'
                        existing_submission.save()
                        logger.info(f"Updated submission: ID={existing_submission.id}, File={existing_submission.document_file}, Status={existing_submission.status}")
                        messages.success(request, "Document updated successfully.")
                    else:
                        # Create new submission
                        new_submission = form.save(commit=False)
                        if 'document_file' in request.FILES:
                            new_submission.document_file = request.FILES['document_file']
                        else:
                            logger.error("No document_file in request.FILES")
                            messages.error(request, "A file is required for new submissions.")
                            return redirect('qualifications:submit_docs', qualification_id=qualification_id)
                        new_submission.learner = learner
                        new_submission.document_requirement = document_requirement
                        new_submission.status = 'PENDING'
                        try:
                            new_submission.save()
                            logger.info(f"New submission saved: ID={new_submission.id}, File={new_submission.document_file}, Name={new_submission.document_file.name if new_submission.document_file else 'None'}, URL={new_submission.document_file.url if new_submission.document_file else 'None'}")
                            messages.success(request, "Document submitted successfully.")
                        except Exception as e:
                            logger.error(f"Error saving submission: {str(e)}")
                            messages.error(request, f"Error saving document: {str(e)}")
                            return redirect('qualifications:submit_docs', qualification_id=qualification_id)

                    # Send notification email to assessor or admin synchronously
                    recipient_email = None
                    recipient_name = None
                    try:
                        if learner.assessor:
                            recipient_email = learner.assessor.user.email
                            recipient_name = learner.assessor.user.full_name or recipient_email
                        else:
                            admin_user = UserBusiness.objects.filter(business__business_id=business.business_id, user_type='admin').select_related('user').first()
                            if admin_user:
                                recipient_email = admin_user.user.email
                                recipient_name = admin_user.user.full_name or recipient_email
                            else:
                                logger.warning(f"No assessor or admin for learner {learner.id} for qualification {qualification_id}")
                                messages.warning(request, "Document submitted, but no assessor or admin to notify.")
                                return redirect('qualifications:submit_docs', qualification_id=qualification_id)
                        learner_name = learner.user.user.full_name or learner.user.user.email
                        logger.debug(
                            f"Preparing to send Document notification: "
                            f"recipient_email={recipient_email}, "
                            f"recipient_name={recipient_name}, "
                            f"learner_name={learner_name}, "
                            f"qualification_title={qualification.qualification_title}"
                        )
                        if not recipient_email:
                            raise ValueError("Recipient email is empty")
                        send_document_submission_notification_email(
                            assessor_email=recipient_email,
                            assessor_name=recipient_name,
                            learner_name=learner_name,
                            qualification_title=qualification.qualification_title,
                            business_name=business.name,
                            business_id=business.business_id,
                            submission_type='Document'
                        )
                        logger.info(f"Sent document submission notification to {recipient_email}")
                    except Exception as e:
                        logger.error(f"Failed to send document submission notification to {recipient_email if recipient_email else 'unknown'}: {str(e)}")
                        messages.warning(request, f"Document submitted, but failed to notify recipient: {str(e)}")

                    # Refresh submissions after save
                    submissions = LearnerDocumentSubmission.objects.filter(learner=learner, document_requirement__qualification=qualification)
                    submission_dict = {str(s.document_requirement_id): s for s in submissions}
                    logger.info(f"Updated submission_dict: {[(k, str(v.document_file) if v.document_file else 'None', v.document_file.name if v.document_file else 'None', v.document_file.url if v.document_file else 'None', v.status) for k, v in submission_dict.items()]}")
                    return redirect('qualifications:submit_docs', qualification_id=qualification_id)
        else:
            logger.error(f"Form errors: {form.errors}")
            logger.error(f"Non-field errors: {form.non_field_errors()}")
            logger.error(f"Field errors: {form['document_file'].errors}")
            messages.error(request, "Please correct the errors in the form.")

    # Prepare document requirements with submission status
    doc_data = []
    for doc in document_requirements:
        submission = submission_dict.get(str(doc.id))
        can_upload = not submission or submission.status in ['PENDING', 'REJECTED']  # Allow for Pending, Rejected, Not Submitted
        doc_data.append({
            'id': doc.id,
            'title': doc.title,
            'description': doc.description,
            'template': doc.template,
            'can_upload': can_upload,
            'status': submission.status if submission else None,
            'comments': submission.comments if submission else None,
        })

    return render(request, 'submit_docs.html', {
        'qualification': qualification,
        'business': business,
        'full_name': user_business.user.full_name or user_business.user.email,
        'document_requirements': doc_data,
        'form': form,
        'submission_dict': submission_dict,
    })

@login_required
def learner_view(request, qualification_id):
    """
    Displays qualification details, completion percentage, units, learning outcomes, and assessment criteria
    for a user with the Learner role. Supports multiple file uploads per evidence submission and workbook submission per LO.
    Allows editing submissions until assessor sets ACCEPTED or REJECTED.
    Sends notification email to assessor or admin on evidence or workbook submission/update.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    try:
        learner = Learner.objects.get(
            user=user_business,
            qualification__id=qualification_id,
            is_active=True
        )
        qualification = learner.qualification
    except Learner.DoesNotExist:
        raise Http404("You are not a learner for this qualification.")

    total_ac = AC.objects.filter(learning_outcome__unit__qualification=qualification).count()
    accepted_ac = EvidenceSubmission.objects.filter(
        user=user_business,
        assessment_criterion__learning_outcome__unit__qualification=qualification,
        status='ACCEPTED'
    ).count()
    completion_percentage = (accepted_ac / total_ac * 100) if total_ac > 0 else 0

    units = Unit.objects.filter(qualification=qualification).prefetch_related(
        'learning_outcomes__assessment_criteria__evidence_submissions',
        'learning_outcomes__workbook_submissions'
    )

    structured_data = []
    for unit in units:
        unit_data = {
            'title': unit.unit_title,
            'number': unit.unit_number,
            'learning_outcomes': []
        }
        for lo in unit.learning_outcomes.all():
            lo_data = {
                'detail': lo.lo_detail,
                'id': lo.id,
                'has_feedback': Feedback.objects.filter(
                    evidence_submission__user=user_business,
                    evidence_submission__assessment_criterion__learning_outcome=lo,
                    evidence_submission__assessment_criterion__learning_outcome__unit__qualification=qualification
                ).exists(),
                'assessment_criteria': [],
                'workbook_submission': None,
                'workbook_status': 'Not Submitted',
                'workbook_url': None,
                'can_upload_workbook': True
            }
            workbook_submission = WorkbookSubmission.objects.filter(
                user=user_business,
                learning_outcome=lo
            ).order_by('-submitted_at').first()
            if workbook_submission:
                lo_data['workbook_submission'] = workbook_submission
                lo_data['workbook_status'] = workbook_submission.status
                if workbook_submission.status == 'REJECTED':
                    lo_data['workbook_status'] = 'Resubmission Required'
                lo_data['workbook_url'] = workbook_submission.workbook_file.url if workbook_submission.workbook_file else None
                lo_data['can_upload_workbook'] = workbook_submission.status not in ['ACCEPTED', 'REJECTED']
            for ac in lo.assessment_criteria.all():
                submission = EvidenceSubmission.objects.filter(
                    user=user_business,
                    assessment_criterion=ac
                ).order_by('-submitted_at').first()
                status = submission.status if submission else 'Not Submitted'
                if status == 'REJECTED':
                    status = 'Resubmission Required'
                lo_data['assessment_criteria'].append({
                    'detail': ac.ac_detail,
                    'id': ac.id,
                    'status': status,
                    'can_upload': status not in ['ACCEPTED', 'REJECTED'],
                    'evidence_url': reverse('qualifications:learner_evidence', args=[str(qualification_id), str(learner.id), str(ac.id)]) if submission else None,
                    'evidence_detail': submission.evidence_detail if submission else ''
                })
            unit_data['learning_outcomes'].append(lo_data)
        structured_data.append(unit_data)

    if request.method == 'POST':
        if 'evidence_submit' in request.POST:
            form = EvidenceSubmissionForm(request.POST, request.FILES)
            if form.is_valid():
                ac_id = request.POST.get('ac_id')
                try:
                    ac = AC.objects.get(
                        id=ac_id,
                        learning_outcome__unit__qualification=qualification
                    )
                    latest_submission = EvidenceSubmission.objects.filter(
                        user=user_business,
                        assessment_criterion=ac
                    ).order_by('-submitted_at').first()
                    
                    with transaction.atomic():
                        if latest_submission and latest_submission.status == 'SUBMITTED':
                            latest_submission.evidence_detail = form.cleaned_data['evidence_detail']
                            latest_submission.save()
                            if request.FILES.getlist('evidence_files'):
                                latest_submission.files.all().delete()
                                for file in request.FILES.getlist('evidence_files'):
                                    EvidenceFile.objects.create(
                                        evidence_submission=latest_submission,
                                        evidence_file=file
                                    )
                            messages.success(request, "Evidence updated successfully.")
                        else:
                            submission = EvidenceSubmission.objects.create(
                                user=user_business,
                                assessment_criterion=ac,
                                evidence_detail=form.cleaned_data['evidence_detail'],
                                status='SUBMITTED'
                            )
                            for file in request.FILES.getlist('evidence_files'):
                                EvidenceFile.objects.create(
                                    evidence_submission=submission,
                                    evidence_file=file
                                )
                            messages.success(request, "Evidence submitted successfully.")

                        # Send notification email to assessor or admin synchronously
                        recipient_email = None
                        recipient_name = None
                        try:
                            if learner.assessor:
                                recipient_email = learner.assessor.user.email
                                recipient_name = learner.assessor.user.full_name or recipient_email
                            else:
                                admin_user = UserBusiness.objects.filter(business__business_id=business.business_id, user_type='admin').select_related('user').first()
                                if admin_user:
                                    recipient_email = admin_user.user.email
                                    recipient_name = admin_user.user.full_name or recipient_email
                                else:
                                    logger.warning(f"No assessor or admin for learner {learner.id} for qualification {qualification_id}")
                                    messages.warning(request, "Evidence submitted, but no assessor or admin to notify.")
                                    return redirect('qualifications:learner_view', qualification_id=qualification_id)
                            learner_name = learner.user.user.full_name or learner.user.user.email
                            logger.debug(
                                f"Preparing to send Evidence notification: "
                                f"recipient_email={recipient_email}, "
                                f"recipient_name={recipient_name}, "
                                f"learner_name={learner_name}, "
                                f"qualification_title={qualification.qualification_title}"
                            )
                            if not recipient_email:
                                raise ValueError("Recipient email is empty")
                            send_document_submission_notification_email(
                                assessor_email=recipient_email,
                                assessor_name=recipient_name,
                                learner_name=learner_name,
                                qualification_title=qualification.qualification_title,
                                business_name=business.name,
                                business_id=business.business_id,
                                submission_type='Evidence'
                            )
                            logger.info(f"Sent evidence submission notification to {recipient_email}")
                        except Exception as e:
                            logger.error(f"Failed to send evidence submission notification to {recipient_email if recipient_email else 'unknown'}: {str(e)}")
                            messages.warning(request, f"Evidence submitted, but failed to notify recipient: {str(e)}")

                        return redirect('qualifications:learner_view', qualification_id=qualification_id)
                except AC.DoesNotExist:
                    messages.error(request, "Invalid assessment criterion.")
                except Exception as e:
                    messages.error(request, f"Error submitting evidence: {str(e)}")
            else:
                messages.error(request, "Error submitting evidence. Please check the form.")
        elif 'workbook_submit' in request.POST:
            form = WorkbookSubmissionForm(request.POST, request.FILES)
            if form.is_valid():
                lo_id = request.POST.get('lo_id')
                try:
                    lo = LO.objects.get(
                        id=lo_id,
                        unit__qualification=qualification
                    )
                    latest_submission = WorkbookSubmission.objects.filter(
                        user=user_business,
                        learning_outcome=lo
                    ).order_by('-submitted_at').first()
                    
                    with transaction.atomic():
                        if latest_submission and latest_submission.status == 'SUBMITTED':
                            latest_submission.workbook_file = form.cleaned_data['workbook_file']
                            latest_submission.submitted_at = timezone.now()
                            latest_submission.save()
                            messages.success(request, "Workbook updated successfully.")
                        else:
                            submission = WorkbookSubmission.objects.create(
                                user=user_business,
                                learning_outcome=lo,
                                workbook_file=form.cleaned_data['workbook_file'],
                                status='SUBMITTED'
                            )
                            messages.success(request, "Workbook submitted successfully.")

                        # Send notification email to assessor or admin synchronously
                        recipient_email = None
                        recipient_name = None
                        try:
                            if learner.assessor:
                                recipient_email = learner.assessor.user.email
                                recipient_name = learner.assessor.user.full_name or recipient_email
                            else:
                                admin_user = UserBusiness.objects.filter(business__business_id=business.business_id, user_type='admin').select_related('user').first()
                                if admin_user:
                                    recipient_email = admin_user.user.email
                                    recipient_name = admin_user.user.full_name or recipient_email
                                else:
                                    logger.warning(f"No assessor or admin for learner {learner.id} for qualification {qualification_id}")
                                    messages.warning(request, "Workbook submitted, but no assessor or admin to notify.")
                                    return redirect('qualifications:learner_view', qualification_id=qualification_id)
                            learner_name = learner.user.user.full_name or learner.user.user.email
                            logger.debug(
                                f"Preparing to send Workbook notification: "
                                f"recipient_email={recipient_email}, "
                                f"recipient_name={recipient_name}, "
                                f"learner_name={learner_name}, "
                                f"qualification_title={qualification.qualification_title}"
                            )
                            if not recipient_email:
                                raise ValueError("Recipient email is empty")
                            send_document_submission_notification_email(
                                assessor_email=recipient_email,
                                assessor_name=recipient_name,
                                learner_name=learner_name,
                                qualification_title=qualification.qualification_title,
                                business_name=business.name,
                                business_id=business.business_id,
                                submission_type='Workbook'
                            )
                            logger.info(f"Sent workbook submission notification to {recipient_email}")
                        except Exception as e:
                            logger.error(f"Failed to send workbook submission notification to {recipient_email if recipient_email else 'unknown'}: {str(e)}")
                            messages.warning(request, f"Workbook submitted, but failed to notify recipient: {str(e)}")

                        return redirect('qualifications:learner_view', qualification_id=qualification_id)
                except LO.DoesNotExist:
                    messages.error(request, "Invalid learning outcome.")
                except Exception as e:
                    messages.error(request, f"Error submitting workbook: {str(e)}")
            else:
                messages.error(request, "Error submitting workbook. Please check the form.")
    else:
        form = EvidenceSubmissionForm()

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': qualification,
        'completion_percentage': round(completion_percentage, 2),
        'structured_data': structured_data,
        'form': form,
        'learner': learner,
    }

    return render(request, 'learner_view.html', context)

@login_required
def doc_check(request, qualification_id, learner_id):
    """
    Displays all mandatory document requirements for a qualification and allows the assessor to accept or reject submitted documents.
    Shows all required documents, including those not yet submitted, similar to IQA view.
    Only accessible to the assigned assessor for the learner.
    Allows status changes for any submission (PENDING, ACCEPTED, REJECTED), showing the current status in the form.
    Includes IQA remarks for visibility.
    Sends email notification to learner for accepted or rejected documents.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        messages.error(request, "Business ID not found in session.")
        return redirect('login')

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = Business.objects.get(business_id=business_id)
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not associated with this business.")
        return redirect('login')
    except Business.DoesNotExist:
        messages.error(request, "Business not found.")
        return redirect('login')

    qualification = get_object_or_404(Qual, id=qualification_id)
    try:
        learner = Learner.objects.get(id=learner_id, qualification=qualification, is_active=True)
    except Learner.DoesNotExist:
        messages.error(request, "Invalid learner or not associated with this qualification.")
        return redirect('qualifications:assessor_view', qualification_id=qualification_id)

    # Check if the user is the assigned assessor
    try:
        assessor = Assessor.objects.get(user=user_business, qualification=qualification)
        if learner.assessor != user_business:
            messages.error(request, "You are not the assigned assessor for this learner.")
            return redirect('qualifications:assessor_view', qualification_id=qualification_id)
    except Assessor.DoesNotExist:
        messages.error(request, "You are not an assessor for this qualification.")
        return redirect('qualifications:assessor_view', qualification_id=qualification_id)

    # Get document requirements, submissions, and IQA remarks
    document_requirements = DocumentRequirement.objects.filter(qualification=qualification)
    submissions = LearnerDocumentSubmission.objects.filter(learner=learner, document_requirement__qualification=qualification)
    submission_dict = {s.document_requirement_id: s for s in submissions}
    remarks = IQADocumentRemark.objects.filter(submission__in=submissions)
    remark_dict = {r.submission_id: r for r in remarks}

    if request.method == 'POST':
        submission_id = request.POST.get('submission_id')
        submission = get_object_or_404(LearnerDocumentSubmission, id=submission_id, learner=learner)
        form = DocumentCheckForm(request.POST, instance=submission)
        form.instance.assessor = user_business
        if form.is_valid():
            with transaction.atomic():
                submission = form.save()
                if submission.status in ['ACCEPTED', 'REJECTED']:
                    status_text = 'accepted' if submission.status == 'ACCEPTED' else 'rejected'
                    message = f"Your document '{submission.document_requirement.title}' was {status_text}. Comments: {submission.comments or 'None'}"
                    notification = Notification.objects.create(
                        user=learner.user,
                        message=message
                    )
                    try:
                        send_notification_email(
                            recipient_email=learner.user.user.email,
                            learner_name=learner.user.user.full_name or learner.user.user.email,
                            business_name=business.name,
                            notification_message=message,
                            notification_date=notification.created_at
                        )
                        logger.info(f"Sent notification email to {learner.user.user.email}")
                    except Exception as e:
                        logger.error(f"Failed to send notification email to {learner.user.user.email}: {str(e)}")
                        messages.warning(request, f"Document updated, but failed to notify learner: {str(e)}")
            messages.success(request, f"Document {submission.document_requirement.title} updated successfully.")
            return redirect('qualifications:doc_check', qualification_id=qualification_id, learner_id=learner_id)
        else:
            messages.error(request, "Please correct the errors in the form.")
            # Rebuild submission_data with the invalid form
            submission_data = []
            for doc in document_requirements:
                submission = submission_dict.get(doc.id)
                remark = remark_dict.get(submission.id) if submission else None
                form_instance = DocumentCheckForm(instance=submission) if submission and submission.id != submission_id else form
                submission_data.append({
                    'id': submission.id if submission else None,
                    'title': doc.title,
                    'description': doc.description,
                    'template': doc.template,
                    'document_file': submission.document_file if submission else None,
                    'status': submission.status if submission else 'Not Submitted',
                    'comments': submission.comments if submission else None,
                    'form': form_instance if submission else None,
                    'remark': remark.remark if remark else None,
                    'remark_comments': remark.comments if remark else None,
                })
    else:
        submission_data = []
        for doc in document_requirements:
            submission = submission_dict.get(doc.id)
            remark = remark_dict.get(submission.id) if submission else None
            submission_data.append({
                'id': submission.id if submission else None,
                'title': doc.title,
                'description': doc.description,
                'template': doc.template,
                'document_file': submission.document_file if submission else None,
                'status': submission.status if submission else 'Not Submitted',
                'comments': submission.comments if submission else None,
                'form': DocumentCheckForm(instance=submission) if submission else None,
                'remark': remark.remark if remark else None,
                'remark_comments': remark.comments if remark else None,
            })

    return render(request, 'doc_check.html', {
        'qualification': qualification,
        'business': business,
        'full_name': user_business.user.full_name or user_business.user.email,
        'learner': learner,
        'learner_name': learner.user.user.full_name or learner.user.user.email,
        'submission_data': submission_data,
    })

@login_required
def iqa_submitted_docs(request, qualification_id, learner_id):
    """
    Displays mandatory document submissions for a learner, similar to submit_docs, for IQA users.
    Includes an IQA Remarks column to select OK or Non-Conformance with comments.
    Remarks are visible to the learner and assessor.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        messages.error(request, "No business selected. Please log in again.")
        return redirect('login')

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not associated with this business.")
        return redirect('login')

    qualification = get_object_or_404(Qual, id=qualification_id)
    try:
        learner = Learner.objects.get(id=learner_id, qualification=qualification, is_active=True)
    except Learner.DoesNotExist:
        messages.error(request, "Invalid learner or not associated with this qualification.")
        return redirect('qualifications:iqa_view', qualification_id=qualification_id)

    # Check if user is IQA for the qualification and learner
    if not IQA.objects.filter(user=user_business, qualification=qualification).exists():
        messages.error(request, "You are not an IQA for this qualification.")
        return redirect('qualifications:iqa_view', qualification_id=qualification_id)
    if learner.iqa != user_business:
        messages.error(request, "This learner is not assigned to you as an IQA.")
        return redirect('qualifications:iqa_view', qualification_id=qualification_id)

    # Get document requirements and submissions
    document_requirements = DocumentRequirement.objects.filter(qualification=qualification)
    submissions = LearnerDocumentSubmission.objects.filter(learner=learner, document_requirement__qualification=qualification)
    submission_dict = {s.document_requirement_id: s for s in submissions}
    remarks = IQADocumentRemark.objects.filter(submission__in=submissions, iqa=user_business)
    remark_dict = {r.submission_id: r for r in remarks}

    if request.method == 'POST':
        submission_id = request.POST.get('submission_id')
        submission = get_object_or_404(LearnerDocumentSubmission, id=submission_id, learner=learner)
        form = IQADocumentRemarkForm(request.POST)
        form.instance.submission = submission
        form.instance.iqa = user_business
        if form.is_valid():
            with transaction.atomic():
                # Delete existing remark if present
                IQADocumentRemark.objects.filter(submission=submission, iqa=user_business).delete()
                # Save new remark
                form.save()
                # Notify learner and assessor
                if form.instance.remark == 'NON_CONFORMANCE':
                    Notification.objects.create(
                        user=learner.user,
                        message=f"IQA marked document '{submission.document_requirement.title}' as Non-Conformance. Comments: {form.instance.comments}",
                    )
                    if learner.assessor:
                        Notification.objects.create(
                            user=learner.assessor,
                            message=f"IQA marked {learner.user.user.full_name}'s document '{submission.document_requirement.title}' as Non-Conformance. Comments: {form.instance.comments}",
                        )
            messages.success(request, "IQA remark saved successfully.")
            return redirect('qualifications:iqa_submitted_docs', qualification_id=qualification_id, learner_id=learner_id)
        else:
            messages.error(request, "Please correct the errors in the remark form.")
    else:
        form = IQADocumentRemarkForm()

    # Prepare document requirements with submission and remark data
    doc_data = []
    for doc in document_requirements:
        submission = submission_dict.get(doc.id)
        remark = remark_dict.get(submission.id) if submission else None
        doc_data.append({
            'id': doc.id,
            'title': doc.title,
            'description': doc.description,
            'template': doc.template,
            'submission': submission,
            'status': submission.status if submission else None,
            'comments': submission.comments if submission else None,
            'remark': remark.remark if remark else None,
            'remark_comments': remark.comments if remark else None,
            'remark_form': IQADocumentRemarkForm(instance=remark) if remark else IQADocumentRemarkForm(initial={'remark': 'OK'}),
        })

    return render(request, 'iqa_submitted_docs.html', {
        'qualification': qualification,
        'business': business,
        'full_name': user_business.user.full_name or user_business.user.email,
        'learner': learner,
        'learner_name': learner.user.user.full_name or learner.user.user.email,
        'document_requirements': doc_data,
        'form': form,
    })

@login_required
def eqa_view(request, qualification_id, learner_id):
    """
    Displays a learner's evidence and workbook submissions for a qualification, organized by units, learning outcomes, and assessment criteria, for EQA or Admin users.
    Includes IQA Feedback History, Assessor Feedback History, and View Workbook buttons.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    is_admin = UserBusiness.objects.filter(user=request.user, business=business, user_type='admin').exists()
    eqa = None
    try:
        eqa = EQA.objects.get(
            user=user_business,
            qualification__id=qualification_id
        )
        qualification = eqa.qualification
    except EQA.DoesNotExist:
        if not is_admin:
            raise Http404("You are not an EQA or admin for this qualification.")
        qualification = Qual.objects.get(id=qualification_id)

    try:
        learner = Learner.objects.get(
            id=learner_id,
            qualification=qualification,
            is_active=True
        )
        learner_user = learner.user
    except Learner.DoesNotExist:
        raise Http404("Invalid learner or not associated with this qualification.")

    # Check if learner is assigned to this EQA or user is admin
    if not is_admin and not (eqa and eqa.learners.filter(id=learner_id).exists()):
        raise Http404("This learner is not assigned to you.")

    units = Unit.objects.filter(qualification__id=qualification_id).prefetch_related(
        'learning_outcomes__assessment_criteria__evidence_submissions',
        'learning_outcomes__workbook_submissions'
    )

    structured_data = []
    for unit in units:
        unit_data = {
            'id': str(unit.id),
            'unit_title': unit.unit_title,
            'unit_number': unit.unit_number,
            'learning_outcomes': [],
            'has_iqa_feedback': Sampling.objects.filter(
                evidence_submission__user=learner_user,
                evidence_submission__assessment_criterion__learning_outcome__unit=unit
            ).exists(),
            'all_ac_accepted': True
        }
        for lo in unit.learning_outcomes.all():
            lo_data = {
                'detail': lo.lo_detail,
                'id': str(lo.id),
                'has_feedback': Feedback.objects.filter(
                    evidence_submission__user=learner_user,
                    evidence_submission__assessment_criterion__learning_outcome=lo,
                    evidence_submission__assessment_criterion__learning_outcome__unit__qualification__id=qualification_id
                ).exists(),
                'assessment_criteria': [],
                'workbook_url': None
            }
            workbook_submission = WorkbookSubmission.objects.filter(
                user=learner_user,
                learning_outcome=lo
            ).order_by('-submitted_at').first()
            if workbook_submission and workbook_submission.workbook_file:
                lo_data['workbook_url'] = workbook_submission.workbook_file.url
            for ac in lo.assessment_criteria.all():
                submission = EvidenceSubmission.objects.filter(
                    user=learner_user,
                    assessment_criterion=ac
                ).order_by('-submitted_at').first()
                status = submission.status if submission else 'Not Submitted'
                if status == 'REJECTED':
                    status = 'Resubmission Required'
                if status != 'ACCEPTED':
                    unit_data['all_ac_accepted'] = False
                lo_data['assessment_criteria'].append({
                    'detail': ac.ac_detail,
                    'id': str(ac.id),
                    'status': status,
                    'evidence_url': reverse('qualifications:learner_evidence', args=[str(qualification_id), str(learner_id), str(ac.id)]) if submission else None
                })
            unit_data['learning_outcomes'].append(lo_data)
        structured_data.append(unit_data)

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': qualification,
        'learner': learner,
        'learner_name': learner_user.user.full_name or learner_user.user.email,
        'structured_data': structured_data,
        'is_admin': is_admin
    }

    return render(request, 'eqa_view.html', context)


@login_required
def eqa_learner_list(request, qualification_id):
       """
       Displays a list of learners assigned to the EQA for a specific qualification.
       Includes filtering by assessor and progress range, mimicking iqa_view.
       Learners are sorted by name.
       """
       business_id = request.session.get('business_id')
       if not business_id:
           raise Http404("No business selected. Please log in again.")

       try:
           user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
           business = user_business.business
       except UserBusiness.DoesNotExist:
           raise Http404("You are not associated with this business.")

       try:
           eqa = EQA.objects.get(
               user=user_business,
               qualification__id=qualification_id
           )
           qualification = eqa.qualification
       except EQA.DoesNotExist:
           raise Http404("You are not an EQA for this qualification.")

       learners = eqa.learners.filter(
           qualification=qualification,
           is_active=True
       ).select_related('user__user', 'assessor__user', 'iqa__user')

       # Filtering
       assessor_id = request.GET.get('assessor')
       progress_min = request.GET.get('progress_min')
       progress_max = request.GET.get('progress_max')

       if assessor_id and assessor_id != 'all':
           learners = learners.filter(assessor__id=assessor_id)

       learner_data = []
       total_ac = AC.objects.filter(learning_outcome__unit__qualification=qualification).count()
       total_units = Unit.objects.filter(qualification=qualification).count()

       for learner in learners:
           accepted_ac = EvidenceSubmission.objects.filter(
               user=learner.user,
               assessment_criterion__learning_outcome__unit__qualification=qualification,
               status='ACCEPTED'
           ).count()
           progress = (accepted_ac / total_ac * 100) if total_ac > 0 else 0

           if progress_min and float(progress_min) > progress:
               continue
           if progress_max and float(progress_max) < progress:
               continue

           sampled_units = Sampling.objects.filter(
               iqa=learner.iqa,
               evidence_submission__user=learner.user,
               evidence_submission__assessment_criterion__learning_outcome__unit__qualification=qualification
           ).values('evidence_submission__assessment_criterion__learning_outcome__unit').distinct().count()
           sampling_ratio = (sampled_units / total_units * 100) if total_units > 0 else 0

           assessor_name = (
               learner.assessor.user.full_name or learner.assessor.user.email
               if learner.assessor else ""
           )
           iqa_name = (
               learner.iqa.user.full_name or learner.iqa.user.email
               if learner.iqa else ""
           )

           learner_data.append({
               'name': learner.user.user.full_name or learner.user.user.email,
               'progress': round(progress, 2),
               'sampling_ratio': round(sampling_ratio, 2),
               'learner_id': str(learner.id),
               'assessor_name': assessor_name,
               'iqa_name': iqa_name
           })

       learner_data.sort(key=lambda x: x['name'])

       # Get assessors for filtering
       assessors = UserBusiness.objects.filter(
           assessor_assignments__qualification=qualification
       ).select_related('user')

       context = {
           'full_name': request.user.full_name or request.user.email,
           'business': business,
           'qualification': qualification,
           'learners': learner_data,
           'assessors': assessors,
           'selected_assessor': assessor_id,
           'progress_min': progress_min,
           'progress_max': progress_max,
       }

       return render(request, 'eqa_learner_list.html', context)


@login_required
def learners_list(request, user_business_id, role_type, qualification_id):
    """
    Displays a list of learners assigned to a user for a specific qualification and role (Assessor, IQA, EQA).
    Accessible only to admin users. Shows learner details with progress and sampling ratio, including progress bars.
    """
    try:
        admin_business = UserBusiness.objects.get(user=request.user, user_type='admin')
        business = admin_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    try:
        user_business = UserBusiness.objects.get(id=user_business_id, business=business)
        qualification = Qual.objects.get(id=qualification_id, business=business)
    except (UserBusiness.DoesNotExist, Qual.DoesNotExist):
        messages.error(request, "Invalid user or qualification.")
        return redirect('qualifications:current_users')

    if role_type.lower() not in ['assessor', 'iqa', 'eqa']:
        messages.error(request, "Invalid role type.")
        return redirect('qualifications:current_users')

    learners = []
    if role_type.lower() == 'assessor':
        learners = Learner.objects.filter(
            assessor=user_business,
            qualification=qualification,
            is_active=True
        ).select_related('user__user', 'assessor__user', 'iqa__user')
    elif role_type.lower() == 'iqa':
        learners = Learner.objects.filter(
            iqa=user_business,
            qualification=qualification,
            is_active=True
        ).select_related('user__user', 'assessor__user', 'iqa__user')
    elif role_type.lower() == 'eqa':
        try:
            eqa = EQA.objects.get(user=user_business, qualification=qualification)
            learners = eqa.learners.filter(
                qualification=qualification,
                is_active=True
            ).select_related('user__user', 'assessor__user', 'iqa__user')
        except EQA.DoesNotExist:
            messages.error(request, "User is not an EQA for this qualification.")
            return redirect('qualifications:current_users')

    learner_data = []
    total_ac = AC.objects.filter(learning_outcome__unit__qualification=qualification).count()
    total_units = Unit.objects.filter(qualification=qualification).count()

    for learner in learners:
        accepted_ac = EvidenceSubmission.objects.filter(
            user=learner.user,
            assessment_criterion__learning_outcome__unit__qualification=qualification,
            status='ACCEPTED'
        ).count()
        progress = (accepted_ac / total_ac * 100) if total_ac > 0 else 0

        sampled_units = Sampling.objects.filter(
            iqa=learner.iqa,
            evidence_submission__user=learner.user,
            evidence_submission__assessment_criterion__learning_outcome__unit__qualification=qualification
        ).values('evidence_submission__assessment_criterion__learning_outcome__unit').distinct().count()
        sampling_ratio = (sampled_units / total_units * 100) if total_units > 0 else 0

        learner_data.append({
            'name': learner.user.user.full_name or learner.user.user.email,
            'qualification': learner.qualification.qualification_title,
            'assessor_name': learner.assessor.user.full_name or learner.assessor.user.email if learner.assessor else "None",
            'iqa_name': learner.iqa.user.full_name or learner.iqa.user.email if learner.iqa else "None",
            'progress': round(progress, 2),
            'sampling_ratio': round(sampling_ratio, 2),
            'role': 'Learner',
            'is_active': learner.is_active,
            'learner_id': str(learner.id)
        })

    learner_data.sort(key=lambda x: x['name'])

    context = {
        'full_name': request.user.full_name or request.user.email,
        'business': business,
        'qualification': qualification,
        'user_name': user_business.user.full_name or user_business.user.email,
        'role_type': role_type.title(),
        'learners': learner_data,
        'user': user_business.user  # For back link
    }

    return render(request, 'learners_list.html', context)


@login_required
def iqa_sub_doc_for_eqa(request, qualification_id, learner_id):
    """
    Displays mandatory document submissions for a learner for EQA users, similar to iqa_submitted_docs.
    Shows current IQA remarks (OK or Non-Conformance) without allowing changes.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    is_admin = UserBusiness.objects.filter(user=request.user, business=business, user_type='admin').exists()
    eqa = None
    try:
        eqa = EQA.objects.get(
            user=user_business,
            qualification__id=qualification_id
        )
        qualification = eqa.qualification
    except EQA.DoesNotExist:
        if not is_admin:
            raise Http404("You are not an EQA or admin for this qualification.")
        qualification = Qual.objects.get(id=qualification_id)

    try:
        learner = Learner.objects.get(
            id=learner_id,
            qualification=qualification,
            is_active=True
        )
    except Learner.DoesNotExist:
        raise Http404("Invalid learner or not associated with this qualification.")

    # Check if learner is assigned to this EQA or user is admin
    if not is_admin and not (eqa and eqa.learners.filter(id=learner_id).exists()):
        raise Http404("This learner is not assigned to you.")

    # Get document requirements and submissions
    document_requirements = DocumentRequirement.objects.filter(qualification=qualification)
    submissions = LearnerDocumentSubmission.objects.filter(learner=learner, document_requirement__qualification=qualification)
    submission_dict = {s.document_requirement_id: s for s in submissions}
    remarks = IQADocumentRemark.objects.filter(submission__in=submissions)
    remark_dict = {r.submission_id: r for r in remarks}

    # Prepare document requirements with submission and remark data
    doc_data = []
    for doc in document_requirements:
        submission = submission_dict.get(doc.id)
        remark = remark_dict.get(submission.id) if submission else None
        doc_data.append({
            'id': doc.id,
            'title': doc.title,
            'description': doc.description,
            'template': doc.template,
            'submission': submission,
            'status': submission.status if submission else None,
            'comments': submission.comments if submission else None,
            'remark': remark.remark if remark else None,
            'remark_comments': remark.comments if remark else None,
        })

    return render(request, 'iqa-sub-doc-for-eqa.html', {
        'qualification': qualification,
        'business': business,
        'full_name': user_business.user.full_name or user_business.user.email,
        'learner': learner,
        'learner_name': learner.user.user.full_name or learner.user.user.email,
        'document_requirements': doc_data,
        'is_admin': is_admin,  # Added to context
    })


@login_required
def learner_specific_docs(request, qualification_id: uuid.UUID, learner_id: uuid.UUID):
    qualification = get_object_or_404(Qual, id=qualification_id)
    learner = get_object_or_404(Learner, id=learner_id)
    business = learner.user.business
    documents = LearnerDocsByAssessor.objects.filter(learner=learner)
    
    # Determine user role (learner, assessor, iqa, eqa, or unknown)
    user_role = 'unknown'
    user_business = UserBusiness.objects.get(user=request.user, business=business)
    if Learner.objects.filter(user=user_business, qualification=qualification, is_active=True).exists():
        user_role = 'learner'
    elif Assessor.objects.filter(user=user_business, qualification=qualification).exists():
        user_role = 'assessor'
    elif IQA.objects.filter(user=user_business, qualification=qualification).exists():
        user_role = 'iqa'
    elif EQA.objects.filter(user=user_business, qualification=qualification).exists():
        user_role = 'eqa'
    
    # Restrict access to the specific learner
    if user_role == 'learner' and learner.user.user != request.user:
        messages.warning(request, 'You are not authorized to view these documents.')
        return redirect('qualifications:learner_view', qualification_id=qualification_id)
    
    # Prepare documents with uploader role
    documents_with_roles = []
    for doc in documents:
        uploader_role = 'Unknown'
        uploader_business = UserBusiness.objects.filter(user=doc.uploaded_by, business=business).first()
        if uploader_business:
            if Assessor.objects.filter(user=uploader_business, qualification=qualification).exists():
                uploader_role = 'Assessor'
            elif IQA.objects.filter(user=uploader_business, qualification=qualification).exists():
                uploader_role = 'IQA'
            elif EQA.objects.filter(user=uploader_business, qualification=qualification).exists():
                uploader_role = 'EQA'
            elif uploader_business.user_type == 'admin':
                uploader_role = 'Admin'
        documents_with_roles.append({
            'id': doc.id,
            'title': doc.title,
            'description': doc.description,
            'file': doc.file,
            'uploaded_by': doc.uploaded_by,
            'uploaded_by_name': doc.uploaded_by.full_name or doc.uploaded_by.email,
            'uploader_role': uploader_role,
            'uploaded_at': doc.uploaded_at,
        })
    
    if request.method == 'POST':
        # Only allow non-EQA and non-learner users to upload files
        if user_role in ['eqa', 'learner']:
            messages.warning(request, 'You are not authorized to upload documents.')
            return redirect('qualifications:learner_specific_docs', qualification_id=qualification_id, learner_id=learner_id)
        form = LearnerDocsByAssessorForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.learner = learner
            doc.uploaded_by = request.user
            doc.save()
            messages.success(request, 'File uploaded successfully.')
            return redirect('qualifications:learner_specific_docs', qualification_id=qualification_id, learner_id=learner_id)
        else:
            messages.error(request, 'Error uploading file. Please check the form.')
    else:
        form = LearnerDocsByAssessorForm()
    
    context = {
        'qualification': qualification,
        'learner': learner,
        'learner_name': learner.user.user.full_name or learner.user.user.email,
        'business': business,
        'full_name': request.user.full_name or request.user.email,
        'form': form,
        'documents': documents_with_roles,
        'user_role': user_role,
    }
    
    # Render read-only template for EQAs and learners, full template for others
    if user_role in ['eqa', 'learner']:
        return render(request, 'learner_specific_docs_read_only.html', context)
    return render(request, 'learner_specific_docs_by_assessor.html', context)

@login_required
def edit_learner_doc(request, qualification_id: uuid.UUID, learner_id: uuid.UUID, doc_id: uuid.UUID):
    qualification = get_object_or_404(Qual, id=qualification_id)
    learner = get_object_or_404(Learner, id=learner_id)
    doc = get_object_or_404(LearnerDocsByAssessor, id=doc_id, learner=learner)
    
    # Restrict access to the user who uploaded the document
    if request.user != doc.uploaded_by:
        messages.warning(request, 'You are not authorized to edit this document.')
        return redirect('qualifications:learner_specific_docs', qualification_id=qualification_id, learner_id=learner_id)
    
    if request.method == 'POST':
        form = LearnerDocsByAssessorForm(request.POST, request.FILES, instance=doc)
        if form.is_valid():
            form.save()
            messages.success(request, 'File updated successfully.')
            return redirect('qualifications:learner_specific_docs', qualification_id=qualification_id, learner_id=learner_id)
        else:
            messages.error(request, 'Error updating file. Please check the form.')
    else:
        form = LearnerDocsByAssessorForm(instance=doc)
    
    context = {
        'qualification': qualification,
        'learner': learner,
        'learner_name': learner.user.user.full_name or learner.user.user.email,
        'business': learner.user.business,
        'full_name': request.user.full_name or request.user.email,
        'form': form,
        'doc': doc,
    }
    return render(request, 'edit_learner_doc.html', context)

@login_required
def delete_learner_doc(request, qualification_id: uuid.UUID, learner_id: uuid.UUID, doc_id: uuid.UUID):
    qualification = get_object_or_404(Qual, id=qualification_id)
    learner = get_object_or_404(Learner, id=learner_id)
    doc = get_object_or_404(LearnerDocsByAssessor, id=doc_id, learner=learner)
    
    # Restrict access to the user who uploaded the document
    if request.user != doc.uploaded_by:
        messages.warning(request, 'You are not authorized to delete this document.')
        return redirect('qualifications:learner_specific_docs', qualification_id=qualification_id, learner_id=learner_id)
    
    if request.method == 'POST':
        doc.delete()
        messages.success(request, 'File deleted successfully.')
        return redirect('qualifications:learner_specific_docs', qualification_id=qualification_id, learner_id=learner_id)
    
    return redirect('qualifications:learner_specific_docs', qualification_id=qualification_id, learner_id=learner_id)

@login_required
def learner_resources_view(request, qualification_id):
    """
    Displays resource folders and files for a Learner, filtered by the Learner's role and qualification.
    Only shows folders where the role 'LEARNER' is in visible_to_roles and the qualification is associated.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    try:
        learner = Learner.objects.get(
            user=user_business,
            qualification__id=qualification_id,
            is_active=True
        )
        qualification = learner.qualification
    except Learner.DoesNotExist:
        raise Http404("You are not a learner for this qualification.")

    # Fetch folders that are visible to Learners, associated with the qualification, and belong to the business
    folders = ResourceFolder.objects.filter(
        business=business,
        visible_to_roles__contains=['LEARNER'],
        qualifications=qualification
    ).prefetch_related('files')

    context = {
        'qualification': qualification,
        'business': business,
        'folders': folders,
        'role': 'learner',
    }

    return render(request, 'learner_resources.html', context)

@login_required
def assessor_resources_view(request, qualification_id):
    """
    Displays resource folders and files for an Assessor, filtered by the Assessor's role and qualification.
    Only shows folders where the role 'ASSESSOR' is in visible_to_roles and the qualification is associated.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    try:
        assessor = Assessor.objects.get(
            user=user_business,
            qualification__id=qualification_id
        )
        qualification = assessor.qualification
    except Assessor.DoesNotExist:
        raise Http404("You are not an assessor for this qualification.")

    # Fetch folders that are visible to Assessors, associated with the qualification, and belong to the business
    folders = ResourceFolder.objects.filter(
        business=business,
        visible_to_roles__contains=['ASSESSOR'],
        qualifications=qualification
    ).prefetch_related('files')

    context = {
        'qualification': qualification,
        'business': business,
        'folders': folders,
        'role': 'assessor',
    }

    return render(request, 'learner_resources.html', context)

@login_required
def iqa_resources_view(request, qualification_id):
    """
    Displays resource folders and files for an IQA, filtered by the IQA's role and qualification.
    Only shows folders where the role 'IQA' is in visible_to_roles and the qualification is associated.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    try:
        iqa = IQA.objects.get(
            user=user_business,
            qualification__id=qualification_id
        )
        qualification = iqa.qualification
    except IQA.DoesNotExist:
        raise Http404("You are not an IQA for this qualification.")

    # Fetch folders that are visible to IQAs, associated with the qualification, and belong to the business
    folders = ResourceFolder.objects.filter(
        business=business,
        visible_to_roles__contains=['IQA'],
        qualifications=qualification
    ).prefetch_related('files')

    context = {
        'qualification': qualification,
        'business': business,
        'folders': folders,
        'role': 'iqa',
    }

    return render(request, 'learner_resources.html', context)

@login_required
def eqa_resources_view(request, qualification_id):
    """
    Displays resource folders and files for an EQA, filtered by the EQA's role and qualification.
    Only shows folders where the role 'EQA' is in visible_to_roles and the qualification is associated.
    Admins can also access this view.
    """
    business_id = request.session.get('business_id')
    if not business_id:
        raise Http404("No business selected. Please log in again.")

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = user_business.business
    except UserBusiness.DoesNotExist:
        raise Http404("You are not associated with this business.")

    is_admin = user_business.user_type == 'admin'
    is_eqa = EQA.objects.filter(
        user=user_business,
        qualification__id=qualification_id
    ).exists()

    if not (is_eqa or is_admin):
        raise Http404("You are not an EQA or admin for this qualification.")

    try:
        qualification = Qual.objects.get(id=qualification_id)
    except Qual.DoesNotExist:
        raise Http404("Qualification does not exist.")

    # Fetch folders that are visible to EQAs, associated with the qualification, and belong to the business
    folders = ResourceFolder.objects.filter(
        business=business,
        visible_to_roles__contains=['EQA'],
        qualifications=qualification
    ).prefetch_related('files')

    context = {
        'qualification': qualification,
        'business': business,
        'folders': folders,
        'role': 'eqa',
    }

    return render(request, 'learner_resources.html', context)


def get_user_business(request):
    business_id = request.session.get('business_id')
    if not business_id:
        logger.error("Business ID not found in session")
        messages.error(request, "Business ID not found in session.")
        return None, None, redirect('login')
    
    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = Business.objects.get(business_id=business_id)
        return user_business, business, None
    except UserBusiness.DoesNotExist:
        logger.error(f"UserBusiness not found for user {request.user.email} and business {business_id}")
        messages.error(request, "You are not authorized to access messages.")
        return None, None, redirect('login')
    except UserBusiness.MultipleObjectsReturned:
        user_business = UserBusiness.objects.filter(user=request.user, business__business_id=business_id).first()
        if not user_business:
            logger.error(f"No valid UserBusiness found for user {request.user.email} and business {business_id}")
            messages.error(request, "You are not authorized to access messages for this business.")
            return None, None, redirect('login')
        business = Business.objects.get(business_id=business_id)
        return user_business, business, None

def process_threads(messages, user_business):
    threads = {}
    for message in messages:
        subject = message.subject
        if subject not in threads:
            threads[subject] = {
                'latest_message': message,
                'unread_count': MessageRecipient.objects.filter(
                    message__subject=subject,
                    recipient=user_business,
                    is_read=False
                ).count() if user_business in message.recipients.all() else 0
            }
    return threads

@login_required
def inbox_view(request):
    if request.method == 'POST':
        logger.warning(f"Unexpected POST request to inbox by user {request.user.email}")
        messages.error(request, "Invalid request method.")
        return redirect('qualifications:inbox')

    user_business, business, redirect_response = get_user_business(request)
    if redirect_response:
        return redirect_response

    received_messages = Message.objects.filter(
        recipients__recipient=user_business
    ).prefetch_related('recipients').distinct().order_by('-sent_at')
    logger.debug(f"Received messages count for user {user_business.user.email}: {received_messages.count()}")

    threads = process_threads(received_messages, user_business)
    logger.debug(f"Threads created: {len(threads)}")

    unread_count = MessageRecipient.objects.filter(
        recipient=user_business,
        is_read=False
    ).count()
    logger.debug(f"Unread messages count: {unread_count}")

    is_admin = user_business.user_type == 'admin'

    return render(request, 'inbox.html', {
        'threads': threads,
        'user_business': user_business,
        'full_name': user_business.user.full_name or request.user.email,
        'unread_count': unread_count,
        'business_id': business.business_id,
        'is_admin': is_admin,
        'debug_messages': {
            'received_count': received_messages.count(),
            'thread_count': len(threads)
        }
    })

@login_required
def sent_messages_view(request):
    if request.method == 'POST':
        logger.warning(f"Unexpected POST request to sent messages by user {request.user.email}")
        messages.error(request, "Invalid request method.")
        return redirect('qualifications:sent_messages')

    user_business, business, redirect_response = get_user_business(request)
    if redirect_response:
        return redirect_response

    sent_messages = Message.objects.filter(
        sender=user_business
    ).prefetch_related('recipients').distinct().order_by('-sent_at')
    logger.debug(f"Sent messages count for user {user_business.user.email}: {sent_messages.count()}")

    threads = process_threads(sent_messages, user_business)
    logger.debug(f"Threads created: {len(threads)}")

    unread_count = MessageRecipient.objects.filter(
        recipient=user_business,
        is_read=False
    ).count()
    logger.debug(f"Unread messages count: {unread_count}")

    is_admin = user_business.user_type == 'admin'

    return render(request, 'sent_messages.html', {
        'threads': threads,
        'user_business': user_business,
        'full_name': user_business.user.full_name or request.user.email,
        'unread_count': unread_count,
        'business_id': business.business_id,
        'is_admin': is_admin,
        'debug_messages': {
            'sent_count': sent_messages.count(),
            'thread_count': len(threads)
        }
    })


@login_required
def compose_message_view(request):
    try:
        business_id = request.session.get('business_id')
        logger.debug(f"Session business_id: {business_id}")
        if not business_id:
            messages.error(request, "Business ID not found in session.")
            return redirect('login')
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        business = Business.objects.get(business_id=business_id)
    except Exception as e:
        messages.error(request, f"You are not authorized to send messages. Error: {str(e)}")
        return redirect('login')

    is_eqa = EQA.objects.filter(user=user_business).exists()
    is_reply = request.GET.get('reply', '') == 'true'
    reply_subject = request.GET.get('subject', '')

# NEW: Fetch subject from message if thread_id is passed
    thread_id = request.GET.get('thread_id')
    if thread_id and not reply_subject:
        main_message = Message.objects.filter(id=thread_id).first()
        if main_message:
            reply_subject = main_message.subject
    reply_recipient_ids = request.GET.getlist('recipient')
    reply_qualification_id = request.GET.get('qualification')

    reply_recipients = None
    reply_qualification = None
    qualification_queryset = None

    if is_reply and reply_qualification_id:
        reply_qualification = Qual.objects.filter(id=reply_qualification_id, business=business).first()
        if reply_qualification:
            qualification_queryset = Qual.objects.filter(id=reply_qualification.id)
            logger.debug(f"Reply qualification: {reply_qualification.qualification_title}")
        if reply_recipient_ids:
            reply_recipients = UserBusiness.objects.filter(id__in=reply_recipient_ids)
            logger.debug(f"Reply recipients: {[r.user.full_name or r.user.email for r in reply_recipients]}")
    else:
        if user_business.user_type != 'admin':
            learner_qual_ids = Learner.objects.filter(user=user_business, qualification__business=business).values_list('qualification__id', flat=True)
            assessor_qual_ids = Assessor.objects.filter(user=user_business, qualification__business=business).values_list('qualification__id', flat=True)
            iqa_qual_ids = IQA.objects.filter(user=user_business, qualification__business=business).values_list('qualification__id', flat=True)
            eqa_qual_ids = EQA.objects.filter(user=user_business, qualification__business=business).values_list('qualification__id', flat=True)
            qual_ids = set(learner_qual_ids) | set(assessor_qual_ids) | set(iqa_qual_ids) | set(eqa_qual_ids)
            qualification_queryset = Qual.objects.filter(id__in=qual_ids, business=business)
        else:
            qualification_queryset = Qual.objects.filter(business=business)
        logger.debug(f"Qualification queryset count: {qualification_queryset.count() if qualification_queryset else 0}")

    if request.method == 'POST':
        form = MessageForm(
            request.POST,
            request.FILES,
            user_business=user_business,
            business=business,
            is_reply=is_reply,
            reply_subject=reply_subject,
            reply_recipients=reply_recipients,
            reply_qualification=reply_qualification,
            qualification_queryset=qualification_queryset
        )
        logger.debug(f"Form data: {request.POST}")
        if form.is_valid():
            logger.debug("Form is valid")
            message = Message.objects.create(
                sender=user_business,
                subject=form.cleaned_data['subject'],
                body=form.cleaned_data['body'],
                attachment=form.cleaned_data['attachment'],
                qualification=form.cleaned_data['qualification'] or reply_qualification
            )
            recipients = form.cleaned_data['recipients']
            for recipient in recipients:
                MessageRecipient.objects.create(
                    message=message,
                    recipient=recipient
                )
                # Send email notification to recipient
                try:
                    # Determine sender's role based on qualification
                    sender_role = "Admin" if user_business.user_type == 'admin' else "User"
                    if message.qualification:
                        if Learner.objects.filter(user=user_business, qualification=message.qualification).exists():
                            sender_role = "Learner"
                        elif Assessor.objects.filter(user=user_business, qualification=message.qualification).exists():
                            sender_role = "Assessor"
                        elif IQA.objects.filter(user=user_business, qualification=message.qualification).exists():
                            sender_role = "IQA"
                        elif EQA.objects.filter(user=user_business, qualification=message.qualification).exists():
                            sender_role = "EQA"
                    
                    send_message_notification_email(
                        recipient_email=recipient.user.email,
                        recipient_name=recipient.user.full_name or recipient.user.email,
                        sender_name=user_business.user.full_name or user_business.user.email,
                        sender_role=sender_role,
                        business_name=business.name,
                        message_subject=message.subject,
                        message_sent_at=message.sent_at or timezone.now(),
                        fail_silently=True  # Avoid breaking message sending if email fails
                    )
                    logger.debug(f"Sent notification email to {recipient.user.email}")
                except Exception as e:
                    logger.error(f"Failed to send notification email to {recipient.user.email}: {str(e)}")
            
            messages.success(request, "Message sent successfully.")
            return redirect('qualifications:inbox')
        else:
            logger.debug(f"Form errors: {form.errors}")
            messages.error(request, "Failed to send message. Please check the form.")
    else:
        form = MessageForm(
            user_business=user_business,
            business=business,
            is_reply=is_reply,
            reply_subject=reply_subject,
            reply_recipients=reply_recipients,
            reply_qualification=reply_qualification,
            qualification_queryset=qualification_queryset
        )

    return render(request, 'compose_message.html', {
        'form': form,
        'full_name': user_business.user.full_name or request.user.email,
        'business_id': business_id,
        'is_reply': is_reply,
        'is_eqa': is_eqa,
        'reply_qualification': reply_qualification
    })


@login_required
def message_thread_view(request, thread_id):
    try:
        user_business = UserBusiness.objects.get(
            user=request.user,
            business__business_id=request.session.get('business_id')
        )
        business_id = request.session.get('business_id')
        if not business_id:
            messages.error(request, "Business ID not found in session.")
            return redirect('login')
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to view messages.")
        return redirect('login')

    # Step 1: Get the message using thread_id
    main_message = get_object_or_404(Message, id=thread_id)

    # Step 2: Use the subject to fetch the whole thread
    messages_query = Message.objects.filter(
        subject=main_message.subject
    ).filter(
        Q(sender=user_business) | Q(recipients__recipient=user_business)
    ).prefetch_related('recipients').distinct().order_by('sent_at')


    if not messages_query.exists():
        messages.error(request, "Message thread not found.")
        return redirect('qualifications:inbox')

    # Step 3: Mark all messages in thread as read for this user
    MessageRecipient.objects.filter(
        message__subject=main_message.subject,
        recipient=user_business,
        is_read=False
    ).update(is_read=True, read_at=timezone.now())

    unread_count = MessageRecipient.objects.filter(
        recipient=user_business,
        is_read=False
    ).count()

    return render(request, 'message_thread.html', {
        'messages': messages_query,
        'subject': main_message.subject,  # display subject
        'user_business': user_business,
        'full_name': user_business.user.full_name or request.user.email,
        'unread_count': unread_count,
        'business_id': business_id,
        'last_message': messages_query.last()
    })


@login_required
def mark_message_read_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message_id = data.get('message_id')
            user_business = UserBusiness.objects.get(user=request.user)
            recipient = MessageRecipient.objects.filter(
                message_id=message_id,
                recipient=user_business,
                is_read=False
            ).first()
            if recipient:
                recipient.is_read = True
                recipient.read_at = timezone.now()
                recipient.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
        

@login_required
def get_recipients_by_qualification(request):
    qualification_id = request.GET.get('qualification')
    try:
        user_business, business, redirect_response = get_user_business(request)
        if redirect_response:
            logger.error("Redirect response triggered due to invalid session or user business")
            return JsonResponse({'error': 'Business ID not found in session'}, status=403)
        logger.debug(f"User: {user_business.user.full_name or user_business.user.email}, Business: {business.business_id}, Qualification: {qualification_id}")

        if not qualification_id:
            logger.debug("No qualification ID provided")
            return JsonResponse({'recipients': []})

        # Verify qualification exists
        try:
            qualification = Qual.objects.get(id=qualification_id, business=business)
            logger.debug(f"Qualification found: {qualification.qualification_title}")
        except Qual.DoesNotExist:
            logger.error(f"Qualification {qualification_id} not found for business {business.business_id}")
            return JsonResponse({'error': 'Qualification not found'}, status=404)

        recipients = []
        if user_business.user_type == 'admin':
            # Admins see all learners, assessors, IQAs, and EQAs
            assessors = UserBusiness.objects.filter(
                assessor_assignments__qualification_id=qualification_id,
                business=business
            ).distinct()
            learners = UserBusiness.objects.filter(
                learner_assignments__qualification_id=qualification_id,
                business=business
            ).distinct()
            iqas = UserBusiness.objects.filter(
                iqa_assignments__qualification_id=qualification_id,
                business=business
            ).distinct()
            eqas = UserBusiness.objects.filter(
                eqa_assignments__qualification_id=qualification_id,
                business=business
            ).distinct()
            recipients = list(assessors) + list(learners) + list(iqas) + list(eqas)
            recipients = [r for r in recipients if r.id != user_business.id]
            logger.debug(f"Admin recipients - Assessors: {assessors.count()}, Learners: {learners.count()}, IQAs: {iqas.count()}, EQAs: {eqas.count()}")
        elif EQA.objects.filter(user=user_business, qualification_id=qualification_id).exists():
            # EQAs only see admin users
            recipients = list(UserBusiness.objects.filter(
                user_type='admin',
                business=business
            ).distinct())
            logger.debug(f"EQA recipients - Admins: {len(recipients)}")
        elif IQA.objects.filter(user=user_business, qualification_id=qualification_id).exists():
            # IQAs see assigned learners, their assessors, and admins
            learners = UserBusiness.objects.filter(
                learner_assignments__qualification_id=qualification_id,
                learner_assignments__iqa=user_business,
                business=business
            ).distinct()
            learner_ids = Learner.objects.filter(
                qualification_id=qualification_id,
                iqa=user_business,
                user__business=business,
                assessor__isnull=False
            ).values_list('assessor__id', flat=True).distinct()
            assessors = UserBusiness.objects.filter(
                id__in=learner_ids,
                business=business
            ).distinct()
            admins = UserBusiness.objects.filter(
                user_type='admin',
                business=business
            ).distinct()
            recipients = list(learners) + list(assessors) + list(admins)
            logger.debug(f"IQA recipients - Learners: {learners.count()}, Assessors: {assessors.count()}, Admins: {admins.count()}")
        elif Learner.objects.filter(user=user_business, qualification_id=qualification_id).exists():
            # Learners see their assigned assessor and admins
            learner = Learner.objects.get(user=user_business, qualification_id=qualification_id)
            recipients = []
            if learner.assessor:
                recipients.append(learner.assessor)
            else:
                logger.warning(f"No assessor assigned to learner {user_business.user.email} for qualification {qualification_id}")
            if learner.iqa:
                recipients.append(learner.iqa)
            else:
                logger.warning(f"No IQA assigned to learner {user_business.user.email} for qualification {qualification_id}")
            admins = UserBusiness.objects.filter(
                user_type='admin',
                business=business
            ).distinct()
            recipients.extend(admins)
            logger.debug(f"Learner recipients - Assessor: {1 if learner.assessor else 0}, IQA: {1 if learner.iqa else 0}, Admins: {admins.count()}")
        elif Assessor.objects.filter(user=user_business, qualification_id=qualification_id).exists():
            # Assessors see assigned learners, their IQAs, and admins
            learners = UserBusiness.objects.filter(
                learner_assignments__assessor=user_business,
                learner_assignments__qualification_id=qualification_id,
                business=business
            ).distinct()
            learner_ids = Learner.objects.filter(
                qualification_id=qualification_id,
                assessor=user_business,
                user__business=business,
                iqa__isnull=False
            ).values_list('iqa__id', flat=True).distinct()
            iqas = UserBusiness.objects.filter(
                id__in=learner_ids,
                business=business
            ).distinct()
            admins = UserBusiness.objects.filter(
                user_type='admin',
                business=business
            ).distinct()
            recipients = list(learners) + list(iqas) + list(admins)
            logger.debug(f"Assessor recipients - Learners: {learners.count()}, IQAs: {iqas.count()}, Admins: {admins.count()}")

        recipient_data = [
            {
                'id': str(r.id),
                'name': r.user.full_name or r.user.email,
                'role': (
                    "Admin" if r.user_type == 'admin' else
                    "Learner" if Learner.objects.filter(user=r, qualification_id=qualification_id).exists() else
                    "Assessor" if Assessor.objects.filter(user=r, qualification_id=qualification_id).exists() else
                    "IQA" if IQA.objects.filter(user=r, qualification_id=qualification_id).exists() else
                    "EQA" if EQA.objects.filter(user=r, qualification_id=qualification_id).exists() else
                    "User"
                )
            } for r in recipients
        ]
        logger.debug(f"Final recipients count: {len(recipient_data)}")
        if not recipient_data:
            logger.warning(f"No recipients found for user {user_business.user.email} with role {user_business.user_type} for qualification {qualification_id}")
        return JsonResponse({'recipients': recipient_data})

    except (UserBusiness.DoesNotExist, Business.DoesNotExist) as e:
        logger.error(f"User or business not found: {str(e)}")
        return JsonResponse({'error': 'User or business not found'}, status=403)
    except Exception as e:
        logger.error(f"Error in get_recipients_by_qualification: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'error': f'Failed to load recipients: {str(e)}'}, status=500)
    
def user_context(request):
    context = {
        'full_name': '',
        'business': None,
        'unread_count': 0,
    }
    
    if request.user.is_authenticated and not isinstance(request.user, AnonymousUser):
        context['full_name'] = request.user.full_name or request.user.email
        business_id = request.session.get('business_id')
        if business_id:
            try:
                user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
                context['business'] = user_business.business
                context['unread_count'] = MessageRecipient.objects.filter(
                    recipient=user_business,
                    is_read=False,
                    message__recipients__recipient__business__business_id=business_id
                ).count()
            except UserBusiness.DoesNotExist:
                pass
    
    return context