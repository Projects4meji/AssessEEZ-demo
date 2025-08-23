from django import forms
from django.core.exceptions import ValidationError
from qualifications.models import Qual, Learner, Assessor, IQA, EQA, validate_file, EvidenceSubmission, ResourceFolder, COUNTRY_CHOICES, ETHNICITY_CHOICES, LearnerDocsByAssessor, IQADocumentRemark, DocumentRequirement, LearnerDocumentSubmission
from users.models import Business, UserBusiness, CustomUser
from .utils import ROLE_TYPES
from django.utils import timezone
import os 
import uuid
import logging
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
import logging


class RoleSelectionForm(forms.Form):
    role = forms.ChoiceField(choices=ROLE_TYPES, label="Select Role")

class BaseUserForm(forms.Form):
    email = forms.EmailField(label="Email Address")
    full_name = forms.CharField(max_length=255, label="Full Name")
    # Define both fields, but only one will be used depending on the form
    qualification = forms.ModelChoiceField(
        queryset=Qual.objects.none(),
        label="Qualification",
        empty_label="Select a qualification",
        required=False
    )
    qualifications = forms.ModelMultipleChoiceField(
        queryset=Qual.objects.none(),
        label="Qualifications",
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
        }),
        required=False
    )

    def __init__(self, *args, **kwargs):
        business = kwargs.pop('business', None)
        super().__init__(*args, **kwargs)
        self.business = business
        print(f"BaseUserForm.__init__: args = {args}, kwargs = {kwargs}, business = {self.business}")
        if self.business:
            try:
                # Set querysets for both fields
                self.fields['qualification'].queryset = Qual.objects.filter(business=self.business)
                self.fields['qualifications'].queryset = Qual.objects.filter(business=self.business)
                qual_count = self.fields['qualification'].queryset.count()
                qual_titles = [q.qualification_title for q in self.fields['qualification'].queryset]
                print(f"BaseUserForm: Business ID = {self.business.business_id}, PK = {self.business.pk}, Qual count = {qual_count}, Titles = {qual_titles}")
            except Exception as e:
                print(f"BaseUserForm: Error setting qualification querysets: {str(e)}")
        else:
            print("BaseUserForm: No business provided")

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        full_name = cleaned_data.get('full_name')
        qualification = cleaned_data.get('qualification')
        qualifications = cleaned_data.get('qualifications')

        if email:
            try:
                existing_user = CustomUser.objects.get(email=email)
                if existing_user.full_name and existing_user.full_name != full_name:
                    raise ValidationError({
                        'full_name': f"The name provided does not match the existing name for this email. The registered name is '{existing_user.full_name}'."
                    })
            except CustomUser.DoesNotExist:
                pass

        if email and self.business:
            try:
                user = CustomUser.objects.get(email=email)
                user_business = UserBusiness.objects.get(user=user, business=self.business)
                if isinstance(self, AssessorForm) and qualifications:
                    for qual in qualifications:
                        if Assessor.objects.filter(user=user_business, qualification=qual).exists():
                            raise ValidationError({
                                'qualifications': f"This user is already an Assessor for the qualification '{qual}'."
                            })
                        if IQA.objects.filter(user=user_business, qualification=qual).exists():
                            raise ValidationError({
                                'qualifications': f"This user is already an IQA for the qualification '{qual}' and cannot also be an Assessor."
                            })
                        if Learner.objects.filter(user=user_business, qualification=qual).exists():
                            raise ValidationError({
                                'qualifications': f"This user is already a Learner for the qualification '{qual}' and cannot also be an Assessor."
                            })
                elif isinstance(self, IQAForm) and qualifications:
                    for qual in qualifications:
                        if IQA.objects.filter(user=user_business, qualification=qual).exists():
                            raise ValidationError({
                                'qualifications': f"This user is already an IQA for the qualification '{qual}'."
                            })
                        if Assessor.objects.filter(user=user_business, qualification=qual).exists():
                            raise ValidationError({
                                'qualifications': f"This user is already an Assessor for the qualification '{qual}' and cannot also be an IQA."
                            })
                        if Learner.objects.filter(user=user_business, qualification=qual).exists():
                            raise ValidationError({
                                'qualifications': f"This user is already a Learner for the qualification '{qual}' and cannot also be an IQA."
                            })
                elif isinstance(self, LearnerForm) and qualification:
                    if Learner.objects.filter(user=user_business, qualification=qualification).exists():
                        raise ValidationError({
                            'qualification': f"This user is already a Learner for the selected qualification: {qualification}."
                        })
                    if Assessor.objects.filter(user=user_business, qualification=qualification).exists():
                        raise ValidationError({
                            'qualification': f"This user is already an Assessor for the selected qualification and cannot also be a Learner."
                        })
                    if IQA.objects.filter(user=user_business, qualification=qualification).exists():
                        raise ValidationError({
                            'qualification': f"This user is already an IQA for the selected qualification and cannot also be a Learner."
                        })
            except CustomUser.DoesNotExist:
                pass
            except UserBusiness.DoesNotExist:
                pass

        return cleaned_data

