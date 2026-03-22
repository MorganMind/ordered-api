"""
Technician views for onboarding and profile management.
"""
from datetime import timedelta

import structlog
from django.db import models
from django.db.models import CharField, Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone
from django.utils.text import slugify
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.middleware import get_current_tenant_id
from apps.core.permissions import IsAdmin, IsTechnician

from .filters import TechnicianApplicationFilter
from apps.events.models import EntityType, EventType
from apps.events.services import event_service
from apps.jobs.models import Skill
from apps.jobs.serializers import SkillSerializer
from apps.tenants.models import Tenant, TenantStatus
from apps.users.models import User, UserRole
from apps.technicians.models import (
    ApplicationForm,
    ApplicationFormStatus,
    ApplicationStatus,
    OnboardingStatus,
    ServiceRegion,
    TechnicianApplication,
    TechnicianProfile,
    ONBOARDING_REQUIREMENTS,
)
from apps.technicians.serializers import (
    ApplicationFormCreateSerializer,
    ApplicationFormDetailSerializer,
    ApplicationFormListSerializer,
    ApplicationFormUpdateSerializer,
    ConversionResultSerializer,
    OnboardingRequirementsSerializer,
    ServiceRegionSerializer,
    TechnicianAdminDetailSerializer,
    TechnicianApplicationApproveSerializer,
    TechnicianApplicationConvertSerializer,
    TechnicianApplicationListSerializer,
    TechnicianApplicationRejectSerializer,
    TechnicianApplicationPublicSubmitSerializer,
    TechnicianApplicationReviewSerializer,
    TechnicianApplicationSerializer,
    TechnicianListSerializer,
    TechnicianOnboardingUpdateSerializer,
    TechnicianProfileReadSerializer,
    TechnicianReviewActionSerializer,
    TechnicianSubmitSerializer,
    TechnicianSuspendSerializer,
)
from apps.technicians.services import (
    ApplicationConversionError,
    TechnicianApplicationConversionService,
    TechnicianOnboardingService,
)

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICIAN SELF-SERVICE VIEWS
# ═══════════════════════════════════════════════════════════════════════════════


