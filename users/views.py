from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, get_user_model
from .forms import LoginForm, CreateUserForm, ForgotPasswordForm, PasswordResetForm, SetNewPasswordForm, BusinessLogoForm, ContactForm
from .models import Business, CustomUser, UserBusiness, Record
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMessage
from django.utils.crypto import get_random_string
from django.conf import settings
from datetime import datetime, timedelta
from django.contrib.auth.password_validation import validate_password
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib import messages
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from email.mime.image import MIMEImage
from django.http import JsonResponse
import os
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from django.contrib.auth import logout
from qualifications.models import Learner, Assessor, IQA, EQA  # Added imports
from django.utils import timezone
from django.contrib.postgres.aggregates import StringAgg
from qualifications.models import Learner, Qual, AC, EvidenceSubmission, MessageRecipient
from AssessEEZ.email_utils import send_welcome_email
import logging
from django.contrib.auth.decorators import user_passes_test
from django import forms
from django.db.models import Q
from django.core.mail import send_mail
import requests

logger = logging.getLogger(__name__)
User = get_user_model()


def forgot_password_view(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            logger.debug(f"Debug - Input: email={email}")
            try:
                user = CustomUser.objects.get(email=email)
                logger.debug(f"Debug - User: {user}, is_superuser={user.is_superuser}")
                uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                
                business_name = 'AssessEEZ Account' if not user.is_superuser else 'Super-Admin Account'
                business_id = 'N/A'
                
                logger.info(f"Debug - Before generating redirect URL: business_id={business_id}, business_name={business_name}")
                redirect_url = request.build_absolute_uri(
                    reverse('users:password_reset_redirect', kwargs={'uidb64': uidb64, 'token': token})
                )
                send_reset_password_email(email, redirect_url, business_id, business_name)
                return render(request, 'forgot_password.html', {'success_message': 'Password reset link has been sent to your email.'})
            except CustomUser.DoesNotExist:
                logger.error("Debug - CustomUser does not exist")
                return render(request, 'forgot_password.html', {'error_message': 'Invalid email address.'})
            except Exception as e:
                logger.error(f"Debug - Unexpected error: {str(e)}")
                return render(request, 'forgot_password.html', {'error_message': 'An error occurred while processing your request.'})
    else:
        form = ForgotPasswordForm()
    return render(request, 'forgot_password.html', {'form': form})

def send_reset_password_email(user_email, reset_link, business_id=None, business_name=None):
    subject = 'Password Reset Request'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user_email]

    business_id = business_id if business_id is not None else 'N/A'
    business_name = business_name if business_name is not None else 'AssessEEZ Account'

    logger.debug(f"Context for email: user_email={user_email}, business_id={business_id}, business_name={business_name}")

    try:
        html_message = render_to_string('password_reset_email.html', {
            'user': CustomUser.objects.get(email=user_email),
            'redirect_url': reset_link,
            'business_id': business_id,
            'business_name': business_name,
        })
    except TemplateDoesNotExist as e:
        logger.error(f"Template error: Template 'password_reset_email.html' not found - {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Template rendering error: {str(e)}")
        raise

    message = f'Hello,\n\nYou have requested a password reset for your {business_name} account. Click the link below to reset your password:\n{reset_link}\n\nIf you didn\'t request this, please ignore this email.\n\nBest regards,\nAssessEEZ Team'

    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=from_email,
        to=recipient_list,
    )
    email.content_subtype = 'html'
    email.body = html_message

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'assesseez_logo.png')
    logger.debug(f"Attempting to attach logo from: {logo_path}")
    try:
        with open(logo_path, 'rb') as f:
            logo_data = f.read()
        logo = MIMEImage(logo_data)
        logo.add_header('Content-ID', '<assesseez_logo>')
        logo.add_header('Content-Disposition', 'inline', filename='assesseez_logo.png')
        email.attach(logo)
    except FileNotFoundError as e:
        logger.error(f"Logo file not found at {logo_path}: {str(e)}")

    try:
        result = email.send(fail_silently=False)
        logger.info(f"Password reset email sent to {user_email}: {result}")
    except Exception as e:
        logger.error(f"Password reset email failed: {str(e)}")
        raise
