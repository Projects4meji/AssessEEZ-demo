from django.db import models
from django.core.exceptions import ValidationError
from users.models import Business, UserBusiness
import uuid
import os
from django.utils import timezone
from qualifications.utils import ROLE_TYPES
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage
from django.core.validators import RegexValidator
# Custom validator for file size and type

def validate_file(fieldfile_obj):
    max_size_mb = 1000  # Max file size in MB
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.mp4', '.doc', '.docx', '.ppt', '.pptx', '.zip', '.xls', '.xlsx']
    
    file_size = fieldfile_obj.size
    if file_size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"File size must not exceed {max_size_mb}MB.")
    
    ext = os.path.splitext(fieldfile_obj.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}.")
    pass

class Qual(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qualification_title = models.CharField(max_length=200)
    qualification_number = models.CharField(max_length=50)
    awarding_body = models.CharField(max_length=200)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='qualifications')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.qualification_title.strip():
            raise ValidationError("Qualification title cannot be empty.")
        if not self.awarding_body.strip():
            raise ValidationError("Awarding body cannot be empty.")
        if len(self.qualification_title) > 200:
            raise ValidationError("Qualification title cannot exceed 200 characters.")
        if len(self.awarding_body) > 200:
            raise ValidationError("Awarding body cannot exceed 200 characters.")

    def __str__(self):
        return f"{self.qualification_title} ({self.qualification_number})"
    def copy_to_business(self, new_business):
        """
        Create a copy of this qualification for a new business, including related units, LOs, and ACs.
        Returns the new Qual instance.
        """
        # Create a new Qual instance with the same details but a different business
        new_qual = Qual(
            qualification_title=self.qualification_title,
            qualification_number=self.qualification_number,
            awarding_body=self.awarding_body,
            business=new_business
        )
        new_qual.full_clean()  # Validate the new instance
        new_qual.save()

        # Copy related Units
        for unit in self.units.all():
            new_unit = Unit(
                unit_title=unit.unit_title,
                unit_number=unit.unit_number,
                qualification=new_qual,
                serial_number=unit.serial_number
            )
            new_unit.full_clean()
            new_unit.save()

            # Copy related Learning Outcomes (LOs)
            for lo in unit.learning_outcomes.all():
                new_lo = LO(
                    lo_detail=lo.lo_detail,
                    unit=new_unit,
                    serial_number=lo.serial_number
                )
                new_lo.full_clean()
                new_lo.save()

                # Copy related Assessment Criteria (ACs)
                for ac in lo.assessment_criteria.all():
                    new_ac = AC(
                        ac_detail=ac.ac_detail,
                        learning_outcome=new_lo,
                        serial_number=ac.serial_number
                    )
                    new_ac.full_clean()
                    new_ac.save()

        return new_qual
    class Meta:
        verbose_name = "Qualification"
        verbose_name_plural = "Qualifications"
        indexes = [
            models.Index(fields=['qualification_number'], name='idx_qualification_number'),
            models.Index(fields=['business'], name='idx_qualification_business'),
        ]
        unique_together = [['qualification_number', 'business']]  # Ensure uniqueness of qualification_number within a business
class Unit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit_title = models.CharField(max_length=200)
    unit_number = models.CharField(max_length=50)
    qualification = models.ForeignKey(Qual, on_delete=models.CASCADE, related_name='units')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    serial_number = models.FloatField(default=0)

    def clean(self):
        if not self.unit_title.strip():
            raise ValidationError("Unit title cannot be empty.")
        if len(self.unit_title) > 200:
            raise ValidationError("Unit title cannot exceed 200 characters.")

    def __str__(self):
        return f"{self.unit_title} ({self.unit_number})"

    class Meta:
        verbose_name = "Unit"
        verbose_name_plural = "Units"
        constraints = [
            models.UniqueConstraint(fields=['unit_number', 'qualification'], name='unique_unit_number_per_qualification'),
        ]
        indexes = [
            models.Index(fields=['unit_number'], name='idx_unit_number'),
            models.Index(fields=['qualification'], name='idx_unit_qualification'),
        ]