class WorkbookSubmissionForm(forms.Form):
    workbook_file = forms.FileField(
        label="Upload Workbook",
        validators=[validate_file],
        required=False,
        widget=forms.FileInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'})
    )

    def clean_workbook_file(self):
        file = self.cleaned_data.get('workbook_file')
        if not file:
            raise forms.ValidationError("A workbook file is required.")
        return file

class LearnerForm(BaseUserForm):
    assessor = forms.ModelChoiceField(
        queryset=UserBusiness.objects.none(),
        label="Assessor",
        empty_label="Select an assessor"
    )
    iqa = forms.ModelChoiceField(
        queryset=UserBusiness.objects.none(),
        label="IQA",
        empty_label="Select an IQA"
    )
    dob = forms.DateField(label="Date of Birth", widget=forms.DateInput(attrs={'type': 'date'}))
    disability = forms.BooleanField(label="Disability", required=False)
    address = forms.CharField(
        label="Address", max_length=500, required=False, widget=forms.Textarea(attrs={'rows': 3})
    )
    batch_number = forms.CharField(
        max_length=50, label="Batch #", required=False,
        widget=forms.TextInput(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'})
    )
    phone_number = forms.CharField(
        max_length=20,
        label="Phone Number",
        required=False,
        widget=forms.TextInput(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm', 'placeholder': '+1234567890'})
    )
    date_of_registration = forms.DateField(
        label="Date of Registration",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        initial=timezone.now
    )
    country = forms.ChoiceField(
        choices=[('', 'Select a country')] + COUNTRY_CHOICES,
        label="Country",
        required=False,
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'})
    )
    ethnicity = forms.ChoiceField(
        choices=ETHNICITY_CHOICES,
        label="Ethnicity",
        required=False,
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print(f"LearnerForm.__init__: business = {self.business}")
        # Remove qualifications field, keep qualification
        self.fields.pop('qualifications', None)
        self.fields['qualification'].required = True
        self.fields['assessor'].label_from_instance = lambda obj: obj.user.full_name or obj.user.email
        self.fields['iqa'].label_from_instance = lambda obj: obj.user.full_name or obj.user.email
        if 'qualification' in self.data:
            try:
                qual_id = self.data.get('qualification')
                self.fields['assessor'].queryset = UserBusiness.objects.filter(
                    assessor_assignments__qualification_id=qual_id
                ).distinct()
                self.fields['iqa'].queryset = UserBusiness.objects.filter(
                    iqa_assignments__qualification_id=qual_id
                ).distinct()
                print(f"LearnerForm: Assessor count = {self.fields['assessor'].queryset.count()}, IQA count = {self.fields['iqa'].queryset.count()}")
            except (ValueError, TypeError) as e:
                print(f"LearnerForm: Error setting assessor/iqa querysets: {str(e)}")

    def clean(self):
        cleaned_data = super().clean()
        qualification = cleaned_data.get('qualification')
        email = cleaned_data.get('email')
        batch_number = cleaned_data.get('batch_number')
        date_of_registration = cleaned_data.get('date_of_registration')

        if batch_number and not batch_number.strip():
            cleaned_data['batch_number'] = None

        if qualification:
            if not Assessor.objects.filter(qualification=qualification).exists():
                raise ValidationError("No Assessors available for this qualification.")
            if not IQA.objects.filter(qualification=qualification).exists():
                raise ValidationError("No IQAs available for this qualification.")

        if date_of_registration and date_of_registration > timezone.now().date():
            raise ValidationError({"date_of_registration": "Date of registration cannot be in the future."})

        return cleaned_data

class AssessorForm(BaseUserForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove qualification field, keep qualifications
        self.fields.pop('qualification', None)
        self.fields['qualifications'].required = True

class IQAForm(BaseUserForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove qualification field, keep qualifications
        self.fields.pop('qualification', None)
        self.fields['qualifications'].required = True
        
logger = logging.getLogger(__name__)

class EQAForm(forms.Form):
    email = forms.EmailField(label="Email Address")
    full_name = forms.CharField(max_length=255, label="Full Name")
    qualifications = forms.ModelMultipleChoiceField(
        queryset=Qual.objects.none(),
        label="Qualifications",
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded',
            'name': 'qualifications'
        })
    )
    learners = forms.ModelMultipleChoiceField(
        queryset=Learner.objects.none(),
        label="Learners",
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded',
            'name': 'learners'
        }),
        required=False
    )

    def __init__(self, *args, **kwargs):
        business = kwargs.pop('business', None)
        super().__init__(*args, **kwargs)
        logger.debug(f"EQAForm.__init__: args = {args}, kwargs = {kwargs}, business = {business}")
        if business:
            try:
                self.fields['qualifications'].queryset = Qual.objects.filter(business=business)
                qual_count = self.fields['qualifications'].queryset.count()
                logger.debug(f"EQAForm: Business ID = {business.business_id}, Qual count = {qual_count}")

                # Set learners queryset based on submitted qualifications
                selected_qual_ids = []
                if self.is_bound and 'qualifications' in self.data:
                    selected_qual_ids = self.data.getlist('qualifications')
                    logger.debug(f"Selected qualification IDs from form data: {selected_qual_ids}")
                elif 'qualifications' in self.initial:
                    selected_qual_ids = [str(q.id) for q in self.initial.get('qualifications', [])]
                    logger.debug(f"Selected qualification IDs from initial data: {selected_qual_ids}")

                if selected_qual_ids:
                    try:
                        self.fields['learners'].queryset = Learner.objects.filter(
                            qualification__id__in=selected_qual_ids,
                            is_active=True
                        )
                        learner_count = self.fields['learners'].queryset.count()
                        logger.debug(f"Learners queryset set: {learner_count} learners for qualifications {selected_qual_ids}")
                    except Exception as e:
                        logger.error(f"Error setting learners queryset: {str(e)}")
                else:
                    logger.debug("No selected qualifications, setting empty learners queryset")
            except Exception as e:
                logger.error(f"EQAForm: Error setting qualifications queryset: {str(e)}")
        else:
            logger.warning("EQAForm: No business provided")

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        full_name = cleaned_data.get('full_name')
        qualifications = cleaned_data.get('qualifications')
        business = self.initial.get('business')

        logger.debug(f"EQAForm.clean: email = {email}, qualifications = {qualifications}, business = {business}")

        if email:
            try:
                existing_user = CustomUser.objects.get(email=email)
                if existing_user.full_name and existing_user.full_name != full_name:
                    raise ValidationError({
                        'full_name': f"The name provided does not match the existing name for this email. The registered name is '{existing_user.full_name}'."
                    })
            except CustomUser.DoesNotExist:
                pass

        if email and qualifications and business:
            try:
                user = CustomUser.objects.get(email=email)
                user_business = UserBusiness.objects.get(user=user, business=business)
                for qual in qualifications:
                    if Learner.objects.filter(user=user_business, qualification=qual).exists():
                        raise ValidationError({
                            'qualifications': f"This user is already a Learner for the qualification '{qual}' and cannot also be an EQA."
                        })
                    if Assessor.objects.filter(user=user_business, qualification=qual).exists():
                        raise ValidationError({
                            'qualifications': f"This user is already an Assessor for the qualification '{qual}' and cannot also be an EQA."
                        })
                    if IQA.objects.filter(user=user_business, qualification=qual).exists():
                        raise ValidationError({
                            'qualifications': f"This user is already an IQA for the qualification '{qual}' and cannot also be an EQA."
                        })
            except CustomUser.DoesNotExist:
                pass
            except UserBusiness.DoesNotExist:
                pass

        if email and business:
            if UserBusiness.objects.filter(user__email=email, business=business).exists():
                raise ValidationError({"email": "This email is already assigned to this business."})

        return cleaned_data

    def clean_learners(self):
        learners = self.cleaned_data.get('learners', [])
        qualifications = self.cleaned_data.get('qualifications')
        business = self.initial.get('business')

        logger.debug(f"EQAForm.clean_learners: learners = {[str(l.id) for l in learners]}, qualifications = {qualifications}, business = {business}")

        if learners and business:
            try:
                learner_ids = [str(learner.id) for learner in learners]
                valid_learners = Learner.objects.filter(
                    id__in=learner_ids,
                    is_active=True
                )
                valid_learner_ids = set(str(learner.id) for learner in valid_learners)
                logger.debug(f"Valid learner IDs: {valid_learner_ids}")

                invalid_ids = set(learner_ids) - valid_learner_ids
                if invalid_ids:
                    logger.error(f"Invalid learner IDs: {invalid_ids}")
                    raise ValidationError(
                        f"Invalid learner IDs: {', '.join(invalid_ids)}. These are inactive or not found."
                    )

                # Log qualification association
                if qualifications:
                    qual_learners = valid_learners.filter(qualification__in=qualifications)
                    qual_learner_ids = set(str(learner.id) for learner in qual_learners)
                    logger.debug(f"Learner IDs for selected qualifications: {qual_learner_ids}")
                    unmatched_ids = valid_learner_ids - qual_learner_ids
                    if unmatched_ids:
                        logger.warning(f"Learner IDs not tied to selected qualifications: {unmatched_ids}")

                self.cleaned_data['learners'] = valid_learners
            except Exception as e:
                logger.error(f"Error validating learners: {str(e)}")
                raise ValidationError("Error validating learner selections.")
        else:
            logger.debug("No learners submitted or missing business")

        return self.cleaned_data['learners']
    
    
class UserFilterForm(forms.Form):
    qualifications = forms.ModelMultipleChoiceField(
        queryset=Qual.objects.none(),
        label="Select Qualifications",
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-multiselect'})
    )
    user_type = forms.ChoiceField(
        choices=[
            ('learner', 'Learner'),
            ('assessor', 'Assessor'),
            ('iqa', 'IQA'),
            ('eqa', 'EQA')
        ],
        label="Select User Type",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        if business:
            self.fields['qualifications'].queryset = Qual.objects.filter(business=business)


class EditUserForm(forms.Form):
    email = forms.EmailField(label="Email Address", widget=forms.EmailInput(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}))
    full_name = forms.CharField(max_length=255, label="Full Name", widget=forms.TextInput(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}))
    # Learner fields
    qualification = forms.ModelChoiceField(
        queryset=Qual.objects.none(),
        label="Qualification",
        empty_label="Select a qualification",
        required=True,
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'})
    )
    assessor = forms.ModelChoiceField(
        queryset=UserBusiness.objects.none(),
        label="Assessor",
        empty_label="Select an assessor",
        required=True,
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'})
    )
    iqa = forms.ModelChoiceField(
        queryset=UserBusiness.objects.none(),
        label="IQA",
        empty_label="Select an IQA",
        required=True,
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'})
    )
    learner_dob = forms.DateField(
        label="Date of Birth",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        required=False
    )
    learner_disability = forms.BooleanField(
        label="Disability",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'mt-1 h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'})
    )
    learner_address = forms.CharField(
        label="Address",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'})
    )
    learner_batch_number = forms.CharField(
        max_length=50,
        label="Batch #",
        required=False,
        widget=forms.TextInput(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'})
    )
    learner_phone_number = forms.CharField(
        max_length=20,
        label="Phone Number",
        required=False,
        widget=forms.TextInput(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm', 'placeholder': '+1234567890'})
    )
    learner_date_of_registration = forms.DateField(
        label="Date of Registration",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        required=True
    )
    learner_country = forms.ChoiceField(
        choices=[('', 'Select a country')] + COUNTRY_CHOICES,
        label="Country",
        required=False,
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'})
    )
    learner_ethnicity = forms.ChoiceField(
        choices=ETHNICITY_CHOICES,
        label="Ethnicity",
        required=False,
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'})
    )
  
    def __init__(self, *args, user_business=None, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_business = user_business
        self.business = business
        self.has_learner_role = False
        self.learner_instance = None

        if user_business:
            # Check if user has learner role
            self.has_learner_role = Learner.objects.filter(user=user_business).exists()
            if self.has_learner_role:
                self.learner_instance = Learner.objects.filter(user=user_business).first()
                # Set querysets for learner fields
                self.fields['qualification'].queryset = Qual.objects.filter(business=business)
                self.fields['assessor'].queryset = UserBusiness.objects.filter(
                    assessor_assignments__qualification=self.learner_instance.qualification
                ).distinct()
                self.fields['iqa'].queryset = UserBusiness.objects.filter(
                    iqa_assignments__qualification=self.learner_instance.qualification
                ).distinct()
                self.fields['assessor'].label_from_instance = lambda obj: obj.user.full_name or obj.user.email
                self.fields['iqa'].label_from_instance = lambda obj: obj.user.full_name or obj.user.email
                # Set initial values from learner instance
                self.initial['qualification'] = self.learner_instance.qualification
                self.initial['assessor'] = self.learner_instance.assessor
                self.initial['iqa'] = self.learner_instance.iqa
                self.initial['learner_dob'] = self.learner_instance.dob
                self.initial['learner_disability'] = self.learner_instance.disability
                self.initial['learner_address'] = self.learner_instance.address
                self.initial['learner_batch_number'] = self.learner_instance.batch_number
                self.initial['learner_phone_number'] = self.learner_instance.phone_number
                self.initial['learner_date_of_registration'] = self.learner_instance.date_of_registration
                self.initial['learner_country'] = self.learner_instance.country
                self.initial['learner_ethnicity'] = self.learner_instance.ethnicity

            self.initial['email'] = user_business.user.email
            self.initial['full_name'] = user_business.user.full_name

            # Remove learner fields if user is not a learner
            if not self.has_learner_role:
                learner_fields = [
                    'qualification', 'assessor', 'iqa', 'learner_dob', 'learner_disability',
                    'learner_address', 'learner_batch_number', 'learner_phone_number',
                    'learner_date_of_registration', 'learner_country', 'learner_ethnicity',
                ]
                for field in learner_fields:
                    self.fields.pop(field, None)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and email != self.user_business.user.email:
            if CustomUser.objects.filter(email=email).exists():
                raise ValidationError("This email is already in use by another user.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if self.has_learner_role:
            dob = cleaned_data.get('learner_dob')
            batch_number = cleaned_data.get('learner_batch_number')
            date_of_registration = cleaned_data.get('learner_date_of_registration')
            qualification = cleaned_data.get('qualification')

            if dob and dob > timezone.now().date():
                raise ValidationError({'learner_dob': "Date of birth cannot be in the future."})
            if batch_number and not batch_number.strip():
                cleaned_data['learner_batch_number'] = None
            if date_of_registration and date_of_registration > timezone.now().date():
                raise ValidationError({'learner_date_of_registration': "Date of registration cannot be in the future."})

            # Check if qualification is being changed and learner has submissions
            if qualification and self.learner_instance:
                current_qualification = self.learner_instance.qualification
                if qualification != current_qualification:
                    # Check for evidence submissions
                    has_evidence = EvidenceSubmission.objects.filter(
                        user=self.user_business,
                        assessment_criterion__learning_outcome__unit__qualification=current_qualification
                    ).exists()
                    # Check for document submissions
                    has_documents = LearnerDocumentSubmission.objects.filter(
                        learner=self.learner_instance,
                        document_requirement__qualification=current_qualification
                    ).exists()
                    if has_evidence or has_documents:
                        raise ValidationError({
                            'qualification': "The learner has some submissions in their portfolio. Their submissions will be deleted if you change the Qualification."
                        })

        return cleaned_data

class ResourceFolderForm(forms.ModelForm):
    qualifications = forms.ModelMultipleChoiceField(
        queryset=Qual.objects.none(),
        label="Qualifications",
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    visible_to_roles = forms.MultipleChoiceField(
        choices=ROLE_TYPES,
        label="Visible to Roles",
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    class Meta:
        model = ResourceFolder
        fields = ['name', 'qualifications', 'visible_to_roles']
        labels = {
            'name': 'Folder Name',
        }

    def __init__(self, *args, **kwargs):
        business = kwargs.pop('business', None)
        super().__init__(*args, **kwargs)
        if business:
            self.fields['qualifications'].queryset = Qual.objects.filter(business=business)

    def clean_name(self):
        name = self.cleaned_data['name']
        if not name.strip():
            raise ValidationError("Folder name cannot be empty.")
        return name

class ResourceFileForm(forms.Form):
    title = forms.CharField(max_length=200, label="File Title")
    file = forms.FileField(label="Upload File")

    def clean_title(self):
        title = self.cleaned_data['title']
        if not title.strip():
            raise ValidationError("File title cannot be empty.")
        return title

    def clean_file(self):
        file = self.cleaned_data['file']
        validate_file(file)
        return file

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        file = cleaned_data.get('file')
        if title and file:
            # Ensure title includes the file's extension
            file_ext = os.path.splitext(file.name)[1].lower()
            if not title.lower().endswith(file_ext):
                cleaned_data['title'] = title + file_ext
        return cleaned_data
    

class MultiFileInput(forms.FileInput):
    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs['multiple'] = True
        return super().render(name, value, attrs, renderer)

class EvidenceSubmissionForm(forms.Form):
    evidence_detail = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        label="Evidence Details",
        required=False
    )
    evidence_files = forms.FileField(
        widget=MultiFileInput(attrs={'class': 'mt-1 block w-full'}),
        label="Upload Evidence Files",
        validators=[validate_file],
        required=False,
        allow_empty_file=True
    )

    def clean_evidence_files(self):
        files = self.files.getlist('evidence_files')
        if not files and not self.cleaned_data.get('evidence_detail'):
            raise forms.ValidationError("You must provide either evidence details or at least one file.")
        return files

class FeedbackForm(forms.Form):
    feedback_detail = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        label="Feedback",
        required=False
    )

    def __init__(self, *args, **kwargs):
        assessment_criteria = kwargs.pop('assessment_criteria', [])
        initial_statuses = kwargs.pop('initial_statuses', {})
        super().__init__(*args, **kwargs)  # Call parent without initial_statuses
        # Dynamically add status fields for each AC
        for ac in assessment_criteria:
            # Map model status to form choice
            initial_status = initial_statuses.get(str(ac.id), 'PENDING')
            if initial_status == 'REJECTED':
                initial_status = 'REJECTED'  # Maps to "Resubmission Required" in choices
            elif initial_status not in ['PENDING', 'ACCEPTED', 'REJECTED']:
                initial_status = 'PENDING'  # Default for unmapped statuses
            self.fields[f'status_{ac.id}'] = forms.ChoiceField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('ACCEPTED', 'Accepted'),
                    ('REJECTED', 'Resubmission Required'),
                ],
                label=f"Status for {ac.ac_detail}",
                widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
                required=True,
                initial=initial_status
            )
class IQAFeedbackForm(forms.Form):
    sampling_type = forms.ChoiceField(
        choices=[('INTERIM', 'Interim'), ('SUMMATIVE', 'Summative')],
        label="Sampling Type",
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        required=True
    )
    outcome = forms.ChoiceField(
        choices=[('OK', 'Ok'), ('NON_CONFORMANCE', 'Non-Conformance')],
        label="Outcome",
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        required=True
    )
    comments = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        label="Comments",
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        comments = cleaned_data.get('comments')
        if comments and not comments.strip():
            cleaned_data['comments'] = None
        return cleaned_data
    

class IQAFeedbackToAssessorForm(forms.Form):
    assessor = forms.ModelChoiceField(
        queryset=UserBusiness.objects.none(),  # Will be set dynamically
        label="Assessor",
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        required=True
    )
    sampling_type = forms.ChoiceField(
        choices=[('INTERIM', 'Interim'), ('SUMMATIVE', 'Summative')],
        label="Sampling Type",
        widget=forms.Select(attrs={'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        required=True
    )
    sampling_date = forms.DateField(
        label="Date of Sampling",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        required=True
    )
    comments = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm'}),
        label="Feedback Comments",
        required=True
    )

    def __init__(self, *args, iqa_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if iqa_user:
            # Get assessors who share learners with the IQA
            shared_assessors = UserBusiness.objects.filter(
                id__in=Learner.objects.filter(
                    iqa=iqa_user,
                    is_active=True
                ).values('assessor_id').distinct()
            ).select_related('user')
            self.fields['assessor'].queryset = shared_assessors
            self.fields['assessor'].label_from_instance = lambda obj: obj.user.full_name or obj.user.email

    def clean(self):
        cleaned_data = super().clean()
        comments = cleaned_data.get('comments')
        if comments and not comments.strip():
            raise ValidationError("Feedback comments cannot be empty.")
        return cleaned_data
    

class DocumentRequirementForm(forms.ModelForm):
    class Meta:
        model = DocumentRequirement
        fields = ['title', 'description', 'template']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded p-2'}),
            'description': forms.Textarea(attrs={'class': 'w-full border border-gray-300 rounded p-2', 'rows': 4}),
            'template': forms.FileInput(attrs={'class': 'w-full border border-gray-300 rounded p-2'}),
        }

    def clean_template(self):
        template = self.cleaned_data.get('template')
        if template:
            # Validate file size and type (already handled by model validator, but reinforce here)
            max_size_mb = 1000
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.mp4', '.doc', '.docx', '.ppt', '.pptx']
            if template.size > max_size_mb * 1024 * 1024:
                raise forms.ValidationError(f"File size must not exceed {max_size_mb}MB.")
            ext = os.path.splitext(template.name)[1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}.")
        return template
    
class LearnerDocumentSubmissionForm(forms.ModelForm):
    class Meta:
        model = LearnerDocumentSubmission
        fields = ['document_file']
        widgets = {
            'document_file': forms.FileInput(attrs={'class': 'mt-1 block w-full'}),
        }


class DocumentCheckForm(forms.ModelForm):
    class Meta:
        model = LearnerDocumentSubmission
        fields = ['status', 'comments']
        widgets = {
            'status': forms.Select(attrs={'class': 'mt-1 block w-full'}),
            'comments': forms.Textarea(attrs={'class': 'mt-1 block w-full', 'rows': 4, 'placeholder': 'Enter comments (required if rejecting)'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        comments = cleaned_data.get('comments')
        if status == 'REJECTED' and not comments:
            self.add_error('comments', 'Comments are required when rejecting a document.')
        return cleaned_data


class IQADocumentRemarkForm(forms.ModelForm):
    class Meta:
        model = IQADocumentRemark
        fields = ['remark', 'comments']
        widgets = {
            'remark': forms.Select(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'}),
            'comments': forms.Textarea(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        remark = cleaned_data.get('remark')
        comments = cleaned_data.get('comments')
        if remark == 'NON_CONFORMANCE' and not comments:
            raise forms.ValidationError("Comments are required for Non-Conformance remarks.")
        return cleaned_data
    

class LearnerDocsByAssessorForm(forms.ModelForm):
    class Meta:
        model = LearnerDocsByAssessor
        fields = ['title', 'description', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full p-2 border rounded'}),
            'description': forms.Textarea(attrs={'class': 'w-full p-2 border rounded', 'rows': 4}),
            'file': forms.FileInput(attrs={'class': 'w-full p-2 border rounded'}),
        }

logger = logging.getLogger(__name__)
class MessageForm(forms.Form):
    qualification = forms.ModelChoiceField(
        queryset=Qual.objects.none(),
        label="Qualification",
        empty_label="Select a qualification",
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full p-2 border border-gray-300 rounded-lg',
            'id': 'id_qualification'  # Changed to match JavaScript
        })
    )
    recipients = forms.ModelMultipleChoiceField(
        queryset=UserBusiness.objects.none(),
        label="Recipients",
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full p-2 border border-gray-300 rounded-lg select2',
            'id': 'id_recipients',  # Changed to match JavaScript
            'multiple': 'multiple'
        })
    )
    subject = forms.CharField(
        max_length=255,
        label="Subject",
        widget=forms.TextInput(attrs={
            'class': 'w-full p-2 border border-gray-300 rounded-lg'
        })
    )
    body = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={
            'class': 'w-full p-2 border border-gray-300 rounded-lg',
            'rows': 5
        })
    )
    attachment = forms.FileField(
        label="Attachment",
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'w-full p-2 border border-gray-300 rounded-lg'
        })
    )

    def __init__(self, *args, user_business=None, business=None, is_reply=False, reply_subject=None, reply_recipients=None, reply_qualification=None, qualification_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_business = user_business
        self.business = business
        self.is_reply = is_reply
        self.reply_subject = reply_subject
        self.reply_recipients = reply_recipients
        self.reply_qualification = reply_qualification

        if user_business and business:
            # Set qualification queryset
            if qualification_queryset is not None:
                self.fields['qualification'].queryset = qualification_queryset
            else:
                if user_business.user_type == 'admin':
                    self.fields['qualification'].queryset = Qual.objects.filter(business=business)
                else:
                    learner_qual_ids = Learner.objects.filter(user=user_business, qualification__business=business).values_list('qualification__id', flat=True)
                    assessor_qual_ids = Assessor.objects.filter(user=user_business, qualification__business=business).values_list('qualification__id', flat=True)
                    iqa_qual_ids = IQA.objects.filter(user=user_business, qualification__business=business).values_list('qualification__id', flat=True)
                    eqa_qual_ids = EQA.objects.filter(user=user_business, qualification__business=business).values_list('qualification__id', flat=True)
                    qual_ids = set(learner_qual_ids) | set(assessor_qual_ids) | set(iqa_qual_ids) | set(eqa_qual_ids)
                    self.fields['qualification'].queryset = Qual.objects.filter(id__in=qual_ids, business=business)
            logger.debug(f"Qualification queryset count: {self.fields['qualification'].queryset.count()}")

            # Customize recipient display to include role
            def get_recipient_label(obj):
                name = obj.user.full_name or obj.user.email
                qualification_id = self.data.get('qualification') or (reply_qualification.id if reply_qualification else None)
                role = "Admin" if obj.user_type == 'admin' else None
                if qualification_id and not role:
                    if Learner.objects.filter(user=obj, qualification_id=qualification_id).exists():
                        role = "Learner"
                    elif Assessor.objects.filter(user=obj, qualification_id=qualification_id).exists():
                        role = "Assessor"
                    elif IQA.objects.filter(user=obj, qualification_id=qualification_id).exists():
                        role = "IQA"
                    elif EQA.objects.filter(user=obj, qualification_id=qualification_id).exists():
                        role = "EQA"
                    else:
                        role = "User"
                return f"{name} ({role})" if role else name

            self.fields['recipients'].label_from_instance = get_recipient_label

            # Set recipients queryset
            if is_reply and reply_recipients:
                self.fields['recipients'].queryset = UserBusiness.objects.filter(
                    id__in=[r.id for r in reply_recipients]
                ).distinct()
                self.fields['recipients'].initial = reply_recipients
                self.fields['recipients'].widget.attrs['readonly'] = 'readonly'
                if reply_qualification:
                    self.fields['qualification'].initial = reply_qualification
                    self.fields['qualification'].widget.attrs['readonly'] = 'readonly'
            else:
                # Handle both GET and POST
                qualification_id = self.data.get('qualification') if self.data else None
                logger.debug(f"Form qualification_id: {qualification_id}")
                if qualification_id:
                    # For POST, include all submitted recipient IDs
                    if self.data and 'recipients' in self.data:
                        recipient_ids = self.data.getlist('recipients')
                        logger.debug(f"POST data recipients: {recipient_ids}")
                        self.fields['recipients'].queryset = UserBusiness.objects.filter(
                            Q(id__in=recipient_ids) |
                            Q(assessor_assignments__qualification_id=qualification_id, business=business) |
                            Q(learner_assignments__qualification_id=qualification_id, business=business) |
                            Q(iqa_assignments__qualification_id=qualification_id, business=business) |
                            Q(eqa_assignments__qualification_id=qualification_id, business=business) |
                            Q(user_type='admin', business=business)
                        ).distinct().exclude(id=user_business.id)
                    else:
                        # For GET, use role-based filtering
                        if user_business.user_type == 'admin':
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
                            self.fields['recipients'].queryset = (assessors | learners | iqas | eqas).distinct().exclude(id=user_business.id)
                            logger.debug(f"Admin recipients - Assessors: {assessors.count()}, Learners: {learners.count()}, IQAs: {iqas.count()}, EQAs: {eqas.count()}")
                        elif EQA.objects.filter(user=user_business, qualification_id=qualification_id).exists():
                            self.fields['recipients'].queryset = UserBusiness.objects.filter(
                                user_type='admin',
                                business=business
                            ).distinct()
                            logger.debug(f"EQA recipients - Admins: {self.fields['recipients'].queryset.count()}")
                        elif user_business.user_type == 'iqa' or IQA.objects.filter(user=user_business, qualification_id=qualification_id).exists():
                            learners = UserBusiness.objects.filter(
                                learner_assignments__qualification_id=qualification_id,
                                learner_assignments__iqa=user_business,
                                business=business
                            ).distinct()
                            assessors = UserBusiness.objects.filter(
                                learner_assignments__qualification_id=qualification_id,
                                learner_assignments__iqa=user_business,
                                learner_assignments__assessor__isnull=False,
                                business=business
                            ).distinct()
                            admins = UserBusiness.objects.filter(
                                user_type='admin',
                                business=business
                            ).distinct()
                            self.fields['recipients'].queryset = (learners | assessors | admins).distinct()
                            logger.debug(f"IQA recipients - Learners: {learners.count()}, Assessors: {assessors.count()}, Admins: {admins.count()}")
                        elif Learner.objects.filter(user=user_business, qualification_id=qualification_id).exists():
                            learner = Learner.objects.filter(user=user_business, qualification_id=qualification_id).first()
                            if learner:
                                recipient_ids = []
                                if learner.assessor:
                                    recipient_ids.append(learner.assessor.id)
                                if learner.iqa:
                                    recipient_ids.append(learner.iqa.id)
                                self.fields['recipients'].queryset = UserBusiness.objects.filter(
                                    Q(id__in=recipient_ids) | Q(user_type='admin', business=business)
                                ).distinct()
                                logger.debug(f"Learner recipients - Assessor: {1 if learner.assessor else 0}, IQA: {1 if learner.iqa else 0}, Admins: {self.fields['recipients'].queryset.filter(user_type='admin').count()}")
                        elif Assessor.objects.filter(user=user_business, qualification_id=qualification_id).exists():
                            learners = UserBusiness.objects.filter(
                                learner_assignments__assessor=user_business,
                                learner_assignments__qualification_id=qualification_id,
                                business=business
                            ).distinct()
                            iqas = UserBusiness.objects.filter(
                                learner_assignments__qualification_id=qualification_id,
                                learner_assignments__assessor=user_business,
                                learner_assignments__iqa__isnull=False,
                                business=business
                            ).distinct()
                            admins = UserBusiness.objects.filter(
                                user_type='admin',
                                business=business
                            ).distinct()
                            self.fields['recipients'].queryset = (learners | iqas | admins).distinct()
                            logger.debug(f"Assessor recipients - Learners: {learners.count()}, IQAs: {iqas.count()}, Admins: {admins.count()}")

            if is_reply and reply_subject:
                self.fields['subject'].initial = reply_subject
                self.fields['subject'].widget.attrs['readonly'] = 'readonly'

    def clean(self):
        cleaned_data = super().clean()
        recipients = cleaned_data.get('recipients')
        subject = cleaned_data.get('subject')
        body = cleaned_data.get('body')
        qualification = cleaned_data.get('qualification')

        logger.debug(f"Cleaning form data: recipients={[r.id for r in recipients] if recipients else None}, subject={subject}, body={body}, qualification={qualification.id if qualification else None}")

        if not self.is_reply:
            if not qualification:
                raise ValidationError({'qualification': "A qualification must be selected for new messages."})
            if not recipients:
                raise ValidationError({'recipients': "At least one recipient is required for new messages."})
        else:
            if not recipients:
                raise ValidationError({'recipients': "At least one recipient is required for replies."})

        if not subject or not subject.strip():
            raise ValidationError({'subject': "Subject cannot be empty."})
        if not body or not body.strip():
            raise ValidationError({'body': "Message body cannot be empty."})

        return cleaned_data

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            validate_file(attachment)
        return attachment