def reset_password_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
        
        if default_token_generator.check_token(user, token):
            if request.method == 'POST':
                form = SetNewPasswordForm(request.POST)
                logger.info("POST request received")
                logger.info(request.POST)
                if form.is_valid():
                    logger.info("Form is valid")
                    new_password = form.cleaned_data['new_password']
                    user.set_password(new_password)
                    user.save()
                    logger.info("User password updated")
                    
                    # Update password for all UserBusiness entries
                    if not user.is_superuser:
                        user_businesses = UserBusiness.objects.filter(user=user)
                        for user_business in user_businesses:
                            user_business.password = make_password(new_password)
                            user_business.save()
                            logger.info(f"UserBusiness password updated for business {user_business.business.business_id}")
                    
                    try:
                        send_mail(
                            'Password Reset Successful',
                            'Your password has been reset successfully.',
                            settings.DEFAULT_FROM_EMAIL,
                            [user.email],
                            fail_silently=False,
                        )
                    except Exception as e:
                        logger.error(f"Failed to send confirmation email: {str(e)}")
                    
                    logger.debug("Redirecting to login with success message")
                    messages.success(request, "Your password has been reset successfully.")
                    return redirect('login')
                else:
                    logger.error(f"Form invalid: {form.errors}")
            else:
                form = SetNewPasswordForm()
                logger.info("GET request - Form initialized")
            
            logger.debug(f"Rendering form with context: form={form}, uidb64={uidb64}, token={token}")
            return render(request, 'reset_password.html', {
                'form': form,
                'uidb64': uidb64,
                'token': token
            })
        else:
            logger.error("Invalid or expired token")
            return render(request, 'invalid_token.html', {'error_message': 'The password reset token is invalid or has expired.'})
    except CustomUser.DoesNotExist:
        logger.error("User does not exist")
        return render(request, 'invalid_token.html', {'error_message': 'User does not exist.'})
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return render(request, 'invalid_token.html', {'error_message': 'An unexpected error occurred.'})

def password_reset_redirect(request, uidb64, token):
    reset_url = reverse('users:reset_password', kwargs={
        'uidb64': uidb64,
        'token': token
    })
    return redirect(reset_url)

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)
            if user:
                login(request, user)
                request.session['business_id'] = None  # Clear business_id; user selects later
                if user.is_superuser:
                    return redirect('users:superadmin')
                else:
                    return redirect('users:main_page')
            else:
                form.add_error(None, 'Invalid login credentials')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})




@login_required
def main_page(request):
    if request.user.is_superuser:
        return redirect('users:superadmin')
    
    # Fetch all businesses associated with the user
    user_businesses = UserBusiness.objects.filter(user=request.user).select_related('business')
    businesses = [
        {
            'business_id': ub.business.business_id,
            'name': ub.business.name,
            'user_type': ub.user_type
        } for ub in user_businesses
    ]
    
    return render(request, 'main_page.html', {
        'businesses': businesses,
        'full_name': request.user.full_name or request.user.email
    })
@login_required
def select_business(request):
    if request.method == 'POST':
        business_id = request.POST.get('business_id')
        try:
            user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
            request.session['business_id'] = business_id
            if user_business.user_type == 'admin':
                return redirect('users:admin_dashboard')
            else:
                return redirect('qualifications:user_dashboard')
        except UserBusiness.DoesNotExist:
            messages.error(request, "You are not associated with this business.")
            return redirect('users:main_page')
    return redirect('users:main_page')


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

@login_required
def admin_dashboard(request):
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

    learners = Learner.objects.filter(
        user__business=business,
        is_active=True
    ).select_related('user__user', 'qualification', 'assessor__user', 'iqa__user')

    learner_data = []
    for learner in learners:
        total_ac = AC.objects.filter(learning_outcome__unit__qualification=learner.qualification).count()
        accepted_ac = EvidenceSubmission.objects.filter(
            user=learner.user,
            assessment_criterion__learning_outcome__unit__qualification=learner.qualification,
            status='ACCEPTED'
        ).count()
        progress = (accepted_ac / total_ac * 100) if total_ac > 0 else 0

        learner_data.append({
            'full_name': learner.user.user.full_name or learner.user.user.email,
            'qualification_title': learner.qualification.qualification_title,
            'qualification_id': str(learner.qualification.id),
            'progress': round(progress, 2),
            'learner_id': str(learner.id),
            'assessor_name': learner.assessor.user.full_name or learner.assessor.user.email if learner.assessor else 'None',
            'iqa_name': learner.iqa.user.full_name or learner.iqa.user.email if learner.iqa else 'None',
            'date_of_registration': learner.date_of_registration.isoformat() if learner.date_of_registration else '',
            'created_at': learner.created_at.isoformat() if learner.created_at else '',
        })

    unread_count = MessageRecipient.objects.filter(
        recipient=user_business,
        is_read=False,
        message__recipients__recipient__business__business_id=business_id
    ).count()

    context = {
        'business': business,
        'learners': learner_data,
        'unread_count': unread_count,
    }

    return render(request, 'admin_dashboard.html', context)

