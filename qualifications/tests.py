from django.test import TestCase
from django.core.exceptions import ValidationError
from users.models import Business, UserBusiness, CustomUser
from qualifications.models import Qual, Learner, Assessor, IQA
from django.contrib.auth.hashers import make_password
import uuid

class RoleTests(TestCase):
    def test_multiple_qualifications_and_role_constraint(self):
        # Create businesses
        business1 = Business.objects.create(business_id="B1", name="Business 1")
        business2 = Business.objects.create(business_id="B2", name="Business 2")

        # Create user
        user = CustomUser.objects.create(email="test@example.com")

        # Create user-business associations
        user_business1 = UserBusiness.objects.create(
            user=user, business=business1, user_type='user', password=make_password('pass123')
        )
        user_business2 = UserBusiness.objects.create(
            user=user, business=business2, user_type='user', password=make_password('pass123')
        )

        # Create qualifications
        qual = Qual.objects.create(
            id=uuid.uuid4(),
            qualification_title="Test Qual",
            qualification_number="Q1",
            awarding_body="AB",
            business=business1
        )
        qual2 = Qual.objects.create(
            id=uuid.uuid4(),
            qualification_title="Test Qual",
            qualification_number="Q2",
            awarding_body="AB",
            business=business2
        )
        qual3 = Qual.objects.create(
            id=uuid.uuid4(),
            qualification_title="Test Qual 2",
            qualification_number="Q3",
            awarding_body="AB",
            business=business1
        )

        # Create Assessor (no Learner conflict)
        Assessor.objects.create(user=user_business1, qualification=qual)

        # Test that IQA creation fails for same qualification and business
        with self.assertRaises(ValidationError):
            IQA.objects.create(user=user_business1, qualification=qual)  # Should fail: same qual, same business

        # Test that IQA creation succeeds for different qualification or business
        IQA.objects.create(user=user_business1, qualification=qual3)  # Succeeds: different qual
        IQA.objects.create(user=user_business2, qualification=qual2)  # Succeeds: different business