from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import uuid
from storages.backends.s3boto3 import S3Boto3Storage


class CustomUserManager(UserManager):
    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self._create_user(email, password, **extra_fields)

class Business(models.Model):
    business_id = models.CharField(max_length=6, primary_key=True, editable=False)
    name = models.CharField(max_length=255)
    address = models.TextField()
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to='business_logos/%Y/%m/%d/', storage=S3Boto3Storage(), blank=True, null=True)  # Updated
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.business_id:
            last_business = Business.objects.order_by('-business_id').first()
            if not last_business:
                self.business_id = 'AA0001'
            else:
                last_id = last_business.business_id
                prefix = last_id[:2]
                number = int(last_id[2:])
                if number < 9999:
                    self.business_id = prefix + f"{number + 1:04d}"
                else:
                    num = (ord(prefix[0]) - ord('A')) * 26 + (ord(prefix[1]) - ord('A'))
                    if num >= 675:
                        raise ValueError("No more business IDs available")
                    next_prefix = chr((num + 1) // 26 + ord('A')) + chr((num + 1) % 26 + ord('A'))
                    self.business_id = next_prefix + '0001'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



class CustomUser(AbstractUser):
    email = models.EmailField(unique=True, blank=False, null=False)  # Unique globally
    username = None  # Remove username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    full_name = models.CharField(max_length=255, blank=True, null=True)

    objects = CustomUserManager()  # Assign custom manager

    def __str__(self):
        return self.email



class UserBusiness(models.Model):
    USER_TYPE_CHOICES = (('superuser', 'Superuser'), ('admin', 'Admin'), ('user', 'User'))
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='user')
    class Meta:
        unique_together = ('user', 'business')  # email + business_id unique

    def __str__(self):
        return f"{self.business.business_id}.{self.user.email}"



class Record(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserBusiness, on_delete=models.SET_NULL, null=True, related_name='records')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='records')
    description = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    def clean(self):
        if not self.description.strip():
            raise ValidationError("Description cannot be empty.")

    def __str__(self):
        return f"Record by {self.user} for {self.business} at {self.created_at}"

    class Meta:
        verbose_name = "Record"
        verbose_name_plural = "Records"
        indexes = [
            models.Index(fields=['user'], name='idx_record_user'),
            models.Index(fields=['business'], name='idx_record_business'),
            models.Index(fields=['content_type', 'object_id'], name='idx_record_content'),
        ]