def create_admin_view(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return redirect('login')

    if request.method == 'POST':
        email = request.POST.get('email')
        admin_name = request.POST.get('admin_name')
        business_name = request.POST.get('business_name')
        business_address = request.POST.get('business_address')
        business_website = request.POST.get('business_website', '')

        # Validate required fields
        if not email or not admin_name or not business_name or not business_address:
            messages.error(request, "All fields (email, admin name, business name, address) are required.")
            return render(request, 'createadmin.html')

        # Check if email is already registered
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, f"Email {email} is already registered in AssessEEZ.")
            return render(request, 'createadmin.html')

        # Create new Business instance (no get_or_create)
        business = Business(
            name=business_name,
            address=business_address,
            website=business_website
        )
        business.save()  # Generates new business_id (e.g., AA0003)

        # Check if business already has an admin
        if UserBusiness.objects.filter(business=business, user_type='admin').exists():
            messages.error(request, f"An admin already exists for business {business_name} ({business.business_id}).")
            business.delete()  # Clean up unused Business
            return render(request, 'createadmin.html')

        # Create new CustomUser
        user = CustomUser.objects.create_user(
            email=email,
            full_name=admin_name,
            password=None  # Password set in UserBusiness
        )

        # Create UserBusiness
        random_password = get_random_string(length=12)
        user_business = UserBusiness.objects.create(
            user=user,
            business=business,
            user_type='admin',
            password=make_password(random_password)
        )

        # Assume send_welcome_email is defined elsewhere
        send_welcome_email(email, business.business_id, business.name, random_password, settings.LOGIN_URL, sender_name="AssessEEZ Support Team")
        messages.success(request, f"Admin {email} created for business {business.business_id}.")
        return redirect('users:superadmin')

    # GET request
    return render(request, 'createadmin.html')

def create_user_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    business_id = request.session.get('business_id')
    if not business_id:
        return redirect('login')
    
    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
        if user_business.user_type != 'admin':
            return redirect('login')
    except UserBusiness.DoesNotExist:
        return redirect('login')

    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            full_name = form.cleaned_data['full_name']
            business = Business.objects.get(business_id=business_id)
            if UserBusiness.objects.filter(business=business, user__email=email).exists():
                form.add_error('email', 'This email is already in use for this business.')
            else:
                new_user, _ = CustomUser.objects.get_or_create(email=email, defaults={'full_name': full_name})
                UserBusiness.objects.create(
                    user=new_user,
                    business=business,
                    user_type='user',
                    password=make_password('default123')
                )
                return redirect('users:admin_dashboard')
    else:
        form = CreateUserForm()
    return render(request, 'create_user.html', {'form': form})

def custom_logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('login')  # Updated to use namespaced URL
    return redirect('login')  # Updated to use namespaced URL


@login_required
def business_details(request, business_id):
    if not request.user.is_superuser:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    business = get_object_or_404(Business, business_id=business_id)
    
    # Calculate time ranges
    today = timezone.now()
    start_of_day = today.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Query registrations
    def get_counts(model, is_unique=False):
        base_query = model.objects.filter(qualification__business=business)
        if is_unique:
            # Count unique users by user__user__id
            return {
                'month': base_query.filter(created_at__gte=start_of_month).values('user__user__id').distinct().count(),
                'week': base_query.filter(created_at__gte=start_of_week).values('user__user__id').distinct().count(),
                'day': base_query.filter(created_at__gte=start_of_day).values('user__user__id').distinct().count(),
                'total': base_query.values('user__user__id').distinct().count(),
            }
        else:
            # Count total records
            return {
                'month': base_query.filter(created_at__gte=start_of_month).count(),
                'week': base_query.filter(created_at__gte=start_of_week).count(),
                'day': base_query.filter(created_at__gte=start_of_day).count(),
                'total': base_query.count(),
            }

    registrations = {
        'learners': get_counts(Learner, is_unique=False),
        'assessors': get_counts(Assessor, is_unique=True),
        'iqa': get_counts(IQA, is_unique=True),
        'eqa': get_counts(EQA, is_unique=True),
    }

    context = {
        'business': business,
        'registrations': registrations,
    }
    return render(request, 'business_details.html', context)