class LO(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lo_detail = models.TextField()
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='learning_outcomes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    serial_number = models.FloatField(default=0)
    
    def clean(self):
        if not self.lo_detail.strip():
            raise ValidationError("Learning outcome detail cannot be empty.")

    def __str__(self):
        return f"LO: {self.lo_detail[:50]}..."

    class Meta:
        verbose_name = "Learning Outcome"
        verbose_name_plural = "Learning Outcomes"
        constraints = [
            models.UniqueConstraint(fields=['lo_detail', 'unit'], name='unique_lo_detail_per_unit'),
        ]
        indexes = [
            models.Index(fields=['unit'], name='idx_lo_unit'),
        ]

class AC(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ac_detail = models.TextField()
    learning_outcome = models.ForeignKey(LO, on_delete=models.CASCADE, related_name='assessment_criteria')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    serial_number = models.FloatField(default=0)

    def clean(self):
        if not self.ac_detail.strip():
            raise ValidationError("Assessment criterion detail cannot be empty.")

    def __str__(self):
        return f"AC: {self.ac_detail[:50]}..."

    class Meta:
        verbose_name = "Assessment Criterion"
        verbose_name_plural = "Assessment Criteria"
        constraints = [
            models.UniqueConstraint(fields=['ac_detail', 'learning_outcome'], name='unique_ac_detail_per_lo'),
        ]
        indexes = [
            models.Index(fields=['learning_outcome'], name='idx_ac_learning_outcome'),
        ]

class WorkbookSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserBusiness, on_delete=models.CASCADE, related_name='workbook_submissions')
    learning_outcome = models.ForeignKey(LO, on_delete=models.CASCADE, related_name='workbook_submissions')
    workbook_file = models.FileField(upload_to='workbooks/%Y/%m/%d/', validators=[validate_file], storage=S3Boto3Storage(), null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('SUBMITTED', 'Submitted'), ('ACCEPTED', 'Accepted'), ('REJECTED', 'Rejected')], default='SUBMITTED')
    assessor = models.ForeignKey(
        UserBusiness,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assessed_workbooks',
        verbose_name="Assessor"
    )

    def clean(self):
        try:
            learner = Learner.objects.get(
                user=self.user,
                qualification=self.learning_outcome.unit.qualification
            )
            if not learner.is_active:
                raise ValidationError("This learner is deactivated and cannot submit workbooks for this qualification.")
            if self.assessor and self.assessor != learner.assessor:
                raise ValidationError("The assessor must be the one assigned to the learner.")
        except Learner.DoesNotExist:
            raise ValidationError("Only users assigned as Learners for this qualification can submit workbooks.")

    def __str__(self):
        return f"Workbook for {self.learning_outcome} by {self.user}"

    class Meta:
        verbose_name = "Workbook Submission"
        verbose_name_plural = "Workbook Submissions"
        indexes = [
            models.Index(fields=['user'], name='idx_workbook_user'),
            models.Index(fields=['learning_outcome'], name='idx_workbook_lo'),
            models.Index(fields=['assessor'], name='idx_workbook_assessor'),
        ]


class EvidenceSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserBusiness, on_delete=models.CASCADE, related_name='evidence_submissions')
    assessment_criterion = models.ForeignKey(AC, on_delete=models.CASCADE, related_name='evidence_submissions')
    evidence_detail = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('SUBMITTED', 'Submitted'), ('ACCEPTED', 'Accepted'), ('REJECTED', 'Rejected')], default='SUBMITTED')
    assessor = models.ForeignKey(
        UserBusiness, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assessed_submissions',
        verbose_name="Assessor"
    )

    def clean(self):
        try:
            learner = Learner.objects.get(
                user=self.user,
                qualification=self.assessment_criterion.learning_outcome.unit.qualification
            )
            if not learner.is_active:
                raise ValidationError("This learner is deactivated and cannot submit evidence for this qualification.")
            if self.assessor and self.assessor != learner.assessor:
                raise ValidationError("The assessor must be the one assigned to the learner.")
        except Learner.DoesNotExist:
            raise ValidationError("Only users assigned as Learners for this qualification can submit evidence.")

    def __str__(self):
        return f"Evidence for {self.assessment_criterion} by {self.user}"

    class Meta:
        verbose_name = "Evidence Submission"
        verbose_name_plural = "Evidence Submissions"
        indexes = [
            models.Index(fields=['user'], name='idx_evidence_user'),
            models.Index(fields=['assessment_criterion'], name='idx_evidence_ac'),
            models.Index(fields=['assessor'], name='idx_evidence_assessor'),  # New index
        ]


class EvidenceFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evidence_submission = models.ForeignKey(EvidenceSubmission, on_delete=models.CASCADE, related_name='files')
    evidence_file = models.FileField(upload_to='evidence/%Y/%m/%d/', validators=[validate_file], storage=S3Boto3Storage())
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"File for {self.evidence_submission}"

    class Meta:
        verbose_name = "Evidence File"
        verbose_name_plural = "Evidence Files"
        indexes = [
            models.Index(fields=['evidence_submission'], name='idx_evidence_file_submission'),
        ]

