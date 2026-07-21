"""
Custom Django email backend for Resend using their HTTP API.

This is more reliable than the SMTP relay because:
- No SSL/TLS configuration headaches
- Better error messages from the API response
- Supports attachments (base64-encoded)
- Works in sandbox mode for testing

Configure in settings.py:
    EMAIL_BACKEND = "payments.email_backends.ResendEmailBackend"
    RESEND_API_KEY = "re_..."
    DEFAULT_FROM_EMAIL = "noreply@yourdomain.com"  # must be a verified domain in Resend
"""
import base64
import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """Send emails via the Resend HTTP API (supports attachments)."""

    def open(self):
        pass

    def close(self):
        pass

    def send_messages(self, email_messages):
        """Send a list of EmailMessage objects. Returns the number sent."""
        try:
            import resend as resend_sdk
        except ImportError:
            logger.error(
                "ResendEmailBackend: the 'resend' package is not installed. "
                "Run: pip install resend"
            )
            return 0

        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            logger.error("ResendEmailBackend: RESEND_API_KEY is not configured.")
            return 0

        resend_sdk.api_key = api_key
        num_sent = 0

        for message in email_messages:
            try:
                params = self._build_params(message)
                logger.info(
                    "Sending email via Resend API: to=%s subject=%r from=%s",
                    params.get("to"),
                    params.get("subject"),
                    params.get("from"),
                )
                response = resend_sdk.Emails.send(params)
                email_id = getattr(response, "id", None) or (response.get("id") if isinstance(response, dict) else None)
                logger.info("Email sent via Resend. id=%s", email_id)
                num_sent += 1
            except Exception as exc:  # noqa: BLE001
                err_str = str(exc)
                if "You can only send testing emails to your own email address" in err_str:
                    import re
                    match = re.search(r'\((.*?@.*?)\)', err_str)
                    if match:
                        sandbox_email = match.group(1)
                        logger.warning(
                            "Resend Sandbox mode detected. Overriding recipient from %s to %s",
                            params.get("to"),
                            sandbox_email
                        )
                        params["to"] = [sandbox_email]
                        try:
                            response = resend_sdk.Emails.send(params)
                            email_id = getattr(response, "id", None) or (response.get("id") if isinstance(response, dict) else None)
                            logger.info("Email sent via Resend (sandbox override). id=%s", email_id)
                            num_sent += 1
                            continue
                        except Exception as inner_exc:
                            logger.error("Sandbox override failed: %s", inner_exc, exc_info=True)
                            if not self.fail_silently:
                                raise inner_exc
                
                logger.error(
                    "Resend API error sending to %s: %s",
                    message.to,
                    exc,
                    exc_info=True,
                )
                if not self.fail_silently:
                    raise

        return num_sent

    def _build_params(self, message):
        """Convert a Django EmailMessage to a Resend API params dict."""
        params = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(message.to),
            "subject": message.subject,
            "text": message.body,
        }

        if message.cc:
            params["cc"] = list(message.cc)
        if message.bcc:
            params["bcc"] = list(message.bcc)
        if message.reply_to:
            params["reply_to"] = list(message.reply_to)

        # Handle attachments
        attachments = []
        for attachment in message.attachments:
            if isinstance(attachment, tuple):
                filename, content, mimetype = attachment
                if isinstance(content, str):
                    content = content.encode()
                attachments.append({
                    "filename": filename,
                    "content": base64.b64encode(content).decode('utf-8'),
                })
            else:
                logger.warning("Skipping unsupported attachment type: %s", type(attachment))

        if attachments:
            params["attachments"] = attachments

        # Handle HTML alternative
        # Django's EmailMultiAlternatives stores alternatives as (content, mimetype)
        for alt_content, alt_mimetype in getattr(message, "alternatives", []):
            if alt_mimetype == "text/html":
                params["html"] = alt_content
                break

        return params