@login_required
def admin_users_details(request, business_id, role, period):
    if not request.user.is_superuser:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('login')

    business = get_object_or_404(Business, business_id=business_id)
    today = timezone.now()
    
    # Define time ranges
    if period == 'month':
        start_time = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_time = today - timedelta(days=today.weekday())  # Monday
    elif period == 'day':
        start_time = today.replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # total
        start_time = None

    # Map role to model
    role_models = {
        'learner': Learner,
        'assessor': Assessor,
        'iqa': IQA,
        'eqa': EQA,
    }
    
    model = role_models.get(role)
    if not model:
        messages.error(request, "Invalid role specified.")
        return redirect('users:business_details', business_id=business_id)

    # Query users
    queryset = model.objects.filter(qualification__business=business)
    if start_time:
        queryset = queryset.filter(created_at__gte=start_time)
    
    # For Assessors, IQA, and EQA, deduplicate in Python; for Learners, keep all entries
    if role in ['assessor', 'iqa', 'eqa']:
        # Fetch all records and deduplicate in Python
        users = queryset.values(
            'user__user__id',
            'user__user__full_name',
            'user__user__email',
            'created_at',
            'qualification__qualification_title'
        ).order_by('user__user__id', '-created_at')
        # Deduplicate by user ID, keeping the latest created_at
        seen_users = {}
        for user in users:
            user_id = user['user__user__id']
            if user_id not in seen_users or user['created_at'] > seen_users[user_id]['created_at']:
                seen_users[user_id] = {
                    'user__user__full_name': user['user__user__full_name'],
                    'user__user__email': user['user__user__email'],
                    'created_at': user['created_at'],
                    'qualifications': [user['qualification__qualification_title']]
                }
            else:
                seen_users[user_id]['qualifications'].append(user['qualification__qualification_title'])
        # Sort users by created_at in descending order
        users = [
            {
                'name': data['user__user__full_name'],
                'email': data['user__user__email'],
                'created_at': data['created_at'],
                'qualification_title': ', '.join(set(data['qualifications']))  # Comma-separated for splitting in template
            } for data in sorted(seen_users.values(), key=lambda x: x['created_at'], reverse=True)
        ]
    else:
        users = queryset.order_by('-created_at').values(
            'user__user__full_name',
            'user__user__email',
            'created_at',
            'qualification__qualification_title'
        )
        # Rename keys for template compatibility
        users = [
            {
                'name': user['user__user__full_name'],
                'email': user['user__user__email'],
                'created_at': user['created_at'],
                'qualification_title': user['qualification__qualification_title']
            } for user in users
        ]

    context = {
        'business': business,
        'role': role,
        'period': period,
        'users': users,
    }
    return render(request, 'admin_users_details.html', context)


@login_required
def add_logo_view(request):
    business_id = request.session.get('business_id')
    if not business_id:
        return redirect('login')

    try:
        user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id, user_type='admin')
        business = user_business.business
    except UserBusiness.DoesNotExist:
        messages.error(request, "You are not authorized to upload a logo.")
        return redirect('users:admin_dashboard')

    if request.method == 'POST':
        form = BusinessLogoForm(request.POST, request.FILES, instance=business)
        if form.is_valid():
            form.save()
            messages.success(request, "Logo uploaded successfully.")
            return redirect('users:admin_dashboard')
        else:
            messages.error(request, "Error uploading logo. Please check the form.")
    else:
        form = BusinessLogoForm(instance=business)

    return render(request, 'add_logo.html', {
        'form': form,
        'business': business,
    })


class AssignQualificationForm(forms.Form):
    businesses = forms.ModelMultipleChoiceField(
        queryset=Business.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Select Businesses"
    )

# Check if user is superuser
def is_superuser(user):
    return user.is_superuser