class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evidence_submission = models.ForeignKey(EvidenceSubmission, on_delete=models.CASCADE, related_name='feedbacks')
    feedback_detail = models.TextField()
    assessor = models.ForeignKey(UserBusiness, on_delete=models.CASCADE, related_name='given_feedbacks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.feedback_detail.strip():
            raise ValidationError("Feedback detail cannot be empty.")
        # Check if assessor is an Assessor for the qualification
        try:
            Assessor.objects.get(
                user=self.assessor,
                qualification=self.evidence_submission.assessment_criterion.learning_outcome.unit.qualification
            )
        except Assessor.DoesNotExist:
            raise ValidationError("Only users assigned as Assessors for this qualification can provide feedback.")

    def __str__(self):
        return f"Feedback: {self.feedback_detail[:50]}..."

    class Meta:
        verbose_name = "Feedback"
        verbose_name_plural = "Feedbacks"
        indexes = [
            models.Index(fields=['evidence_submission'], name='idx_feedback_evidence'),
            models.Index(fields=['assessor'], name='idx_feedback_assessor'),
        ]


class Sampling(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evidence_submission = models.ForeignKey(
        'EvidenceSubmission',
        on_delete=models.CASCADE,
        related_name='samplings'
    )
    iqa = models.ForeignKey(
        UserBusiness,
        on_delete=models.CASCADE,
        related_name='samplings'
    )
    sampling_type = models.CharField(
        max_length=20,
        choices=[('INTERIM', 'Interim'), ('SUMMATIVE', 'Summative')],
        default='INTERIM'
    )
    outcome = models.CharField(
        max_length=20,
        choices=[('OK', 'Ok'), ('NON_CONFORMANCE', 'Non-Conformance')],
        default='OK'
    )
    comments = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.sampling_type:
            raise ValidationError("Sampling type cannot be empty.")
        if not self.outcome:
            raise ValidationError("Outcome cannot be empty.")
        # Check if iqa is an IQA for the qualification
        try:
            IQA.objects.get(
                user=self.iqa,
                qualification=self.evidence_submission.assessment_criterion.learning_outcome.unit.qualification
            )
        except IQA.DoesNotExist:
            raise ValidationError("Only users assigned as IQAs for this qualification can perform sampling.")

    def __str__(self):
        return f"Sampling by {self.iqa} for {self.evidence_submission} ({self.sampling_type}, {self.outcome})"

    class Meta:
        verbose_name = "Sampling"
        verbose_name_plural = "Samplings"
        indexes = [
            models.Index(fields=['evidence_submission'], name='idx_sampling_evidence'),
            models.Index(fields=['iqa'], name='idx_sampling_iqa'),
        ]

COUNTRY_CHOICES = [
    ('AF', 'Afghanistan'),
    ('AL', 'Albania'),
    ('DZ', 'Algeria'),
    ('AS', 'American Samoa'),
    ('AD', 'Andorra'),
    ('AO', 'Angola'),
    ('AI', 'Anguilla'),
    ('AQ', 'Antarctica'),
    ('AG', 'Antigua and Barbuda'),
    ('AR', 'Argentina'),
    ('AM', 'Armenia'),
    ('AW', 'Aruba'),
    ('AU', 'Australia'),
    ('AT', 'Austria'),
    ('AZ', 'Azerbaijan'),
    ('BS', 'Bahamas'),
    ('BH', 'Bahrain'),
    ('BD', 'Bangladesh'),
    ('BB', 'Barbados'),
    ('BY', 'Belarus'),
    ('BE', 'Belgium'),
    ('BZ', 'Belize'),
    ('BJ', 'Benin'),
    ('BM', 'Bermuda'),
    ('BT', 'Bhutan'),
    ('BO', 'Bolivia'),
    ('BA', 'Bosnia and Herzegovina'),
    ('BW', 'Botswana'),
    ('BR', 'Brazil'),
    ('IO', 'British Indian Ocean Territory'),
    ('VG', 'British Virgin Islands'),
    ('BN', 'Brunei'),
    ('BG', 'Bulgaria'),
    ('BF', 'Burkina Faso'),
    ('BI', 'Burundi'),
    ('KH', 'Cambodia'),
    ('CM', 'Cameroon'),
    ('CA', 'Canada'),
    ('CV', 'Cape Verde'),
    ('KY', 'Cayman Islands'),
    ('CF', 'Central African Republic'),
    ('TD', 'Chad'),
    ('CL', 'Chile'),
    ('CN', 'China'),
    ('CX', 'Christmas Island'),
    ('CC', 'Cocos Islands'),
    ('CO', 'Colombia'),
    ('KM', 'Comoros'),
    ('CK', 'Cook Islands'),
    ('CR', 'Costa Rica'),
    ('HR', 'Croatia'),
    ('CU', 'Cuba'),
    ('CW', 'Curacao'),
    ('CY', 'Cyprus'),
    ('CZ', 'Czech Republic'),
    ('CD', 'Democratic Republic of the Congo'),
    ('DK', 'Denmark'),
    ('DJ', 'Djibouti'),
    ('DM', 'Dominica'),
    ('DO', 'Dominican Republic'),
    ('TL', 'East Timor'),
    ('EC', 'Ecuador'),
    ('EG', 'Egypt'),
    ('SV', 'El Salvador'),
    ('GQ', 'Equatorial Guinea'),
    ('ER', 'Eritrea'),
    ('EE', 'Estonia'),
    ('ET', 'Ethiopia'),
    ('FK', 'Falkland Islands'),
    ('FO', 'Faroe Islands'),
    ('FJ', 'Fiji'),
    ('FI', 'Finland'),
    ('FR', 'France'),
    ('PF', 'French Polynesia'),
    ('GA', 'Gabon'),
    ('GM', 'Gambia'),
    ('GE', 'Georgia'),
    ('DE', 'Germany'),
    ('GH', 'Ghana'),
    ('GI', 'Gibraltar'),
    ('GR', 'Greece'),
    ('GL', 'Greenland'),
    ('GD', 'Grenada'),
    ('GU', 'Guam'),
    ('GT', 'Guatemala'),
    ('GG', 'Guernsey'),
    ('GN', 'Guinea'),
    ('GW', 'Guinea-Bissau'),
    ('GY', 'Guyana'),
    ('HT', 'Haiti'),
    ('HN', 'Honduras'),
    ('HK', 'Hong Kong'),
    ('HU', 'Hungary'),
    ('IS', 'Iceland'),
    ('IN', 'India'),
    ('ID', 'Indonesia'),
    ('IR', 'Iran'),
    ('IQ', 'Iraq'),
    ('IE', 'Ireland'),
    ('IM', 'Isle of Man'),
    ('IL', 'Israel'),
    ('IT', 'Italy'),
    ('CI', 'Ivory Coast'),
    ('JM', 'Jamaica'),
    ('JP', 'Japan'),
    ('JE', 'Jersey'),
    ('JO', 'Jordan'),
    ('KZ', 'Kazakhstan'),
    ('KE', 'Kenya'),
    ('KI', 'Kiribati'),
    ('XK', 'Kosovo'),
    ('KW', 'Kuwait'),
    ('KG', 'Kyrgyzstan'),
    ('LA', 'Laos'),
    ('LV', 'Latvia'),
    ('LB', 'Lebanon'),
    ('LS', 'Lesotho'),
    ('LR', 'Liberia'),
    ('LY', 'Libya'),
    ('LI', 'Liechtenstein'),
    ('LT', 'Lithuania'),
    ('LU', 'Luxembourg'),
    ('MO', 'Macau'),
    ('MK', 'Macedonia'),
    ('MG', 'Madagascar'),
    ('MW', 'Malawi'),
    ('MY', 'Malaysia'),
    ('MV', 'Maldives'),
    ('ML', 'Mali'),
    ('MT', 'Malta'),
    ('MH', 'Marshall Islands'),
    ('MR', 'Mauritania'),
    ('MU', 'Mauritius'),
    ('YT', 'Mayotte'),
    ('MX', 'Mexico'),
    ('FM', 'Micronesia'),
    ('MD', 'Moldova'),
    ('MC', 'Monaco'),
    ('MN', 'Mongolia'),
    ('ME', 'Montenegro'),
    ('MS', 'Montserrat'),
    ('MA', 'Morocco'),
    ('MZ', 'Mozambique'),
    ('MM', 'Myanmar'),
    ('NA', 'Namibia'),
    ('NR', 'Nauru'),
    ('NP', 'Nepal'),
    ('NL', 'Netherlands'),
    ('NC', 'New Caledonia'),
    ('NZ', 'New Zealand'),
    ('NI', 'Nicaragua'),
    ('NE', 'Niger'),
    ('NG', 'Nigeria'),
    ('NU', 'Niue'),
    ('KP', 'North Korea'),
    ('MP', 'Northern Mariana Islands'),
    ('NO', 'Norway'),
    ('OM', 'Oman'),
    ('PK', 'Pakistan'),
    ('PW', 'Palau'),
    ('PS', 'Palestine'),
    ('PA', 'Panama'),
    ('PG', 'Papua New Guinea'),
    ('PY', 'Paraguay'),
    ('PE', 'Peru'),
    ('PH', 'Philippines'),
    ('PN', 'Pitcairn'),
    ('PL', 'Poland'),
    ('PT', 'Portugal'),
    ('PR', 'Puerto Rico'),
    ('QA', 'Qatar'),
    ('CG', 'Republic of the Congo'),
    ('RE', 'Reunion'),
    ('RO', 'Romania'),
    ('RU', 'Russia'),
    ('RW', 'Rwanda'),
    ('BL', 'Saint Barthelemy'),
    ('SH', 'Saint Helena'),
    ('KN', 'Saint Kitts and Nevis'),
    ('LC', 'Saint Lucia'),
    ('MF', 'Saint Martin'),
    ('PM', 'Saint Pierre and Miquelon'),
    ('VC', 'Saint Vincent and the Grenadines'),
    ('WS', 'Samoa'),
    ('SM', 'San Marino'),
    ('ST', 'Sao Tome and Principe'),
    ('SA', 'Saudi Arabia'),
    ('SN', 'Senegal'),
    ('RS', 'Serbia'),
    ('SC', 'Seychelles'),
    ('SL', 'Sierra Leone'),
    ('SG', 'Singapore'),
    ('SX', 'Sint Maarten'),
    ('SK', 'Slovakia'),
    ('SI', 'Slovenia'),
    ('SB', 'Solomon Islands'),
    ('SO', 'Somalia'),
    ('ZA', 'South Africa'),
    ('KR', 'South Korea'),
    ('SS', 'South Sudan'),
    ('ES', 'Spain'),
    ('LK', 'Sri Lanka'),
    ('SD', 'Sudan'),
    ('SR', 'Suriname'),
    ('SJ', 'Svalbard and Jan Mayen'),
    ('SZ', 'Swaziland'),
    ('SE', 'Sweden'),
    ('CH', 'Switzerland'),
    ('SY', 'Syria'),
    ('TW', 'Taiwan'),
    ('TJ', 'Tajikistan'),
    ('TZ', 'Tanzania'),
    ('TH', 'Thailand'),
    ('TG', 'Togo'),
    ('TK', 'Tokelau'),
    ('TO', 'Tonga'),
    ('TT', 'Trinidad and Tobago'),
    ('TN', 'Tunisia'),
    ('TR', 'Turkey'),
    ('TM', 'Turkmenistan'),
    ('TC', 'Turks and Caicos Islands'),
    ('TV', 'Tuvalu'),
    ('VI', 'U.S. Virgin Islands'),
    ('UG', 'Uganda'),
    ('UA', 'Ukraine'),
    ('AE', 'United Arab Emirates'),
    ('GB', 'United Kingdom'),
    ('US', 'United States'),
    ('UY', 'Uruguay'),
    ('UZ', 'Uzbekistan'),
    ('VU', 'Vanuatu'),
    ('VA', 'Vatican'),
    ('VE', 'Venezuela'),
    ('VN', 'Vietnam'),
    ('WF', 'Wallis and Futuna'),
    ('EH', 'Western Sahara'),
    ('YE', 'Yemen'),
    ('ZM', 'Zambia'),
    ('ZW', 'Zimbabwe'),
]

# Ethnicity choices
ETHNICITY_CHOICES = [
    ('PREFER_NOT_TO_SAY', 'Prefer not to say'),
    ('PAKISTANI', 'Pakistani'),
    ('INDIAN', 'Indian'),
    ('ARAB', 'Arab'),
    ('BANGLADESHI', 'Bangladeshi'),
    ('CHINESE', 'Chinese'),
    ('BLACK_AFRICAN', 'Black African'),
    ('BLACK_CARIBBEAN', 'Black Caribbean'),
    ('WHITE_BRITISH', 'White British'),
    ('WHITE_IRISH', 'White Irish'),
    ('WHITE_OTHER', 'White Other'),
    ('ASIAN_OTHER', 'Asian Other'),
    ('MIXED_WHITE_BLACK', 'Mixed White and Black'),
    ('MIXED_WHITE_ASIAN', 'Mixed White and Asian'),
    ('MIXED_OTHER', 'Mixed Other'),
    ('OTHER', 'Other'),
]

# ... (previous imports and other models remain unchanged)

class Learner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserBusiness, on_delete=models.CASCADE, related_name='learner_assignments')
    qualification = models.ForeignKey(Qual, on_delete=models.CASCADE, related_name='learners')
    assessor = models.ForeignKey(
        UserBusiness, on_delete=models.SET_NULL, null=True, related_name='assigned_learners_as_assessor',
        verbose_name="Assigned Assessor"
    )
    iqa = models.ForeignKey(
        UserBusiness, on_delete=models.SET_NULL, null=True, related_name='assigned_learners_as_iqa',
        verbose_name="Assigned IQA"
    )
    dob = models.DateField(null=True, blank=True, verbose_name="Date of Birth")
    disability = models.BooleanField(default=False, verbose_name="Disability")
    address = models.TextField(blank=True, verbose_name="Address")
    batch_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Batch #")
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ],
        verbose_name="Phone Number"
    )
    date_of_registration = models.DateField(default=timezone.now, verbose_name="Date of Registration")
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=True, null=True, verbose_name="Country")
    ethnicity = models.CharField(max_length=50, choices=ETHNICITY_CHOICES, blank=True, null=True, verbose_name="Ethnicity")
    signed_off = models.BooleanField(default=False, verbose_name="Signed Off")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, verbose_name="Is Active")

    def clean(self):
        # Existing role constraints
        if Assessor.objects.filter(user=self.user, qualification=self.qualification).exists():
            raise ValidationError("A learner cannot be an Assessor for the same qualification.")
        if IQA.objects.filter(user=self.user, qualification=self.qualification).exists():
            raise ValidationError("A learner cannot be an IQA for the same qualification.")

        # Validate Assessor
        if self.assessor and not Assessor.objects.filter(
            user=self.assessor, qualification=self.qualification
        ).exists():
            raise ValidationError("The selected Assessor is not assigned to this qualification.")

        # Validate IQA
        if self.iqa and not IQA.objects.filter(
            user=self.iqa, qualification=self.qualification
        ).exists():
            raise ValidationError("The selected IQA is not assigned to this qualification.")

        # Validate date_of_registration
        if self.date_of_registration and self.date_of_registration > timezone.now().date():
            raise ValidationError("Date of registration cannot be in the future.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        batch = f", Batch: {self.batch_number}" if self.batch_number else ""
        return f"{self.user} as Learner for {self.qualification} ({status}{batch})"

    class Meta:
        verbose_name = "Learner"
        verbose_name_plural = "Learners"
        constraints = [
            models.UniqueConstraint(fields=['user', 'qualification'], name='unique_learner_qualification'),
        ]
        indexes = [
            models.Index(fields=['user'], name='idx_learner_user'),
            models.Index(fields=['qualification'], name='idx_learner_qualification'),
            models.Index(fields=['assessor'], name='idx_learner_assessor'),
            models.Index(fields=['iqa'], name='idx_learner_iqa'),
            models.Index(fields=['is_active'], name='idx_learner_is_active'),
            models.Index(fields=['batch_number'], name='idx_learner_batch_number'),
        ]

class Assessor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserBusiness, on_delete=models.CASCADE, related_name='assessor_assignments')
    qualification = models.ForeignKey(Qual, on_delete=models.CASCADE, related_name='assessors')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Ensure user is not an IQA for this qualification in the same business
        if IQA.objects.filter(user=self.user, qualification=self.qualification).exists():
            raise ValidationError(
                "A user cannot be both an Assessor and an IQA for the same qualification in the same business."
            )
        # Ensure user is not a Learner for this qualification
        if Learner.objects.filter(user=self.user, qualification=self.qualification).exists():
            raise ValidationError("An Assessor cannot be a Learner for the same qualification.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Enforce clean() validation
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} as Assessor for {self.qualification}"

    class Meta:
        verbose_name = "Assessor"
        verbose_name_plural = "Assessors"
        constraints = [
            models.UniqueConstraint(fields=['user', 'qualification'], name='unique_assessor_qualification'),
        ]
        indexes = [
            models.Index(fields=['user'], name='idx_assessor_user'),
            models.Index(fields=['qualification'], name='idx_assessor_qualification'),
        ]

