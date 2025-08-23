from django.core.mail import EmailMessage
from django.conf import settings
from django.template.loader import render_to_string
import logging
from email.mime.image import MIMEImage
import os

logger = logging.getLogger(__name__)
ROLE_TYPES = (
    ('LEARNER', 'Learner'),
    ('ASSESSOR', 'Assessor'),
    ('IQA', 'Internal Quality Assurer'),
    ('EQA', 'External Quality Assurer'),
)

logger = logging.getLogger('users')  # Use the 'users' logger

def send_welcome_email(email, business_id, business_name, password, portal_url, sender_name):
    subject = 'Welcome to AssessEEZ'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email]

    logger.debug(f"Starting send_welcome_email for {email}")

    # Define logo path
    base_path = settings.STATIC_ROOT if settings.STATIC_ROOT and not settings.DEBUG else settings.BASE_DIR
    logo_path = os.path.join(base_path, 'static', 'images', 'assesseez_logo.png')
    
    # Fallback to STATICFILES_DIRS if available
    if hasattr(settings, 'STATICFILES_DIRS') and settings.STATICFILES_DIRS:
        for static_dir in settings.STATICFILES_DIRS:
            possible_path = os.path.join(static_dir, 'images', 'assesseez_logo.png')
            if os.path.exists(possible_path):
                logo_path = possible_path
                break

    logo_available = os.path.exists(logo_path)
    logger.debug(f"Logo available: {logo_available} at {logo_path}")

    # Render template
    html_message = render_to_string('welcome_email.html', {
        'business_id': business_id,
        'business_name': business_name,
        'email': email,
        'password': password,
        'portal_url': portal_url,
        'sender_name': sender_name,
        'logo_available': logo_available
    })
    logger.debug(f"Template rendered for {email}")

    # Create email
    email_message = EmailMessage(
        subject=subject,
        body=html_message,
        from_email=from_email,
        to=recipient_list,
    )
    email_message.content_subtype = 'html'
    logger.debug(f"EmailMessage created for {email}")

    # Attach logo if available
    if logo_available:
        logger.debug(f"Attempting to attach logo from: {logo_path}")
        try:
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
            logo = MIMEImage(logo_data)
            logo.add_header('Content-ID', '<assesseez_logo>')
            logo.add_header('Content-Disposition', 'inline', filename='assesseez_logo.png')
            email_message.attach(logo)
            logger.debug(f"Logo attached for {email}")
        except Exception as e:
            logger.error(f"Failed to attach logo at {logo_path}: {str(e)}")
            logo_available = False
            html_message = render_to_string('welcome_email.html', {
                'business_id': business_id,
                'business_name': business_name,
                'email': email,
                'password': password,
                'portal_url': portal_url,
                'sender_name': sender_name,
                'logo_available': False
            })
            email_message.body = html_message
            email_message.content_subtype = 'html'

    logger.debug(f"Sending email to {email}")
    result = email_message.send(fail_silently=False)
    logger.debug(f"Welcome email sent to {email}: {result}")
    return result