class TechnicianMeView(APIView):
    """
    Self-service endpoint for the logged-in technician's profile.

    GET  /api/v1/technicians/me/ - Get profile with onboarding progress
    PATCH /api/v1/technicians/me/ - Update onboarding fields
    """

    permission_classes = [IsAuthenticated, IsTechnician]

    def get(self, request):
        """Get the current technician's profile."""
        if request.user.role != UserRole.TECHNICIAN:
            return Response(
                {"error": {"code": "not_technician", "message": "This endpoint is for technicians only."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            profile = request.user.technician_profile
        except TechnicianProfile.DoesNotExist:
            return Response(
                {"error": {"code": "profile_not_found", "message": "Technician profile not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianProfileReadSerializer(profile)
        return Response(serializer.data)

    def patch(self, request):
        """Update onboarding fields."""
        if request.user.role != UserRole.TECHNICIAN:
            return Response(
                {"error": {"code": "not_technician", "message": "This endpoint is for technicians only."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            profile = request.user.technician_profile
        except TechnicianProfile.DoesNotExist:
            return Response(
                {"error": {"code": "profile_not_found", "message": "Technician profile not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianOnboardingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Track previous completion state for cascading effects
        was_complete = profile.has_completed_required_fields
        previous_status = profile.onboarding_status

        # Perform the update
        profile = serializer.update(profile, serializer.validated_data)

        # Handle cascading effects: if an active technician removes required
        # fields, they go back to pending_onboarding
        is_complete = profile.has_completed_required_fields

        if previous_status == OnboardingStatus.ACTIVE and was_complete and not is_complete:
            # Active technician broke their eligibility
            profile.onboarding_status = OnboardingStatus.PENDING_ONBOARDING
            profile.save(update_fields=["onboarding_status", "updated_at"])

            logger.warning(
                "technician_eligibility_lost",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                missing_fields=profile.get_missing_onboarding_fields(),
            )

        elif previous_status == OnboardingStatus.SUBMITTED and was_complete and not is_complete:
            # Submitted technician broke their completion — back to pending
            profile.onboarding_status = OnboardingStatus.PENDING_ONBOARDING
            profile.submitted_at = None
            profile.save(update_fields=["onboarding_status", "submitted_at", "updated_at"])

            logger.info(
                "technician_submission_reset",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
            )

        # Return updated profile
        response_serializer = TechnicianProfileReadSerializer(profile)
        return Response(response_serializer.data)


class TechnicianSubmitView(APIView):
    """
    Submit onboarding for admin review.

    POST /api/v1/technicians/me/submit/
    """

    permission_classes = [IsAuthenticated, IsTechnician]

    def post(self, request):
        if request.user.role != UserRole.TECHNICIAN:
            return Response(
                {"error": {"code": "not_technician", "message": "This endpoint is for technicians only."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            profile = request.user.technician_profile
        except TechnicianProfile.DoesNotExist:
            return Response(
                {"error": {"code": "profile_not_found", "message": "Technician profile not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianSubmitSerializer(
            data=request.data,
            context={"profile": profile},
        )
        serializer.is_valid(raise_exception=True)

        profile = TechnicianOnboardingService.submit_for_review(
            profile=profile,
            actor=request.user,
        )

        response_serializer = TechnicianProfileReadSerializer(profile)
        return Response(response_serializer.data)


# ═══════════════════════════════════════════════════════════════════════════════
# REFERENCE DATA VIEWS
# ═══════════════════════════════════════════════════════════════════════════════


class ServiceRegionListView(APIView):
    """
    List available service regions.

    GET /api/v1/technicians/service-regions/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        regions = ServiceRegion.objects.filter(is_active=True).order_by("state", "name")
        serializer = ServiceRegionSerializer(regions, many=True)

        # Group by state for frontend convenience
        grouped = {}
        for region in serializer.data:
            state = region["state"]
            if state not in grouped:
                grouped[state] = []
            grouped[state].append(region)

        return Response({
            "regions": serializer.data,
            "grouped_by_state": grouped,
            "states": sorted(grouped.keys()),
        })


class TechnicianSkillsListView(APIView):
    """
    List available skills for technicians.

    GET /api/v1/technicians/skills/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        skills = Skill.objects.filter(is_active=True).order_by("category", "label")
        serializer = SkillSerializer(skills, many=True)

        # Group by category
        grouped = {}
        for skill in serializer.data:
            category = skill["category"]
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(skill)

        return Response({
            "skills": serializer.data,
            "grouped_by_category": grouped,
            "categories": sorted(grouped.keys()),
        })


class OnboardingRequirementsView(APIView):
    """
    List onboarding requirements for the frontend.

    GET /api/v1/technicians/onboarding-requirements/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "requirements": [
                {
                    "key": req["key"],
                    "label": req["label"],
                    "type": req["type"],
                    "required": req.get("required", True),
                    "min_count": req.get("min_count"),
                }
                for req in ONBOARDING_REQUIREMENTS
            ]
        })


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN VIEWS
# ═══════════════════════════════════════════════════════════════════════════════


class TechnicianAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin viewset for managing technicians.

    GET    /api/v1/admin/technicians/           - List technicians
    GET    /api/v1/admin/technicians/{id}/      - Get technician detail
    POST   /api/v1/admin/technicians/{id}/approve/  - Approve onboarding
    POST   /api/v1/admin/technicians/{id}/request-changes/  - Request changes
    POST   /api/v1/admin/technicians/{id}/suspend/  - Suspend technician
    POST   /api/v1/admin/technicians/{id}/reactivate/  - Reactivate suspended technician
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = TechnicianListSerializer

    def get_queryset(self):
        """Return technician profiles for the admin's tenant."""
        base = TechnicianProfile.objects.filter(
            tenant_id=self.request.user.tenant_id
        )

        if self.action == "retrieve":
            qs = base.select_related("user").prefetch_related(
                "service_regions",
                "user__skills",
            )
        else:
            email_sq = User.objects.filter(pk=OuterRef("user_id")).values("email")[:1]
            phone_sq = User.objects.filter(pk=OuterRef("user_id")).values("phone")[:1]
            display_sq = (
                User.objects.filter(pk=OuterRef("user_id"))
                .annotate(
                    _dn=Concat(
                        Coalesce("first_name", Value("")),
                        Value(" "),
                        Coalesce("last_name", Value("")),
                        output_field=CharField(),
                    )
                )
                .values("_dn")[:1]
            )
            skill_sq = (
                User.objects.filter(pk=OuterRef("user_id"))
                .annotate(n=Count("skills", filter=Q(skills__is_active=True)))
                .values("n")[:1]
            )
            qs = base.annotate(
                _list_email=Subquery(
                    email_sq, output_field=models.EmailField(null=True, blank=True)
                ),
                _list_phone=Subquery(phone_sq, output_field=CharField(max_length=50)),
                _list_display_name=Subquery(display_sq, output_field=CharField()),
                _skill_count=Coalesce(
                    Subquery(skill_sq, output_field=IntegerField()),
                    0,
                ),
                _region_count=Count(
                    "service_regions",
                    filter=Q(service_regions__is_active=True),
                    distinct=True,
                ),
            )

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(onboarding_status=status_filter)

        pending_review = self.request.query_params.get("pending_review")
        if pending_review and pending_review.lower() == "true":
            qs = qs.filter(onboarding_status=OnboardingStatus.SUBMITTED)

        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TechnicianAdminDetailSerializer
        return TechnicianListSerializer

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a technician's onboarding."""
        profile = self.get_object()

        serializer = TechnicianReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = TechnicianOnboardingService.approve(
                profile=profile,
                reviewer=request.user,
                notes=serializer.validated_data.get("notes", ""),
            )
        except Exception as e:
            logger.error(
                "technician_approval_failed",
                profile_id=str(profile.id),
                error=str(e),
            )
            raise

        response_serializer = TechnicianAdminDetailSerializer(profile)
        return Response(response_serializer.data)

    @action(detail=True, methods=["post"], url_path="request-changes")
    def request_changes(self, request, pk=None):
        """Send a technician's profile back for revisions."""
        profile = self.get_object()

        serializer = TechnicianReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = TechnicianOnboardingService.request_changes(
                profile=profile,
                reviewer=request.user,
                notes=serializer.validated_data.get("notes", ""),
            )
        except Exception as e:
            logger.error(
                "technician_changes_request_failed",
                profile_id=str(profile.id),
                error=str(e),
            )
            raise

        response_serializer = TechnicianAdminDetailSerializer(profile)
        return Response(response_serializer.data)

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        """Suspend a technician."""
        profile = self.get_object()

        serializer = TechnicianSuspendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = TechnicianOnboardingService.suspend(
                profile=profile,
                actor=request.user,
                reason=serializer.validated_data["reason"],
            )

            # Optionally store internal notes separately
            notes = serializer.validated_data.get("notes")
            if notes:
                profile.review_notes = notes
                profile.save(update_fields=["review_notes", "updated_at"])

        except Exception as e:
            logger.error(
                "technician_suspension_failed",
                profile_id=str(profile.id),
                error=str(e),
            )
            raise

        response_serializer = TechnicianAdminDetailSerializer(profile)
        return Response(response_serializer.data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        """Reactivate a suspended technician."""
        profile = self.get_object()

        serializer = TechnicianReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = TechnicianOnboardingService.reactivate(
                profile=profile,
                actor=request.user,
                notes=serializer.validated_data.get("notes", ""),
            )
        except Exception as e:
            logger.error(
                "technician_reactivation_failed",
                profile_id=str(profile.id),
                error=str(e),
            )
            raise

        response_serializer = TechnicianAdminDetailSerializer(profile)
        return Response(response_serializer.data)


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION FORM VIEWSET (operator/admin)
# ═══════════════════════════════════════════════════════════════════════════════


class ApplicationFormViewSet(viewsets.ModelViewSet):
    """
    Operator-facing CRUD for application form definitions.

    Routes (mounted under /api/v1/admin/):
        GET/POST   application-forms/
        GET/PATCH/PUT/DELETE application-forms/{id}/
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "status": ["exact", "in"],
    }
    search_fields = ["title", "slug", "description"]
    ordering_fields = ["created_at", "updated_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            tenant_id = getattr(self.request.user, "tenant_id", None)
        if not tenant_id:
            return ApplicationForm.objects.none()

        return ApplicationForm.objects.filter(tenant_id=tenant_id)

    def get_serializer_class(self):
        if self.action == "list":
            return ApplicationFormListSerializer
        if self.action == "create":
            return ApplicationFormCreateSerializer
        if self.action in ("update", "partial_update"):
            return ApplicationFormUpdateSerializer
        return ApplicationFormDetailSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["tenant_id"] = (
            get_current_tenant_id()
            or getattr(self.request.user, "tenant_id", None)
        )
        return ctx

    def perform_create(self, serializer):
        tenant_id = get_current_tenant_id() or self.request.user.tenant_id

        slug = serializer.validated_data.get("slug")
        if not slug:
            base_slug = slugify(serializer.validated_data["title"])[:140]
            slug = base_slug
            counter = 1
            while ApplicationForm.objects.filter(
                tenant_id=tenant_id, slug=slug
            ).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

        serializer.save(tenant_id=tenant_id, slug=slug)

        logger.info(
            "application_form_created",
            form_id=str(serializer.instance.id),
            tenant_id=str(tenant_id),
            title=serializer.instance.title,
            created_by=str(self.request.user.id),
        )

    def perform_destroy(self, instance):
        if instance.status != ApplicationFormStatus.DRAFT:
            raise ValidationError(
                {
                    "error": {
                        "code": "cannot_delete",
                        "message": (
                            f"Cannot delete a form with status '{instance.status}'. "
                            "Set status to 'archived' instead."
                        ),
                    }
                }
            )

        if instance.applications.exists():
            raise ValidationError(
                {
                    "error": {
                        "code": "has_applications",
                        "message": (
                            "Cannot delete a form that has applications. "
                            "Archive it instead."
                        ),
                    }
                }
            )

        logger.info(
            "application_form_deleted",
            form_id=str(instance.id),
            tenant_id=str(instance.tenant_id),
            title=instance.title,
            deleted_by=str(self.request.user.id),
        )
        instance.delete()


# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICIAN APPLICATION VIEWSET (operator/admin)
# ═══════════════════════════════════════════════════════════════════════════════


class TechnicianApplicationViewSet(viewsets.ModelViewSet):
    """
    Operator-facing CRUD + review for technician applications.

    Routes (mounted under /api/v1/admin/):
        GET    technician-applications/              list (filter, search, order)
        POST   technician-applications/              create (operator manual entry)
        GET    technician-applications/{id}/         retrieve
        PATCH  technician-applications/{id}/         update (notes, applicant data)
        PUT    technician-applications/{id}/         replace
        DELETE technician-applications/{id}/         destroy
        POST   technician-applications/{id}/review/   generic status transition
        POST   technician-applications/{id}/approve/  approve (terminal)
        POST   technician-applications/{id}/reject/   reject (terminal, reason required)
        POST   technician-applications/{id}/convert/   User + TechnicianProfile

    Tenant safety:
        - Queryset is always filtered by the request's tenant.
        - Creates inject tenant_id from context (client cannot spoof).

    Permissions:
        - Admin-only. Applicant-facing submission endpoints (if any) live
          elsewhere and are out of scope for this phase.
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = TechnicianApplicationSerializer

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = TechnicianApplicationFilter
    search_fields = [
        "first_name",
        "last_name",
        "company_name",
        "email",
        "phone",
    ]
    ordering_fields = [
        "created_at",
        "submitted_at",
        "status_changed_at",
        "reviewed_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            tenant_id = getattr(self.request.user, "tenant_id", None)
        if not tenant_id:
            return TechnicianApplication.objects.none()

        return TechnicianApplication.objects.filter(tenant_id=tenant_id).select_related(
            "converted_technician_profile",
            "application_form",
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["tenant_id"] = (
            get_current_tenant_id()
            or getattr(self.request.user, "tenant_id", None)
        )
        return ctx

    def get_serializer_class(self):
        if self.action == "list":
            return TechnicianApplicationListSerializer
        if self.action == "review":
            return TechnicianApplicationReviewSerializer
        if self.action == "approve":
            return TechnicianApplicationApproveSerializer
        if self.action == "reject":
            return TechnicianApplicationRejectSerializer
        if self.action == "convert":
            return TechnicianApplicationConvertSerializer
        return TechnicianApplicationSerializer

    def perform_create(self, serializer):
        tenant_id = get_current_tenant_id() or self.request.user.tenant_id
        now = timezone.now()

        serializer.save(
            tenant_id=tenant_id,
            source=serializer.validated_data.get("source") or "operator_entry",
            submitted_at=serializer.validated_data.get("submitted_at") or now,
        )

        logger.info(
            "technician_application_created",
            application_id=str(serializer.instance.id),
            tenant_id=str(tenant_id),
            created_by=str(self.request.user.id),
            source=serializer.instance.source,
            form_id=(
                str(serializer.instance.application_form_id)
                if serializer.instance.application_form_id
                else None
            ),
        )

        event_service.log_event(
            event_type=EventType.TECHNICIAN_APPLICATION_CREATED,
            entity_type=EntityType.TECHNICIAN_APPLICATION,
            entity_id=serializer.instance.id,
            payload={
                "source": serializer.instance.source,
                "applicant_type": serializer.instance.applicant_type,
                "email": serializer.instance.email,
                "application_form_id": (
                    str(serializer.instance.application_form_id)
                    if serializer.instance.application_form_id
                    else None
                ),
            },
            actor=self.request.user,
            tenant_id=tenant_id,
            request=self.request,
        )

    # ── Status transition helper ──

    def _apply_status_transition(
        self,
        application: TechnicianApplication,
        *,
        new_status: str,
        reviewer_notes: str | None = None,
        rejection_reason: str | None = None,
    ) -> TechnicianApplication:
        """
        Shared mutation path for review / approve / reject.

        - Stamps reviewer + timestamps.
        - Appends reviewer_notes (rather than overwriting) so history accrues.
        - Overwrites rejection_reason (single canonical reason).
        """
        now = timezone.now()
        old_status = application.status

        application.status = new_status
        application.status_changed_at = now
        application.reviewed_by = self.request.user
        application.reviewed_at = now

        update_fields = [
            "status",
            "status_changed_at",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]

        if reviewer_notes:
            stamp = now.strftime("%Y-%m-%d %H:%M")
            author = self.request.user.email
            entry = f"[{stamp} · {author}] {reviewer_notes.strip()}"
            application.reviewer_notes = (
                f"{application.reviewer_notes}\n{entry}"
                if application.reviewer_notes
                else entry
            )
            update_fields.append("reviewer_notes")

        if rejection_reason is not None:
            application.rejection_reason = rejection_reason
            update_fields.append("rejection_reason")

        application.save(update_fields=update_fields)

        event_type_map = {
            ApplicationStatus.APPROVED.value: EventType.TECHNICIAN_APPLICATION_APPROVED,
            ApplicationStatus.REJECTED.value: EventType.TECHNICIAN_APPLICATION_REJECTED,
        }
        status_key = (
            new_status
            if isinstance(new_status, str)
            else getattr(new_status, "value", str(new_status))
        )
        event_service.log_event(
            event_type=event_type_map.get(
                status_key, EventType.TECHNICIAN_APPLICATION_REVIEWED
            ),
            entity_type=EntityType.TECHNICIAN_APPLICATION,
            entity_id=application.id,
            payload={
                "old_status": old_status,
                "new_status": new_status,
                "reviewer_notes_added": bool(reviewer_notes),
                "rejection_reason": rejection_reason,
            },
            actor=self.request.user,
            tenant_id=application.tenant_id,
            request=self.request,
        )

        logger.info(
            "technician_application_status_changed",
            application_id=str(application.id),
            tenant_id=str(application.tenant_id),
            reviewer_id=str(self.request.user.id),
            old_status=old_status,
            new_status=new_status,
        )

        return application

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        """
        Generic status transition (e.g. move to `reviewing`, or `withdrawn`).

        Prefer /approve/ and /reject/ for terminal decisions — they carry
        dedicated validation. Use POST …/convert/ to provision accounts.
        """
        application = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "application": application},
        )
        serializer.is_valid(raise_exception=True)

        application = self._apply_status_transition(
            application,
            new_status=serializer.validated_data["status"],
            reviewer_notes=serializer.validated_data.get("reviewer_notes"),
            rejection_reason=serializer.validated_data.get("rejection_reason"),
        )

        out = TechnicianApplicationSerializer(
            application, context=self.get_serializer_context()
        )
        return Response(out.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """
        POST /admin/technician-applications/{id}/approve/

        Body (all optional):
            { "reviewer_notes": "Looks solid, good references." }

        Transitions to `approved` and stamps reviewer metadata.
        Use POST …/convert/ to create or link a User + TechnicianProfile.
        """
        application = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "application": application},
        )
        serializer.is_valid(raise_exception=True)

        application = self._apply_status_transition(
            application,
            new_status=ApplicationStatus.APPROVED,
            reviewer_notes=serializer.validated_data.get("reviewer_notes"),
        )

        out = TechnicianApplicationSerializer(
            application, context=self.get_serializer_context()
        )
        return Response(out.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """
        POST /admin/technician-applications/{id}/reject/

        Body:
            {
              "rejection_reason": "No availability in our service areas.",
              "reviewer_notes": "Revisit if we expand to Hudson."   // optional
            }

        `rejection_reason` is required.
        """
        application = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "application": application},
        )
        serializer.is_valid(raise_exception=True)

        application = self._apply_status_transition(
            application,
            new_status=ApplicationStatus.REJECTED,
            reviewer_notes=serializer.validated_data.get("reviewer_notes"),
            rejection_reason=serializer.validated_data["rejection_reason"],
        )

        out = TechnicianApplicationSerializer(
            application, context=self.get_serializer_context()
        )
        return Response(out.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="convert")
    def convert(self, request, pk=None):
        """
        POST /admin/technician-applications/{id}/convert/

        Turns the application into a User + TechnicianProfile.

        Body (all optional):
          {
            "existing_user_id": "uuid",          // link mode
            "create_supabase_account": true,     // default true
            "activate_immediately": false,       // skip onboarding gate
            "reviewer_notes": "Converted after phone screen."
          }

        Returns the updated application plus the created/linked user & profile ids.
        """
        application = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "application": application},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = TechnicianApplicationConversionService(
            actor=request.user, request=request
        )

        try:
            result = service.convert(
                application,
                existing_user_id=data.get("existing_user_id"),
                create_supabase_account=data.get("create_supabase_account", True),
                activate_immediately=data.get("activate_immediately", False),
                reviewer_notes=data.get("reviewer_notes"),
            )
        except ApplicationConversionError as e:
            return Response(
                {"error": {"code": e.code, "message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        out = ConversionResultSerializer(
            {
                "application": result.application,
                "user_id": result.user.id,
                "profile_id": result.profile.id,
                "user_created": result.user_created,
                "supabase_created": result.supabase_created,
            },
            context=self.get_serializer_context(),
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


class TechnicianApplicationPublicSubmitView(APIView):
    """
    POST /api/v1/tenants/{tenant_id}/apply/

    Legacy public apply: tenant from URL; application_form is null.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, tenant_id):
        try:
            tenant = Tenant.objects.get(id=tenant_id, status=TenantStatus.ACTIVE)
        except Tenant.DoesNotExist:
            return Response(
                {"error": {"code": "tenant_not_found", "message": "Invalid tenant."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianApplicationPublicSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        now = timezone.now()
        recent_cutoff = now - timedelta(hours=24)
        duplicate = TechnicianApplication.objects.filter(
            tenant=tenant,
            email__iexact=serializer.validated_data["email"],
            created_at__gte=recent_cutoff,
        ).exists()

        if duplicate:
            return Response(
                {
                    "error": {
                        "code": "duplicate_application",
                        "message": (
                            "An application with this email was recently submitted. "
                            "Please wait before reapplying."
                        ),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        application = serializer.save(
            tenant=tenant,
            status=ApplicationStatus.NEW,
            source="public_form",
            submitted_at=now,
            metadata={
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": (request.META.get("HTTP_USER_AGENT", "") or "")[:500],
                "submitted_via": "public_api",
            },
        )

        logger.info(
            "technician_application_submitted",
            application_id=str(application.id),
            tenant_id=str(tenant.id),
            email=application.email,
            source="public_form",
        )

        return Response(
            {
                "success": True,
                "message": "Application submitted successfully. We'll be in touch soon.",
                "reference": str(application.id)[:8],
            },
            status=status.HTTP_201_CREATED,
        )


class ApplicationFormPublicSubmitView(APIView):
    """
    POST /api/v1/forms/{form_id}/apply/

    Public apply against a specific ApplicationForm; tenant comes from the form.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, form_id):
        try:
            form = ApplicationForm.objects.select_related("tenant").get(id=form_id)
        except ApplicationForm.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "form_not_found",
                        "message": "Application form not found.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if not form.is_accepting_submissions:
            return Response(
                {
                    "error": {
                        "code": "form_not_active",
                        "message": (
                            "This application form is not currently accepting "
                            "submissions."
                        ),
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = form.tenant
        if not tenant.is_active:
            return Response(
                {
                    "error": {
                        "code": "tenant_inactive",
                        "message": "This organization is not currently active.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianApplicationPublicSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        now = timezone.now()
        raw_dup_hours = (form.settings or {}).get("duplicate_check_hours", 24)
        try:
            duplicate_check_hours = int(raw_dup_hours)
        except (TypeError, ValueError):
            duplicate_check_hours = 24
        if duplicate_check_hours < 0:
            duplicate_check_hours = 24
        recent_cutoff = now - timedelta(hours=duplicate_check_hours)

        duplicate = TechnicianApplication.objects.filter(
            tenant=tenant,
            application_form=form,
            email__iexact=serializer.validated_data["email"],
            created_at__gte=recent_cutoff,
        ).exists()

        if duplicate:
            return Response(
                {
                    "error": {
                        "code": "duplicate_application",
                        "message": (
                            "An application with this email was recently submitted "
                            "to this form. Please wait before reapplying."
                        ),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        application = serializer.save(
            tenant=tenant,
            application_form=form,
            status=ApplicationStatus.NEW,
            source="public_form",
            submitted_at=now,
            metadata={
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": (request.META.get("HTTP_USER_AGENT", "") or "")[:500],
                "submitted_via": "public_api",
                "form_id": str(form.id),
                "form_title": form.title,
            },
        )

        logger.info(
            "technician_application_submitted",
            application_id=str(application.id),
            tenant_id=str(tenant.id),
            form_id=str(form.id),
            email=application.email,
            source="public_form",
        )

        confirmation_message = (form.settings or {}).get(
            "confirmation_message",
            "Application submitted successfully. We'll be in touch soon.",
        )

        return Response(
            {
                "success": True,
                "message": confirmation_message,
                "reference": str(application.id)[:8],
            },
            status=status.HTTP_201_CREATED,
        )