class IQA(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserBusiness, on_delete=models.CASCADE, related_name='iqa_assignments')
    qualification = models.ForeignKey(Qual, on_delete=models.CASCADE, related_name='iqas')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Ensure user is not an Assessor for this qualification in the same business
        if Assessor.objects.filter(user=self.user, qualification=self.qualification).exists():
            raise ValidationError(
                "A user cannot be both an IQA and an Assessor for the same qualification in the same business."
            )
        # Ensure user is not a Learner for this qualification
        if Learner.objects.filter(user=self.user, qualification=self.qualification).exists():
            raise ValidationError("An IQA cannot be a Learner for the same qualification.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Enforce clean() validation
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} as IQA for {self.qualification}"

    class Meta:
        verbose_name = "IQA"
        verbose_name_plural = "IQAs"
        constraints = [
            models.UniqueConstraint(fields=['user', 'qualification'], name='unique_iqa_qualification'),
        ]
        indexes = [
            models.Index(fields=['user'], name='idx_iqa_user'),
            models.Index(fields=['qualification'], name='idx_iqa_qualification'),
        ]

class EQA(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.UserBusiness', on_delete=models.CASCADE, related_name='eqa_assignments')
    qualification = models.ForeignKey('qualifications.Qual', on_delete=models.CASCADE, related_name='eqas')
    learners = models.ManyToManyField('qualifications.Learner', related_name='eqas', blank=True)  # New field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Ensure user is not a Learner, Assessor, or IQA for the same qualification in the same business
        if Learner.objects.filter(user=self.user, qualification=self.qualification).exists():
            raise ValidationError("An EQA cannot be a Learner for the same qualification.")
        if Assessor.objects.filter(user=self.user, qualification=self.qualification).exists():
            raise ValidationError("An EQA cannot be an Assessor for the same qualification.")
        if IQA.objects.filter(user=self.user, qualification=self.qualification).exists():
            raise ValidationError("An EQA cannot be an IQA for the same qualification.")

        # Validate that assigned learners belong to the same qualification
        for learner in self.learners.all():
            if learner.qualification != self.qualification:
                raise ValidationError(f"Learner {learner} is not assigned to qualification {self.qualification}.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Enforce clean() validation
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} as EQA for {self.qualification}"

    class Meta:
        verbose_name = "EQA"
        verbose_name_plural = "EQAs"
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'qualification'],
                name='unique_eqa_qualification'
            ),
        ]
        indexes = [
            models.Index(fields=['user'], name='idx_eqa_user'),
            models.Index(fields=['qualification'], name='idx_eqa_qualification'),
        ]

