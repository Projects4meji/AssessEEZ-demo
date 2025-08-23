from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    business_id = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        business_id = attrs.get("business_id")

        # Authenticate using BusinessIDAuthBackend
        user = authenticate(email=email, password=password, business_id=business_id)
        if not user:
            raise serializers.ValidationError("Invalid credentials or business ID")

        # Manually generate tokens instead of calling parent validate
        refresh = RefreshToken.for_user(user)
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        return data