# Resend (transactional email)

The API uses **[django-anymail](https://anymail.dev/)** with **[Resend](https://resend.com/)** when `RESEND_API_KEY` is set in the environment.

---

## 1. Resend dashboard

1. Create a [Resend](https://resend.com/) account.
2. **Domains** → add your domain (e.g. `orderedhq.com`) and add the DNS records Resend shows (SPF, DKIM). Wait until verification succeeds.
3. **API Keys** → create a key with **Sending access** (not full access).
4. Decide the **From** address. It must use a verified domain, e.g. `notifications@orderedhq.com`.  
   For quick tests only, Resend may offer `onboarding@resend.dev` — check their current docs.

---

## 2. Environment variables (`ordered-api` `.env`)

```bash
RESEND_API_KEY=re_xxxxxxxx
DEFAULT_FROM_EMAIL="Ordered <notifications@yourdomain.com>"
SERVER_EMAIL=Ordered <notifications@yourdomain.com>
```

- **`DEFAULT_FROM_EMAIL`**: RFC 5322 form, `Name <email@verified-domain.com>` or plain `email@verified-domain.com`.
- **`SERVER_EMAIL`**: Optional; defaults to `DEFAULT_FROM_EMAIL` (used for internal/error mail if you wire it later).

If **`RESEND_API_KEY` is unset**, Django uses **`django.core.mail.backends.console.EmailBackend`**: messages are printed to stdout (good for local dev). You can override with **`EMAIL_BACKEND`** (e.g. SMTP) without Resend.

Restart the app after changing env vars.

---

## 3. Sending from code

Use Django’s APIs or the small helper in `apps/core/mail.py`:

```python
from apps.core.mail import send_transactional

send_transactional(
    subject="Welcome",
    body="Plain text body.",
    to="user@example.com",
    html_body="<p>HTML <strong>optional</strong>.</p>",
)
```

Or `from django.core.mail import send_mail` — same backend.

---

## 4. Smoke test (Django shell)

```bash
python manage.py shell
```

```python
from django.core.mail import send_mail
from django.conf import settings

send_mail(
    subject="Resend test",
    message="If you see this in Resend logs, it worked.",
    from_email=settings.DEFAULT_FROM_EMAIL,
    recipient_list=["your-personal-email@example.com"],
    fail_silently=False,
)
```

---

## 5. Production checklist

- Domain verified in Resend; **From** matches that domain.
- `RESEND_API_KEY` set in the deployment secret/env (never commit it).
- Watch [Resend Logs](https://resend.com/emails) for bounces or API errors.

Optional later: [webhooks / delivery tracking](https://anymail.dev/en/stable/esps/resend/#status-tracking-webhooks) (needs `anymail` URLs and optionally `RESEND_SIGNING_SECRET` + `svix` — install with `django-anymail[resend]` if you use signed webhooks).

---

## Reference

- Anymail Resend ESP: https://anymail.dev/en/stable/esps/resend/
- Resend API: https://resend.com/docs