class ResourceFolder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    business = models.ForeignKey('users.Business', on_delete=models.CASCADE, related_name='resource_folders')
    qualifications = models.ManyToManyField('Qual', related_name='resource_folders')
    visible_to_roles = models.JSONField(default=list)  # Stores list of roles, e.g., ['LEARNER', 'ASSESSOR']
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.name.strip():
            raise ValidationError("Folder name cannot be empty.")
        if len(self.name) > 200:
            raise ValidationError("Folder name cannot exceed 200 characters.")
        # Validate roles
        valid_roles = [role[0] for role in ROLE_TYPES]
        for role in self.visible_to_roles:
            if role not in valid_roles:
                raise ValidationError(f"Invalid role: {role}. Allowed roles are {', '.join(valid_roles)}.")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Resource Folder"
        verbose_name_plural = "Resource Folders"
        indexes = [
            models.Index(fields=['business'], name='idx_resource_folder_business'),
        ]

class ResourceFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folder = models.ForeignKey(ResourceFolder, on_delete=models.CASCADE, related_name='files')
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='resources/%Y/%m/%d/', validators=[validate_file], storage=S3Boto3Storage())
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.title.strip():
            raise ValidationError("File title cannot be empty.")
        if len(self.title) > 200:
            raise ValidationError("File title cannot exceed 200 characters.")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Resource File"
        verbose_name_plural = "Resource Files"
        indexes = [
            models.Index(fields=['folder'], name='idx_resource_file_folder'),
        ]


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.UserBusiness', on_delete=models.CASCADE, related_name='notifications')
    evidence_submission = models.ForeignKey('EvidenceSubmission', on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if not self.message.strip():
            raise ValidationError("Notification message cannot be empty.")
        # Validate learner assignment only if evidence_submission is provided
        if self.evidence_submission:
            try:
                Learner.objects.get(
                    user=self.user,
                    qualification=self.evidence_submission.assessment_criterion.learning_outcome.unit.qualification
                )
            except Learner.DoesNotExist:
                raise ValidationError("Notifications can only be sent to users assigned as Learners for the qualification.")

    def __str__(self):
        return f"Notification for {self.user}: {self.message[:50]}..."

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=['user'], name='idx_notification_user'),
            models.Index(fields=['evidence_submission'], name='idx_notification_submission'),
            models.Index(fields=['is_read'], name='idx_notification_is_read'),
        ]

class IQAFeedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sampling = models.ForeignKey('Sampling', on_delete=models.CASCADE, related_name='iqa_feedbacks')
    assessor = models.ForeignKey(UserBusiness, on_delete=models.CASCADE, related_name='iqa_feedbacks_received')
    feedback = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.feedback.strip():
            raise ValidationError("Feedback detail cannot be empty.")
        try:
            Assessor.objects.get(
                user=self.assessor,
                qualification=self.sampling.evidence_submission.assessment_criterion.learning_outcome.unit.qualification
            )
        except Assessor.DoesNotExist:
            raise ValidationError("Only users assigned as Assessors for this qualification can receive IQA feedback.")

    def __str__(self):
        return f"IQA Feedback for {self.sampling} to {self.assessor}"

    class Meta:
        db_table = 'qualifications_iqa_feedback'
        indexes = [
            models.Index(fields=['sampling'], name='idx_iqa_feedback_sampling'),
            models.Index(fields=['assessor'], name='idx_iqa_feedback_assessor'),
        ]


class IQAFeedbackToAssessor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    iqa = models.ForeignKey(
        UserBusiness,
        on_delete=models.CASCADE,
        related_name='iqa_feedbacks_given'
    )
    assessor = models.ForeignKey(
        UserBusiness,
        on_delete=models.CASCADE,
        related_name='iqa_assessor_feedbacks_received'  # Changed related_name
    )
    sampling_type = models.CharField(
        max_length=20,
        choices=[('INTERIM', 'Interim'), ('SUMMATIVE', 'Summative')],
        default='INTERIM'
    )
    sampling_date = models.DateField()
    comments = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.sampling_type:
            raise ValidationError("Sampling type cannot be empty.")
        if not self.sampling_date:
            raise ValidationError("Sampling date cannot be empty.")
        if not self.comments.strip():
            raise ValidationError("Feedback comments cannot be empty.")
        # Verify IQA and assessor roles
        if not IQA.objects.filter(user=self.iqa).exists():
            raise ValidationError("The selected IQA user is not assigned as an IQA.")
        if not Assessor.objects.filter(user=self.assessor).exists():
            raise ValidationError("The selected user is not assigned as an Assessor.")

    def __str__(self):
        return f"IQA Feedback from {self.iqa} to {self.assessor} ({self.sampling_type}, {self.sampling_date})"

    class Meta:
        verbose_name = "IQA Feedback to Assessor"
        verbose_name_plural = "IQA Feedbacks to Assessors"
        indexes = [
            models.Index(fields=['iqa'], name='idx_iqa_feedback_iqa'),
            models.Index(fields=['assessor'], name='idx_iqa_feedback_to_assessor'),  # Changed index name
            models.Index(fields=['created_at'], name='idx_iqa_feedback_created_at'),
        ]