def superadmin_view(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return redirect('login')
    
    businesses = Business.objects.all()
    businesses_with_admin = []
    for business in businesses:
        try:
            admin_user_business = UserBusiness.objects.get(business=business, user_type='admin')
            admin_user = admin_user_business.user
            businesses_with_admin.append({
                'business': business,
                'admin_name': admin_user.full_name,
                'admin_email': admin_user.email
            })
        except UserBusiness.DoesNotExist:
            businesses_with_admin.append({
                'business': business,
                'admin_name': 'No admin assigned',
                'admin_email': 'N/A'
            })
    return render(request, 'superadmin_login.html', {'businesses_with_admin': businesses_with_admin})


@user_passes_test(is_superuser)
def superadmin_qualifications_dashboard(request):
    """
    Display distinct qualifications with a search option.
    """
    form = QualificationSearchForm(request.GET or None)
    qualifications = Qual.objects.select_related('business').all()

    # Apply search filter if query exists
    if form.is_valid() and form.cleaned_data['query']:
        query = form.cleaned_data['query']
        qualifications = qualifications.filter(
            Q(qualification_title__icontains=query) |
            Q(qualification_number__icontains=query) |
            Q(awarding_body__icontains=query)
        )

    # Get distinct qualifications by qualification_number
    seen_numbers = set()
    distinct_qualifications = []
    for qual in qualifications.order_by('qualification_number', 'created_at'):
        if qual.qualification_number not in seen_numbers:
            seen_numbers.add(qual.qualification_number)
            distinct_qualifications.append(qual)

    return render(request, 'superadmin_qualifications_dashboard.html', {
        'qualifications': distinct_qualifications,
        'form': form
    })

@user_passes_test(is_superuser)
def assign_qualification(request, qual_id):
    qualification = get_object_or_404(Qual, id=qual_id)
    if request.method == 'POST':
        form = AssignQualificationForm(request.POST)
        if form.is_valid():
            selected_businesses = form.cleaned_data['businesses']
            for business in selected_businesses:
                if Qual.objects.filter(
                    qualification_number=qualification.qualification_number,
                    business=business
                ).exists():
                    messages.warning(
                        request,
                        f"Qualification '{qualification.qualification_title}' already exists for business {business.business_id}."
                    )
                    continue
                try:
                    qualification.copy_to_business(business)
                    messages.success(
                        request,
                        f"Qualification '{qualification.qualification_title}' assigned to business {business.business_id}."
                    )
                except Exception as e:
                    messages.error(
                        request,
                        f"Failed to assign qualification to {business.business_id}: {str(e)}"
                    )
            return redirect('users:superadmin_qualifications_dashboard')
    else:
        form = AssignQualificationForm()
    return render(request, 'assign_qualification.html', {
        'qualification': qualification,
        'form': form
    })

class QualificationSearchForm(forms.Form):
    query = forms.CharField(
        max_length=100,
        required=False,
        label="Search Qualifications",
        widget=forms.TextInput(attrs={'placeholder': 'Enter title, number, or awarding body', 'class': 'w-full p-2 border rounded'})
    )

def learner_view(request):
    return render(request, 'learner.html')


def eqa_view(request):
    return render(request, 'eqa.html')

def iqa_view(request):
    return render(request, 'iqa.html')

def administrator_view(request):
    return render(request, 'administrator.html')

def assessor_view(request):
    return render(request, 'assessor.html')

def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            phone = form.cleaned_data['phone']
            purpose = form.cleaned_data['purpose']
            message = form.cleaned_data['message']

            recipient = {
                'general': 'info@assesseez.co.uk',
                'support': 'support@assesseez.co.uk',
                'sales': 'sales@assesseez.co.uk'
            }.get(purpose, 'info@assesseez.co.uk')

            subject = f"Contact Form Submission: {purpose.capitalize()}"
            body = f"""
            Name: {name}
            Email: {email}
            Phone: {phone or 'Not provided'}
            Purpose: {dict(form.fields['purpose'].choices)[purpose]}
            Message: {message}
            """
            try:
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    [recipient],
                    fail_silently=False
                )
                messages.success(request, 'Your message has been sent successfully!')
                return redirect('contact')
            except Exception as e:
                logger.error(f"Email sending failed: {str(e)}")
                messages.error(request, 'An error occurred while sending your message. Please try again later.')
        else:
            logger.debug(f"Form validation failed: {form.errors}")
            messages.error(request, 'Please correct the errors in the form.')
    else:
        form = ContactForm()
    return render(request, 'contact.html', {'form': form})

def pricing_view(request):
    from django.conf import settings
    return render(request, 'pricing.html', {
        'STRIPE_PUBLIC_KEY': getattr(settings, 'STRIPE_PUBLIC_KEY', '')
    })

def privacy_policy_view(request):
    return render(request, 'privacy_policy.html')

def user_agreement_view(request):
    return render(request, 'user_agreement.html')

def faq_view(request):
    return render(request, 'FAQ.html')