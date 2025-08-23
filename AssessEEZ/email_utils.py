import logging
from django.core.mail import get_connection
from django.core.mail.message import EmailMessage
from django.conf import settings
from django.utils.html import strip_tags
from django.urls import reverse
from django.template.loader import render_to_string
from email.mime.image import MIMEImage
import os
from users.models import UserBusiness, CustomUser

logger = logging.getLogger(__name__)

def send_email(subject, message, from_email, recipient_list, fail_silently=False, html_message=None):
    """
    Custom email sending function to replace send_mail, using SESEmailBackend.
    """
    try:
        logger.debug("Creating backend connection...")
        connection = get_connection(backend='AssessEEZ.email_backends.SESEmailBackend')

        logger.debug("Creating EmailMessage...")
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=from_email,
            to=recipient_list,
            connection=connection
        )
        email.content_subtype = 'plain'  # Ensure plain text
        if html_message:
            email.content_subtype = 'html'
            email.body = html_message

        logger.debug("Sending email...")
        result = email.send(fail_silently=fail_silently)
        logger.debug("Email sent, result: %s", result)
        return result
    except Exception as e:
        logger.error("Email sending failed: %s", str(e))
        if not fail_silently:
            raise e
        return 0

def send_welcome_email(email, business_name, password, portal_url, sender_name, role, qualification_title):
    """
    Send a welcome email to a new user after their first registration with a business.
    Includes role, qualification details, and full name.
    """
    subject = 'Welcome to AssessEEZ'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [email]

    logger.debug(f"Starting send_welcome_email for {email}")
    password_to_send = password  # Use provided password or None

    # Retrieve full_name from CustomUser
    try:
        user = CustomUser.objects.get(email=email)
        full_name = user.full_name or "User"
    except CustomUser.DoesNotExist:
        full_name = "User"
        logger.warning(f"CustomUser not found for email: {email}")

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

    # Render template with full_name
    html_message = render_to_string('welcome_email.html', {
        'business_name': business_name,
        'email': email,
        'password': password_to_send,
        'portal_url': portal_url,
        'sender_name': sender_name,
        'role': role,
        'qualification_title': qualification_title,
        'full_name': full_name,
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
            html_message = render_to_string('welcome_email.html', {
                'business_name': business_name,
                'email': email,
                'password': password_to_send,
                'portal_url': portal_url,
                'sender_name': sender_name,
                'role': role,
                'qualification_title': qualification_title,
                'full_name': full_name,
                'logo_available': False
            })
            email_message.body = html_message
            email_message.content_subtype = 'html'

    logger.debug(f"Sending email to {email}")
    result = email_message.send(fail_silently=False)
    logger.debug(f"Welcome email sent to {email}: {result}")
    return result

def send_role_notification_email(recipient_email, business_name, business_id, action, role, learner_name=None, qualification_titles=None):
    """
    Send a notification email for role assignments, removals, or new qualifications.
    """
    subject = f'AssessEEZ: {action} Notification'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [recipient_email]
    login_url = f"{settings.SITE_URL}{reverse('login')}"

    # Fetch recipient's full name
    try:
        user = CustomUser.objects.get(email=recipient_email)
        recipient_name = user.full_name or recipient_email
    except CustomUser.DoesNotExist:
        recipient_name = recipient_email
        logger.warning(f"CustomUser not found for email: {recipient_email}")

    # Fetch admin's email for the business
    try:
        admin_user = UserBusiness.objects.filter(business__business_id=business_id, user_type='admin').select_related('user').first()
        admin_email = admin_user.user.email if admin_user else 'support@assesseez.co.uk'
    except UserBusiness.DoesNotExist:
        admin_email = 'support@assesseez.co.uk'
        logger.warning(f"No admin found for business ID: {business_id}")

    # Ensure qualification_titles is a list
    qualification_titles = qualification_titles or []

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
    html_message = render_to_string('role_notification_email.html', {
        'business_name': business_name,
        'business_id': business_id,
        'action': action,
        'role': role,
        'recipient_name': recipient_name,
        'learner_name': learner_name,
        'qualification_titles': qualification_titles,
        'login_url': login_url,
        'admin_email': admin_email,
        'logo_available': logo_available
    })
    plain_message = strip_tags(html_message)

    # Create email
    email_message = EmailMessage(
        subject=subject,
        body=html_message,
        from_email=from_email,
        to=recipient_list,
    )
    email_message.content_subtype = 'html'

    # Attach logo if available
    if logo_available:
        try:
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
            logo = MIMEImage(logo_data)
            logo.add_header('Content-ID', '<assesseez_logo>')
            logo.add_header('Content-Disposition', 'inline', filename='assesseez_logo.png')
            email_message.attach(logo)
        except Exception as e:
            logger.error(f"Failed to attach logo at {logo_path}: {str(e)}")
            html_message = render_to_string('role_notification_email.html', {
                'business_name': business_name,
                'business_id': business_id,
                'action': action,
                'role': role,
                'recipient_name': recipient_name,
                'learner_name': learner_name,
                'qualification_titles': qualification_titles,
                'login_url': login_url,
                'admin_email': admin_email,
                'logo_available': False
            })
            email_message.body = html_message
            email_message.content_subtype = 'html'

    logger.debug(f"Sending role notification to {recipient_email} for {action}")
    result = email_message.send(fail_silently=False)
    logger.debug(f"Role notification email sent to {recipient_email}: {result}")
    return result

def send_non_conformance_email(recipient_email, iqa_name, learner_name, qualification_title, unit_title, business_name, business_id):
    """
    Send a notification email to an assessor when an IQA marks a sampling as non-conformance.
    """
    subject = 'AssessEEZ: Non-Conformance Notification'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [recipient_email]
    login_url = f"{settings.SITE_URL}{reverse('login')}"
    support_email = settings.SUPPORT_EMAIL or 'support@assesseez.co.uk'

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
    html_message = render_to_string('non_conformance_email.html', {
        'iqa_name': iqa_name,
        'learner_name': learner_name,
        'qualification_title': qualification_title,
        'unit_title': unit_title,
        'business_name': business_name,
        'business_id': business_id,
        'login_url': login_url,
        'support_email': support_email,
        'logo_available': logo_available
    })
    plain_message = strip_tags(html_message)

    # Create email
    email_message = EmailMessage(
        subject=subject,
        body=html_message,
        from_email=from_email,
        to=recipient_list,
    )
    email_message.content_subtype = 'html'

    # Attach logo if available
    if logo_available:
        try:
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
            logo = MIMEImage(logo_data)
            logo.add_header('Content-ID', '<assesseez_logo>')
            logo.add_header('Content-Disposition', 'inline', filename='assesseez_logo.png')
            email_message.attach(logo)
        except Exception as e:
            logger.error(f"Failed to attach logo at {logo_path}: {str(e)}")
            html_message = render_to_string('non_conformance_email.html', {
                'iqa_name': iqa_name,
                'learner_name': learner_name,
                'qualification_title': qualification_title,
                'unit_title': unit_title,
                'business_name': business_name,
                'business_id': business_id,
                'login_url': login_url,
                'support_email': support_email,
                'logo_available': False
            })
            email_message.body = html_message
            email_message.content_subtype = 'html'

    logger.debug(f"Sending non-conformance notification to {recipient_email} for learner {learner_name}")
    result = email_message.send(fail_silently=False)
    logger.debug(f"Non-conformance email sent to {recipient_email}: {result}")
    return result

def send_message_notification_email(recipient_email, recipient_name, sender_name, sender_role, business_name, message_subject, message_sent_at, fail_silently=False):
    """
    Send a notification email to a user when they receive a new message on AssessEEZ.
    """
    subject = 'New Message Received on AssessEEZ'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [recipient_email]
    login_url = f"{settings.SITE_URL}{reverse('login')}"
    support_email = settings.SUPPORT_EMAIL or 'support@assesseez.co.uk'

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
    html_message = render_to_string('message_notification_email.html', {
        'recipient_name': recipient_name,
        'sender_name': sender_name,
        'sender_role': sender_role,
        'business_name': business_name,
        'message_subject': message_subject,
        'message_sent_at': message_sent_at.strftime('%Y-%m-%d %H:%M'),
        'login_url': login_url,
        'support_email': support_email,
        'logo_available': logo_available
    })
    plain_message = strip_tags(html_message)

    # Create email
    email_message = EmailMessage(
        subject=subject,
        body=html_message,
        from_email=from_email,
        to=recipient_list,
    )
    email_message.content_subtype = 'html'

    # Attach logo if available
    if logo_available:
        try:
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
            logo = MIMEImage(logo_data)
            logo.add_header('Content-ID', '<assesseez_logo>')
            logo.add_header('Content-Disposition', 'inline', filename='assesseez_logo.png')
            email_message.attach(logo)
        except Exception as e:
            logger.error(f"Failed to attach logo at {logo_path}: {str(e)}")
            html_message = render_to_string('message_notification_email.html', {
                'recipient_name': recipient_name,
                'sender_name': sender_name,
                'sender_role': sender_role,
                'business_name': business_name,
                'message_subject': message_subject,
                'message_sent_at': message_sent_at.strftime('%Y-%m-%d %H:%M'),
                'login_url': login_url,
                'support_email': support_email,
                'logo_available': False
            })
            email_message.body = html_message
            email_message.content_subtype = 'html'

    logger.debug(f"Sending message notification to {recipient_email} from {sender_name} ({sender_role}) at {business_name}")
    result = email_message.send(fail_silently=fail_silently)
    logger.debug(f"Message notification email sent to {recipient_email}: {result}")
    return result

def send_document_submission_notification_email(assessor_email, assessor_name, learner_name, qualification_title, business_name, business_id, submission_type):
    """
    Send a notification email to an assessor when a learner submits a document or evidence.
    """
    subject = f'AssessEEZ: New {submission_type} Submission Notification'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [assessor_email]
    login_url = f"{settings.SITE_URL}{reverse('login')}"

    # Fetch admin's email for the business
    try:
        admin_user = UserBusiness.objects.filter(business__business_id=business_id, user_type='admin').select_related('user').first()
        admin_email = admin_user.user.email if admin_user else 'support@assesseez.co.uk'
    except UserBusiness.DoesNotExist:
        admin_email = 'support@assesseez.co.uk'
        logger.warning(f"No admin found for business ID: {business_id}")

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
    html_message = render_to_string('document_submission_notification_email.html', {
        'assessor_name': assessor_name,
        'learner_name': learner_name,
        'qualification_title': qualification_title,
        'business_name': business_name,
        'business_id': business_id,
        'submission_type': submission_type,
        'login_url': login_url,
        'admin_email': admin_email,
        'logo_available': logo_available
    })
    plain_message = strip_tags(html_message)

    # Create email
    email_message = EmailMessage(
        subject=subject,
        body=html_message,
        from_email=from_email,
        to=recipient_list,
    )
    email_message.content_subtype = 'html'

    # Attach logo if available
    if logo_available:
        try:
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
            logo = MIMEImage(logo_data)
            logo.add_header('Content-ID', '<assesseez_logo>')
            logo.add_header('Content-Disposition', 'inline', filename='assesseez_logo.png')
            email_message.attach(logo)
        except Exception as e:
            logger.error(f"Failed to attach logo at {logo_path}: {str(e)}")
            html_message = render_to_string('document_submission_notification_email.html', {
                'assessor_name': assessor_name,
                'learner_name': learner_name,
                'qualification_title': qualification_title,
                'business_name': business_name,
                'business_id': business_id,
                'submission_type': submission_type,
                'login_url': login_url,
                'admin_email': admin_email,
                'logo_available': False
            })
            email_message.body = html_message
            email_message.content_subtype = 'html'

    logger.debug(f"Sending {submission_type} submission notification to {assessor_email} for learner {learner_name}")
    result = email_message.send(fail_silently=False)
    logger.debug(f"{submission_type} submission notification email sent to {assessor_email}: {result}")
    return result

def send_notification_email(recipient_email, learner_name, business_name, notification_message, notification_date):
    """
    Send a notification email to a learner when a new notification is generated.
    """
    subject = 'AssessEEZ: New Notification'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [recipient_email]
    login_url = f"{settings.SITE_URL}{reverse('login')}"
    support_email = settings.SUPPORT_EMAIL or 'support@assesseez.co.uk'

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
    html_message = render_to_string('notification_email.html', {
        'learner_name': learner_name,
        'business_name': business_name,
        'notification_message': notification_message,
        'notification_date': notification_date.strftime('%Y-%m-%d %H:%M'),
        'login_url': login_url,
        'support_email': support_email,
        'logo_available': logo_available
    })
    plain_message = strip_tags(html_message)

    # Create email
    email_message = EmailMessage(
        subject=subject,
        body=html_message,
        from_email=from_email,
        to=recipient_list,
    )
    email_message.content_subtype = 'html'

    # Attach logo if available
    if logo_available:
        try:
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
            logo = MIMEImage(logo_data)
            logo.add_header('Content-ID', '<assesseez_logo>')
            logo.add_header('Content-Disposition', 'inline', filename='assesseez_logo.png')
            email_message.attach(logo)
        except Exception as e:
            logger.error(f"Failed to attach logo at {logo_path}: {str(e)}")
            html_message = render_to_string('notification_email.html', {
                'learner_name': learner_name,
                'business_name': business_name,
                'notification_message': notification_message,
                'notification_date': notification_date.strftime('%Y-%m-%d %H:%M'),
                'login_url': login_url,
                'support_email': support_email,
                'logo_available': False
            })
            email_message.body = html_message
            email_message.content_subtype = 'html'

    logger.debug(f"Sending notification email to {recipient_email} for notification: {notification_message}")
    result = email_message.send(fail_silently=False)
    logger.debug(f"Notification email sent to {recipient_email}: {result}")
    return result