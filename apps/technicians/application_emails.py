"""
HTML (and plain-text) notifications when a technician application is submitted
via public endpoints only.
"""

from __future__ import annotations

import logging

from django.template.loader import render_to_string

from apps.core.mail import send_transactional
from apps.technicians.models import ApplicantType, TechnicianApplication

logger = logging.getLogger(__name__)


def _applicant_display_name(application: TechnicianApplication) -> str:
    if application.applicant_type == ApplicantType.COMPANY:
        return (application.company_name or "").strip() or application.email
    parts = f"{application.first_name or ''} {application.last_name or ''}".strip()
    return parts or application.email


def notify_application_submitted(application: TechnicianApplication) -> None:
    """
    Email the applicant and (if configured) the tenant ``operator_admin_email``.

    Failures are logged; submission HTTP response is not affected.
    """
    full = (
        TechnicianApplication.objects.select_related("tenant", "application_form")
        .filter(pk=getattr(application, "pk", None))
        .first()
    )
    if not full:
        return
    application = full
    tenant = application.tenant
    if tenant is None:
        logger.warning(
            "application_email_skip_no_tenant",
            extra={"application_id": str(application.id)},
        )
        return

    if not application.email:
        logger.warning(
            "application_email_skip_no_applicant_email",
            extra={"application_id": str(application.id)},
        )
        return

    form_title = ""
    if application.application_form_id and application.application_form:
        form_title = application.application_form.title or ""

    ctx = {
        "tenant_name": tenant.name,
        "applicant_name": _applicant_display_name(application),
        "applicant_email": application.email,
        "reference": str(application.id)[:8],
        "form_title": form_title or "Technician application",
    }

    subject_applicant = f"We received your application — {tenant.name}"
    subject_operator = (
        f"New technician application — {ctx['applicant_name']} ({ctx['reference']})"
    )

    try:
        text_applicant = render_to_string(
            "technicians/email/application_submitted_applicant.txt",
            ctx,
        )
        html_applicant = render_to_string(
            "technicians/email/application_submitted_applicant.html",
            ctx,
        )
        send_transactional(
            subject=subject_applicant,
            body=text_applicant,
            to=application.email,
            html_body=html_applicant,
        )
    except Exception:
        logger.exception(
            "application_email_applicant_failed",
            extra={"application_id": str(application.id)},
        )

    op_email = (tenant.operator_admin_email or "").strip()
    if not op_email:
        return

    try:
        text_op = render_to_string(
            "technicians/email/application_submitted_operator.txt",
            ctx,
        )
        html_op = render_to_string(
            "technicians/email/application_submitted_operator.html",
            ctx,
        )
        send_transactional(
            subject=subject_operator,
            body=text_op,
            to=op_email,
            html_body=html_op,
        )
    except Exception:
        logger.exception(
            "application_email_operator_failed",
            extra={
                "application_id": str(application.id),
                "operator_admin_email": op_email,
            },
        )
