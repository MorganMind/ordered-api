"""
Transactional email helpers. Sending uses Django’s email stack; when
``RESEND_API_KEY`` is set in settings, the backend is Resend (django-anymail).
"""

from __future__ import annotations

from typing import Iterable

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail


def send_transactional(
    *,
    subject: str,
    body: str,
    to: str | Iterable[str],
    html_body: str | None = None,
    from_email: str | None = None,
) -> None:
    """
    Send a single transactional message.

    ``to`` may be one address or an iterable of addresses. Plain ``body`` is
    required; if ``html_body`` is set, the message is multipart/alternative.
    """
    recipient_list = [to] if isinstance(to, str) else list(to)
    sender = from_email or settings.DEFAULT_FROM_EMAIL

    if html_body is not None:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=sender,
            to=recipient_list,
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
    else:
        send_mail(
            subject=subject,
            message=body,
            from_email=sender,
            recipient_list=recipient_list,
            fail_silently=False,
        )