class DocumentRequirement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qualification = models.ForeignKey(Qual, on_delete=models.CASCADE, related_name='document_requirements')
    title = models.CharField(max_length=200)
    description = models.TextField()
    template = models.FileField(upload_to='document_templates/%Y/%m/%d/', validators=[validate_file], blank=True, null=True, storage=S3Boto3Storage())
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if not self.title.strip():
            raise ValidationError("Document title cannot be empty.")
        if len(self.title) > 200:
            raise ValidationError("Document title cannot exceed 200 characters.")
        if not self.description.strip():
            raise ValidationError("Description cannot be empty.")

    def __str__(self):
        return f"{self.title} for {self.qualification}"

    class Meta:
        verbose_name = "Document Requirement"
        verbose_name_plural = "Document Requirements"
        indexes = [
            models.Index(fields=['qualification'], name='idx_doc_req_qual'),
        ]

class LearnerDocumentSubmission(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name='document_submissions')
    document_requirement = models.ForeignKey(DocumentRequirement, on_delete=models.CASCADE, related_name='submissions')
    document_file = models.FileField(upload_to='learner_documents/%Y/%m/%d/', validators=[validate_file], storage=S3Boto3Storage())
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    comments = models.TextField(blank=True, null=True)
    assessor = models.ForeignKey('users.UserBusiness', on_delete=models.SET_NULL, related_name='document_reviews', null=True, blank=True)

    def clean(self):
        # Ensure learner is active and assigned to the qualification
        if not self.learner.is_active:
            raise ValidationError("This learner is deactivated and cannot submit documents.")
        if self.learner.qualification != self.document_requirement.qualification:
            raise ValidationError("Learner is not assigned to the qualification for this document requirement.")
        # Ensure comments are provided if status is REJECTED
        if self.status == 'REJECTED' and not self.comments:
            raise ValidationError("Comments are required when rejecting a document.")

    def save(self, *args, **kwargs):
        # Ensure assessor is set for non-PENDING status before saving
        if self.status != 'PENDING' and not self.assessor:
            raise ValidationError("An assessor must be assigned when accepting or rejecting a document.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Submission of {self.document_requirement.title} by {self.learner.user} ({self.status})"

    class Meta:
        verbose_name = "Learner Document Submission"
        verbose_name_plural = "Learner Document Submissions"
        constraints = [
            models.UniqueConstraint(fields=['learner', 'document_requirement'], name='unique_learner_doc_submission'),
        ]


class IQADocumentRemark(models.Model):
    REMARK_CHOICES = (
        ('OK', 'OK'),
        ('NON_CONFORMANCE', 'Non-Conformance'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey('LearnerDocumentSubmission', on_delete=models.CASCADE, related_name='iqa_remarks')
    iqa = models.ForeignKey('users.UserBusiness', on_delete=models.CASCADE, related_name='iqa_document_remarks')
    remark = models.CharField(max_length=20, choices=REMARK_CHOICES, default='OK')
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.remark == 'NON_CONFORMANCE' and not self.comments:
            raise ValidationError("Comments are required for Non-Conformance remarks.")

    def __str__(self):
        return f"IQA Remark for {self.submission.document_requirement.title} by {self.iqa}: {self.remark}"

    class Meta:
        verbose_name = "IQA Document Remark"
        verbose_name_plural = "IQA Document Remarks"
        constraints = [
            models.UniqueConstraint(fields=['submission', 'iqa'], name='unique_iqa_submission_remark'),
        ]
        indexes = [
            models.Index(fields=['submission'], name='idx_iqa_remark_submission'),
            models.Index(fields=['iqa'], name='idx_iqa_remark_iqa'),
        ]


class LearnerDocsByAssessor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    learner = models.ForeignKey('qualifications.Learner', on_delete=models.CASCADE, related_name='assessor_documents')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='learner_docs/%Y/%m/%d/', storage=S3Boto3Storage())
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_documents'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Learner Document by Assessor'
        verbose_name_plural = 'Learner Documents by Assessor'

    def __str__(self):
        return f"{self.title} - {self.learner}"
    

class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(UserBusiness, on_delete=models.CASCADE, related_name='sent_messages')
    subject = models.CharField(max_length=255)
    body = models.TextField()
    attachment = models.FileField(
        upload_to='message_attachments/%Y/%m/%d/',
        blank=True,
        null=True,
        validators=[validate_file],
        storage=S3Boto3Storage()
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    qualification = models.ForeignKey('Qual', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.subject} from {self.sender} at {self.sent_at}"

    class Meta:
        ordering = ['-sent_at']

class MessageRecipient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='recipients')
    recipient = models.ForeignKey(UserBusiness, on_delete=models.CASCADE, related_name='received_messages')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.message} to {self.recipient} (Read: {self.is_read})"

    class Meta:
        unique_together = ['message', 'recipient']