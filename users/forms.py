from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Business, UserBusiness
from qualifications.models import Qual, Learner
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
import requests
from django.conf import settings
import logging
from captcha.fields import CaptchaField

class LoginForm(forms.Form):
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)

class CreateUserForm(forms.Form):
    email = forms.EmailField(label='Email')
    full_name = forms.CharField(max_length=255, label='Full Name')

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(label='Email Address', widget=forms.EmailInput(attrs={'class': 'block w-full rounded-md border-2 border-gray-300 shadow-sm focus:border-blue-600 focus:ring-blue-600 text-base px-4 py-2', 'required': True}))

class PasswordResetForm(forms.Form):
    email = forms.EmailField(required=True)
    business_id = forms.CharField(max_length=100, required=True)
    new_password = forms.CharField(widget=forms.PasswordInput, required=True, label="New Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm Password")
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")
        
        if new_password != confirm_password:
            raise ValidationError("The passwords do not match.")
        
        return cleaned_data
    
class SetNewPasswordForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput, required=True, label="New Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm Password")
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")
        if new_password != confirm_password:
            raise ValidationError("The passwords do not match.")
        return cleaned_data


class BusinessLogoForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ['logo']
        widgets = {
            'logo': forms.ClearableFileInput(attrs={'accept': 'image/png,image/jpeg,image/jpg'}),
        }

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if logo:
            # Check if logo is a new file (InMemoryUploadedFile) or existing file (ImageFieldFile)
            if isinstance(logo, InMemoryUploadedFile):
                # Perform validation only for new uploads
                if logo.content_type not in ['image/png', 'image/jpeg', 'image/jpg']:
                    raise forms.ValidationError('Only PNG, JPEG, or JPG files are allowed.')
                if logo.size > 5 * 1024 * 1024:  # 5MB limit
                    raise forms.ValidationError('File size must be under 5MB.')
                # Resize image to 96x96 pixels
                img = Image.open(logo)
                img = img.convert('RGB')  # Ensure compatibility for JPEG
                img = img.resize((96, 96), Image.Resampling.LANCZOS)
                output = BytesIO()
                img.save(output, format='JPEG', quality=85)
                output.seek(0)
                logo = InMemoryUploadedFile(
                    output, 'ImageField', f"{logo.name.rsplit('.', 1)[0]}.jpg",
                    'image/jpeg', sys.getsizeof(output), None
                )
        return logo

logger = logging.getLogger('users')
class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=False)
    purpose = forms.ChoiceField(
        choices=[
            ('general', 'I need some general information'),
            ('support', 'I am an existing customer and need support'),
            ('sales', 'I am interested to buy'),
        ],
        widget=forms.RadioSelect,
        required=True
    )
    message = forms.CharField(widget=forms.Textarea, max_length=1000, required=True)
    captcha = CaptchaField(label='Verify you are not a bot')

    def clean_captcha(self):
        captcha_value = self.cleaned_data.get('captcha')
        if not captcha_value:
            logger.debug("CAPTCHA validation failed")
            raise forms.ValidationError('Please complete the CAPTCHA verification.')
        return captcha_value