import logging
from rest_framework import serializers
from .models import Qual, Unit, LO, AC, EvidenceSubmission
from django.db import transaction

logger = logging.getLogger('qualifications')

class ACSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False, allow_null=True)
    ac_detail = serializers.CharField()
    serial_number = serializers.FloatField(read_only=True)

    class Meta:
        model = AC
        fields = ['id', 'ac_detail', 'serial_number']

class LOSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False, allow_null=True)
    lo_detail = serializers.CharField()
    assessment_criteria = ACSerializer(many=True)
    serial_number = serializers.FloatField(read_only=True)

    class Meta:
        model = LO
        fields = ['id', 'lo_detail', 'assessment_criteria', 'serial_number']

    def get_assessment_criteria(self, obj):
        assessment_criteria = obj.assessment_criteria.all().order_by('serial_number')
        logger.debug(f"Fetched ACs for LO {obj.id}: {[ac.ac_detail for ac in assessment_criteria]}")
        return ACSerializer(assessment_criteria, many=True).data

class UnitSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False, allow_null=True)
    unit_title = serializers.CharField()
    unit_number = serializers.CharField()
    learning_outcomes = LOSerializer(many=True)
    serial_number = serializers.FloatField(read_only=True)

    class Meta:
        model = Unit
        fields = ['id', 'unit_title', 'unit_number', 'learning_outcomes', 'serial_number']

    def get_learning_outcomes(self, obj):
        learning_outcomes = obj.learning_outcomes.all().order_by('serial_number')
        return LOSerializer(learning_outcomes, many=True).data

