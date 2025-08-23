from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from users.models import CustomUser, UserBusiness
import logging

logger = logging.getLogger(__name__)

class BusinessIDAuthBackend(BaseBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        logger.debug(f"Authenticating: email={email}")
        if not email or not password:
            logger.debug("Missing email or password")
            return None

        try:
            user = CustomUser.objects.get(email__iexact=email)  # Case-insensitive
            logger.debug(f"Found user: {user}, is_superuser={user.is_superuser}, is_staff={user.is_staff}")
        except CustomUser.DoesNotExist:
            logger.debug("User does not exist")
            return None

        # Check password against CustomUser's password
        if check_password(password, user.password):
            logger.debug("Password check passed")
            # For non-superusers, verify they have at least one business association
            if not user.is_superuser:
                if not UserBusiness.objects.filter(user=user).exists():
                    logger.debug("Non-superuser has no business associations")
                    return None
            if request:
                # Do not set business_id in session yet; user will select business on main page
                request.session['business_id'] = None
            logger.debug("Authentication successful")
            return user
        else:
            logger.debug("Password check failed")
            return None

    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None