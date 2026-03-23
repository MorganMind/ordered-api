"""
Technician onboarding service — state transitions and eligibility checks.

Also hosts technician application → User + TechnicianProfile conversion
(application snapshot, Supabase provisioning, audit events).

All onboarding state mutations go through this service. The state machine
in apps.core.state_machine enforces valid transitions; this service adds
business rules (required-field checks, timestamps, event logging).
"""
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import structlog
from django.db import DatabaseError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.state_machine import get_state_machine
from apps.events.models import EntityType, EventType
from apps.events.services import event_service
from apps.jobs.models import Skill
from apps.technicians.models import (
    ApplicationStatus,
    OnboardingStatus,
    ServiceRegion,
    TechnicianApplication,
    TechnicianProfile,
    ONBOARDING_REQUIREMENTS,
)
from apps.users.models import User, UserRole, UserStatus
from apps.users.services.auth import SupabaseAuthService

logger = structlog.get_logger(__name__)

_machine = get_state_machine("technician_onboarding")


def _choice_as_str(value):
    """Coerce TextChoices / enums to plain str for JSONB and event payloads."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "value", str(value))


class TechnicianOnboardingService:
    """Service layer for technician onboarding operations."""

    # ── Eligibility check (used by permission class + service layer) ──

    @staticmethod
    def check_eligibility(user) -> TechnicianProfile:
        """
        Verify that a technician user is eligible to participate in jobs.

        Returns the profile if eligible.
        Raises TechnicianNotEligibleError if not.
        Does nothing for non-technician roles.
        """
        from apps.users.models import UserRole
        from apps.core.exceptions import TechnicianNotEligibleError

        if user.role != UserRole.TECHNICIAN:
            return None

        try:
            profile = user.technician_profile
        except TechnicianProfile.DoesNotExist:
            # Build missing fields from requirements
            missing_fields = [
                {"key": req["key"], "label": req["label"], "type": req["type"]}
                for req in ONBOARDING_REQUIREMENTS
                if req.get("required", True)
            ]
            raise TechnicianNotEligibleError(
                onboarding_status=OnboardingStatus.PENDING_ONBOARDING,
                missing_fields=missing_fields,
            )

        if not profile.is_eligible:
            raise TechnicianNotEligibleError(
                onboarding_status=profile.onboarding_status,
                missing_fields=profile.get_missing_onboarding_fields(),
                suspension_reason=(
                    profile.suspension_reason
                    if profile.onboarding_status == OnboardingStatus.SUSPENDED
                    else ""
                ),
            )

        return profile

    # ── State transitions ──

    @staticmethod
    def submit_for_review(profile: TechnicianProfile, actor=None) -> TechnicianProfile:
        """
        Technician submits their profile for admin review.

        Requires all ONBOARDING_REQUIREMENTS to be satisfied.
        """
        # Validate required fields are present
        missing = profile.get_missing_onboarding_fields()
        if missing:
            raise ValidationError({
                "error": {
                    "code": "onboarding_fields_incomplete",
                    "message": "Required onboarding fields are missing.",
                    "missing_fields": missing,
                }
            })

        # Validate state transition
        _machine.validate_transition(
            from_state=profile.onboarding_status,
            to_state=OnboardingStatus.SUBMITTED,
            entity_id=str(profile.id),
        )

        with transaction.atomic():
            profile.onboarding_status = OnboardingStatus.SUBMITTED
            profile.submitted_at = timezone.now()
            profile.save(update_fields=[
                "onboarding_status", "submitted_at", "updated_at",
            ])

            logger.info(
                "technician_onboarding_submitted",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                tenant_id=str(profile.tenant_id),
            )

        return profile

    @staticmethod
    def approve(
        profile: TechnicianProfile,
        reviewer,
        notes: str = "",
    ) -> TechnicianProfile:
        """Admin approves a submitted technician profile."""
        _machine.validate_transition(
            from_state=profile.onboarding_status,
            to_state=OnboardingStatus.ACTIVE,
            entity_id=str(profile.id),
        )

        with transaction.atomic():
            profile.onboarding_status = OnboardingStatus.ACTIVE
            profile.reviewed_at = timezone.now()
            profile.reviewed_by = reviewer
            profile.activated_at = timezone.now()
            profile.review_notes = notes
            # Clear any previous suspension
            profile.suspension_reason = ""
            profile.save(update_fields=[
                "onboarding_status",
                "reviewed_at",
                "reviewed_by",
                "activated_at",
                "review_notes",
                "suspension_reason",
                "updated_at",
            ])

            logger.info(
                "technician_onboarding_approved",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                reviewer_id=str(reviewer.id),
                tenant_id=str(profile.tenant_id),
            )

        return profile

    @staticmethod
    def request_changes(
        profile: TechnicianProfile,
        reviewer,
        notes: str = "",
    ) -> TechnicianProfile:
        """Admin sends a submitted profile back for revisions."""
        _machine.validate_transition(
            from_state=profile.onboarding_status,
            to_state=OnboardingStatus.PENDING_ONBOARDING,
            entity_id=str(profile.id),
        )

        with transaction.atomic():
            profile.onboarding_status = OnboardingStatus.PENDING_ONBOARDING
            profile.reviewed_at = timezone.now()
            profile.reviewed_by = reviewer
            profile.review_notes = notes
            # Clear submitted_at so they can re-submit
            profile.submitted_at = None
            profile.save(update_fields=[
                "onboarding_status",
                "reviewed_at",
                "reviewed_by",
                "review_notes",
                "submitted_at",
                "updated_at",
            ])

            logger.info(
                "technician_onboarding_changes_requested",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                reviewer_id=str(reviewer.id),
                tenant_id=str(profile.tenant_id),
            )

        return profile

    @staticmethod
    def suspend(
        profile: TechnicianProfile,
        actor,
        reason: str = "",
    ) -> TechnicianProfile:
        """Admin suspends a technician — blocks all job operations."""
        _machine.validate_transition(
            from_state=profile.onboarding_status,
            to_state=OnboardingStatus.SUSPENDED,
            entity_id=str(profile.id),
        )

        with transaction.atomic():
            profile.onboarding_status = OnboardingStatus.SUSPENDED
            profile.suspended_at = timezone.now()
            profile.suspension_reason = reason
            profile.save(update_fields=[
                "onboarding_status",
                "suspended_at",
                "suspension_reason",
                "updated_at",
            ])

            logger.info(
                "technician_suspended",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                actor_id=str(actor.id),
                reason=reason,
                tenant_id=str(profile.tenant_id),
            )

        return profile

    @staticmethod
    def reactivate(
        profile: TechnicianProfile,
        actor,
        notes: str = "",
    ) -> TechnicianProfile:
        """Admin reactivates a suspended technician."""
        _machine.validate_transition(
            from_state=profile.onboarding_status,
            to_state=OnboardingStatus.ACTIVE,
            entity_id=str(profile.id),
        )

        with transaction.atomic():
            profile.onboarding_status = OnboardingStatus.ACTIVE
            profile.activated_at = timezone.now()
            profile.suspension_reason = ""
            profile.review_notes = notes
            profile.save(update_fields=[
                "onboarding_status",
                "activated_at",
                "suspension_reason",
                "review_notes",
                "updated_at",
            ])

            logger.info(
                "technician_reactivated",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                actor_id=str(actor.id),
                tenant_id=str(profile.tenant_id),
            )

        return profile


# ═══════════════════════════════════════════════════════════════════════════════
# Technician application → technician conversion
# ═══════════════════════════════════════════════════════════════════════════════


class ApplicationConversionError(Exception):
    """Raised when an application cannot be converted."""

    def __init__(self, message: str, code: str = "conversion_failed"):
        self.code = code
        super().__init__(message)


@dataclass
class ConversionResult:
    application: TechnicianApplication
    user: User
    profile: TechnicianProfile
    user_created: bool
    supabase_created: bool


def build_application_snapshot(app: TechnicianApplication) -> dict:
    """
    Freeze the application into a plain dict for outcome correlation.

    Shape is intentionally flat + stable so downstream analytics can
    rely on key paths without chasing schema drift.
    """
    return {
        "application_id": str(app.id),
        "application_form_id": (
            str(app.application_form_id) if app.application_form_id else None
        ),
        "schema_version": app.schema_version,
        "snapshot_at": timezone.now().isoformat(),
        "applicant_type": _choice_as_str(app.applicant_type),
        "identity": {
            "first_name": app.first_name,
            "last_name": app.last_name,
            "company_name": app.company_name,
            "email": app.email,
            "phone": app.phone,
        },
        "service_area": app.service_area or {},
        "availability": app.availability or {},
        "experience": app.experience or {},
        "capabilities": app.capabilities or {},
        "answers": app.answers or {},
        "source": app.source,
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "review": {
            "reviewer_notes": app.reviewer_notes,
            "rejection_reason": app.rejection_reason,
            "reviewed_by": str(app.reviewed_by_id) if app.reviewed_by_id else None,
            "reviewed_at": app.reviewed_at.isoformat() if app.reviewed_at else None,
        },
    }


class TechnicianApplicationConversionService:
    """
    Converts an approved TechnicianApplication into a User + TechnicianProfile.

    Supports two modes:
      • create  — provision a new Supabase user + local User (default)
      • link    — attach to an existing User in the same tenant
    """

    def __init__(self, *, actor: User, request=None):
        self.actor = actor
        self.request = request

    def convert(
        self,
        application: TechnicianApplication,
        *,
        existing_user_id: Optional[UUID] = None,
        create_supabase_account: bool = True,
        activate_immediately: bool = False,
        reviewer_notes: Optional[str] = None,
    ) -> ConversionResult:
        self._validate(application, existing_user_id)

        snapshot = build_application_snapshot(application)
        supabase_uid: Optional[str] = None
        supabase_created = False

        if existing_user_id is None and create_supabase_account:
            supabase_uid, supabase_created = self._provision_supabase(application)

        try:
            with transaction.atomic():
                if existing_user_id:
                    user, user_created = self._link_existing_user(
                        application, existing_user_id
                    )
                else:
                    user, user_created = self._create_user(
                        application, supabase_uid=supabase_uid
                    )

                profile = self._upsert_profile(
                    application, user, snapshot, activate_immediately
                )

                self._seed_skills_and_regions(application, user, profile)
                self._finalize_application(
                    application, user, profile, reviewer_notes
                )

        except Exception:
            if supabase_created and supabase_uid:
                self._rollback_supabase(supabase_uid)
            raise

        try:
            self._log_events(application, user, profile, user_created)
        except DatabaseError:
            logger.exception(
                "technician_conversion_audit_events_failed",
                application_id=str(application.id),
                tenant_id=str(application.tenant_id),
                user_id=str(user.id),
            )

        logger.info(
            "technician_application_converted",
            application_id=str(application.id),
            tenant_id=str(application.tenant_id),
            user_id=str(user.id),
            profile_id=str(profile.id),
            user_created=user_created,
            supabase_created=supabase_created,
            actor_id=str(self.actor.id),
        )

        return ConversionResult(
            application=application,
            user=user,
            profile=profile,
            user_created=user_created,
            supabase_created=supabase_created,
        )

    def _validate(
        self, app: TechnicianApplication, existing_user_id: Optional[UUID]
    ) -> None:
        if app.is_converted:
            raise ApplicationConversionError(
                "Application has already been converted.",
                code="already_converted",
            )

        if app.status not in {
            ApplicationStatus.APPROVED,
            ApplicationStatus.REVIEWING,
            ApplicationStatus.NEW,
        }:
            raise ApplicationConversionError(
                f"Cannot convert an application with status '{app.status}'.",
                code="invalid_status",
            )

        if existing_user_id:
            return

        clash = (
            User.objects.filter(
                tenant_id=app.tenant_id, email__iexact=app.email
            )
            .exclude(role=UserRole.TECHNICIAN)
            .first()
        )
        if clash:
            raise ApplicationConversionError(
                f"A user with email {app.email} already exists in this tenant "
                "with a non-technician role. Use link mode instead.",
                code="email_conflict",
            )

    def _provision_supabase(
        self, app: TechnicianApplication
    ) -> tuple[Optional[str], bool]:
        try:
            auth = SupabaseAuthService()
            res = auth.create_user(app.email)
            uid = res.get("id")
            return (str(uid) if uid is not None else None), True
        except Exception as e:
            logger.warning(
                "supabase_provisioning_failed_during_conversion",
                application_id=str(app.id),
                email=app.email,
                error=str(e),
            )
            return None, False

    def _rollback_supabase(self, supabase_uid: str) -> None:
        try:
            SupabaseAuthService().delete_user(supabase_uid)
            logger.info("supabase_user_rolled_back", supabase_uid=supabase_uid)
        except Exception as e:
            logger.error(
                "supabase_rollback_failed",
                supabase_uid=supabase_uid,
                error=str(e),
            )

    def _create_user(
        self, app: TechnicianApplication, *, supabase_uid: Optional[str]
    ) -> tuple[User, bool]:
        existing = User.objects.filter(
            tenant_id=app.tenant_id,
            email__iexact=app.email,
            role=UserRole.TECHNICIAN,
        ).first()
        if existing:
            if supabase_uid and not existing.supabase_uid:
                existing.supabase_uid = supabase_uid
                existing.save(update_fields=["supabase_uid", "updated_at"])
            return existing, False

        user = User.objects.create(
            tenant_id=app.tenant_id,
            email=app.email,
            first_name=app.first_name,
            last_name=app.last_name,
            phone=app.phone,
            role=UserRole.TECHNICIAN,
            status=UserStatus.PENDING,
            supabase_uid=supabase_uid,
            metadata={
                "origin": "technician_application",
                "application_id": str(app.id),
                "company_name": app.company_name,
                "applicant_type": _choice_as_str(app.applicant_type),
            },
        )
        return user, True

    def _link_existing_user(
        self, app: TechnicianApplication, user_id: UUID
    ) -> tuple[User, bool]:
        try:
            user = User.objects.select_for_update().get(
                id=user_id, tenant_id=app.tenant_id
            )
        except User.DoesNotExist:
            raise ApplicationConversionError(
                "Target user not found in this tenant.", code="user_not_found"
            )

        if user.role != UserRole.TECHNICIAN:
            user.role = UserRole.TECHNICIAN
            user.save(update_fields=["role", "updated_at"])

        dirty = []
        for fld in ("first_name", "last_name", "phone"):
            if not getattr(user, fld) and getattr(app, fld):
                setattr(user, fld, getattr(app, fld))
                dirty.append(fld)
        if dirty:
            dirty.append("updated_at")
            user.save(update_fields=dirty)

        return user, False

    def _upsert_profile(
        self,
        app: TechnicianApplication,
        user: User,
        snapshot: dict,
        activate_immediately: bool,
    ) -> TechnicianProfile:
        profile, _ = TechnicianProfile.objects.get_or_create(
            user=user,
            defaults={"tenant_id": app.tenant_id},
        )

        profile.tenant_id = app.tenant_id
        profile.application_snapshot = snapshot

        profile.additional_data = {
            **(profile.additional_data or {}),
            "declared_availability": app.availability or {},
            "declared_experience": app.experience or {},
            "declared_service_area": app.service_area or {},
            "declared_capabilities": app.capabilities or {},
            "applicant_type": _choice_as_str(app.applicant_type),
            "company_name": app.company_name,
        }

        if activate_immediately:
            profile.onboarding_status = OnboardingStatus.ACTIVE
            profile.activated_at = timezone.now()
            profile.reviewed_by = self.actor
            profile.reviewed_at = timezone.now()

        profile.save()
        return profile

    def _seed_skills_and_regions(
        self,
        app: TechnicianApplication,
        user: User,
        profile: TechnicianProfile,
    ) -> None:
        skill_keys = (app.capabilities or {}).get("skill_keys") or []
        if skill_keys:
            skills = Skill.objects.filter(key__in=skill_keys, is_active=True)
            if skills.exists():
                user.skills.add(*skills)

        region_keys = (app.service_area or {}).get("service_region_keys") or []
        if region_keys:
            regions = ServiceRegion.objects.filter(
                key__in=region_keys, is_active=True
            )
            if regions.exists():
                profile.service_regions.add(*regions)

    def _finalize_application(
        self,
        app: TechnicianApplication,
        user: User,
        profile: TechnicianProfile,
        reviewer_notes: Optional[str],
    ) -> None:
        now = timezone.now()

        app.status = ApplicationStatus.APPROVED
        app.status_changed_at = now
        app.reviewed_by = self.actor
        app.reviewed_at = now
        app.converted_user = user
        app.converted_technician_profile = profile
        app.converted_at = now
        app.converted_by = self.actor

        if reviewer_notes:
            stamp = now.strftime("%Y-%m-%d %H:%M")
            entry = f"[{stamp} · {self.actor.email}] {reviewer_notes.strip()}"
            app.reviewer_notes = (
                f"{app.reviewer_notes}\n{entry}" if app.reviewer_notes else entry
            )

        app.save()

    def _log_events(
        self,
        app: TechnicianApplication,
        user: User,
        profile: TechnicianProfile,
        user_created: bool,
    ) -> None:
        common_payload = {
            "application_id": str(app.id),
            "user_id": str(user.id),
            "profile_id": str(profile.id),
            "user_created": user_created,
            "applicant_type": _choice_as_str(app.applicant_type),
            "email": app.email,
        }

        event_service.log_event(
            event_type=EventType.TECHNICIAN_APPLICATION_CONVERTED,
            entity_type=EntityType.TECHNICIAN_APPLICATION,
            entity_id=app.id,
            payload=common_payload,
            actor=self.actor,
            tenant_id=app.tenant_id,
            request=self.request,
        )

        event_service.log_event(
            event_type=EventType.TECHNICIAN_PROFILE_CREATED,
            entity_type=EntityType.TECHNICIAN,
            entity_id=profile.id,
            payload={
                **common_payload,
                "onboarding_status": _choice_as_str(profile.onboarding_status),
            },
            actor=self.actor,
            tenant_id=app.tenant_id,
            request=self.request,
        )

        if user_created:
            event_service.log_event(
                event_type=EventType.USER_CREATED,
                entity_type=EntityType.USER,
                entity_id=user.id,
                payload={
                    "origin": "technician_application_conversion",
                    "application_id": str(app.id),
                    "role": _choice_as_str(user.role),
                },
                actor=self.actor,
                tenant_id=app.tenant_id,
                request=self.request,
            )