class QualificationSerializer(serializers.ModelSerializer):
    units = UnitSerializer(many=True)
    qualification_title = serializers.CharField()
    qualification_number = serializers.CharField()
    awarding_body = serializers.CharField()

    class Meta:
        model = Qual
        fields = ['id', 'qualification_title', 'qualification_number', 'awarding_body', 'units']

    def validate_qualification_number(self, value):
        qualification = self.instance
        business = self.context.get('business')
        if not business:
            logger.error("Business context is missing for qualification number validation")
            raise serializers.ValidationError("Business context is required for validation.")
        qs = Qual.objects.filter(qualification_number=value, business=business)
        if qualification:
            qs = qs.exclude(id=qualification.id)
        if qs.exists():
            logger.warning(f"Attempted to use existing qualification number '{value}' for business {business.business_id}")
            raise serializers.ValidationError("A qualification with this number already exists for this business.")
        return value

    def create(self, validated_data):
        with transaction.atomic():
            units_data = validated_data.pop('units', [])
            business = self.context.get('business')
            validated_data['business'] = business
            qualification = Qual.objects.create(**validated_data)
            logger.info(f"Created qualification {qualification.id}")
            self._create_or_update_units(qualification, units_data)
            return qualification

    def update(self, instance, validated_data):
        with transaction.atomic():
            units_data = validated_data.pop('units', [])
            instance.qualification_title = validated_data.get('qualification_title', instance.qualification_title)
            instance.qualification_number = validated_data.get('qualification_number', instance.qualification_number)
            instance.awarding_body = validated_data.get('awarding_body', instance.awarding_body)
            instance.save()
            logger.info(f"Updating qualification {instance.id}")
            self._create_or_update_units(instance, units_data)
            return instance

    def _create_or_update_units(self, qualification, units_data):
        logger.debug(f"Creating/updating units for qualification: {qualification.id}")
        existing_units = {str(unit.id): unit for unit in qualification.units.all()}
        submitted_unit_ids = set(str(unit.get('id')) for unit in units_data if unit.get('id'))
        logger.debug(f"Existing unit IDs: {set(existing_units.keys())}, Submitted unit IDs: {submitted_unit_ids}")

        for unit_idx, unit_data in enumerate(units_data, 1):
            unit_id = str(unit_data.get('id')) if unit_data.get('id') else None
            lo_data = unit_data.pop('learning_outcomes', [])
            serial_number = float(unit_idx)
            logger.debug(f"Processing unit data with ID: {unit_id}, serial_number: {serial_number}")
            if unit_id and unit_id in existing_units:
                logger.debug(f"Updating existing unit: {unit_id}")
                unit = existing_units[unit_id]
                unit.unit_title = unit_data.get('unit_title', unit.unit_title)
                unit.unit_number = unit_data.get('unit_number', unit.unit_number)
                unit.serial_number = serial_number
                unit.save()
                del existing_units[unit_id]
            else:
                logger.debug(f"Creating new unit with data: {unit_data}")
                if 'id' in unit_data:
                    del unit_data['id']
                unit = Unit(
                    qualification=qualification,
                    unit_title=unit_data['unit_title'],
                    unit_number=unit_data['unit_number'],
                    serial_number=serial_number
                )
                unit.save()  # Save Unit before creating LOs
            self._create_or_update_learning_outcomes(unit, lo_data, unit_idx)

        for unit_id in existing_units:
            unit = existing_units[unit_id]
            submission_count = EvidenceSubmission.objects.filter(
                assessment_criterion__learning_outcome__unit=unit
            ).count()
            if submission_count > 0:
                logger.debug(f"Blocking deletion of unit {unit_id} due to {submission_count} submissions")
                raise serializers.ValidationError({
                    "units": "You cannot Edit this Qualification because there are Learners Submissions against this Qualification"
                })
            unit.delete()
            logger.debug(f"Deleted unit: {unit_id}")

    def _create_or_update_learning_outcomes(self, unit, learning_outcomes_data, unit_serial):
        logger.debug(f"Creating/updating LOs for unit: {unit.id}")
        existing_los = {str(lo.id): lo for lo in unit.learning_outcomes.all()}
        submitted_lo_ids = set(str(lo.get('id')) for lo in learning_outcomes_data if lo.get('id'))

        for lo_idx, lo_data in enumerate(learning_outcomes_data, 1):
            lo_id = str(lo_data.get('id')) if lo_data.get('id') else None
            ac_data = lo_data.pop('assessment_criteria', [])
            serial_number = float(f"{unit_serial}.{lo_idx}")
            logger.debug(f"Processing LO with ID: {lo_id}, serial_number: {serial_number}")
            
            if lo_id and lo_id in existing_los:
                lo = existing_los[lo_id]
                lo.lo_detail = lo_data.get('lo_detail', lo.lo_detail)
                lo.serial_number = serial_number
                lo.save()
                logger.debug(f"Updated LO: {lo.id}")
            else:
                if 'id' in lo_data:
                    del lo_data['id']
                lo = LO(
                    unit=unit,
                    lo_detail=lo_data['lo_detail'],
                    serial_number=serial_number
                )
                lo.save()  # Save LO before creating ACs
                logger.debug(f"Created LO: {lo.id}")
            
            self._create_or_update_assessment_criteria(lo, ac_data, unit_serial, lo_idx)
            
            if lo_id and lo_id in existing_los:
                del existing_los[lo_id]

        for lo_id in existing_los:
            lo = existing_los[lo_id]
            submission_count = EvidenceSubmission.objects.filter(
                assessment_criterion__learning_outcome=lo
            ).count()
            if submission_count > 0:
                logger.debug(f"Blocking deletion of LO {lo_id} due to {submission_count} submissions")
                raise serializers.ValidationError({
                    "learning_outcomes": "You cannot Edit this Qualification because there are Learners Submissions against this Qualification"
                })
            lo.delete()
            logger.debug(f"Deleted LO: {lo_id}")

    def _create_or_update_assessment_criteria(self, learning_outcome, ac_data, unit_serial, lo_idx):
        logger.debug(f"Creating/updating ACs for LO: {learning_outcome.id}")
        existing_acs = {str(ac.id): ac for ac in learning_outcome.assessment_criteria.all()}
        submitted_ac_ids = set(str(ac.get('id')) for ac in ac_data if ac.get('id'))

        for ac_idx, ac_data in enumerate(ac_data, 1):
            ac_id = str(ac_data.get('id')) if ac_data.get('id') else None
            serial_number = float(f"{unit_serial}.{lo_idx}{ac_idx}")
            logger.debug(f"Processing AC with ID: {ac_id}, serial_number: {serial_number}, detail: {ac_data['ac_detail']}")
            if ac_id and ac_id in existing_acs:
                logger.debug(f"Updating existing AC: {ac_id}")
                ac = existing_acs[ac_id]
                ac.ac_detail = ac_data.get('ac_detail', ac.ac_detail)
                ac.serial_number = serial_number
                ac.save()
                logger.debug(f"Updated AC: {ac.id}")
                del existing_acs[ac_id]
            else:
                logger.debug(f"Creating new AC with data: {ac_data}")
                if 'id' in ac_data:
                    del ac_data['id']
                ac = AC(
                    learning_outcome=learning_outcome,
                    ac_detail=ac_data['ac_detail'],
                    serial_number=serial_number
                )
                ac.save()
                logger.debug(f"Created AC: {ac.id}")

        for ac_id in existing_acs:
            ac = existing_acs[ac_id]
            submission_count = EvidenceSubmission.objects.filter(assessment_criterion=ac).count()
            if submission_count > 0:
                logger.debug(f"Blocking deletion of AC {ac_id} due to {submission_count} submissions")
                raise serializers.ValidationError({
                    "assessment_criteria": "You cannot Edit this Qualification because there are Learners Submissions against this Qualification"
                })
            ac.delete()
            logger.debug(f"Deleted AC: {ac_id}")

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        units = Unit.objects.filter(qualification=instance).order_by('serial_number')
        representation['units'] = UnitSerializer(units, many=True).data
        logger.debug(f"Returning qualification {instance.id} with units: {[u.unit_title for u in units]}")
        return representation