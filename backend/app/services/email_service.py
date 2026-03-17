"""Email sending, template rendering, and verification service."""

import logging
from typing import Any

import httpx
from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateSyntaxError, UndefinedError

from app.config import settings

logger = logging.getLogger(__name__)

# Jinja2 environment configured with StrictUndefined so missing variables
# cause an immediate error rather than silently rendering blank.
_jinja_env = Environment(
    loader=BaseLoader(),
    undefined=StrictUndefined,
    autoescape=True,
)


class TemplateRenderError(Exception):
    """Raised when a template cannot be rendered due to missing variables or syntax errors."""


class EmailSendError(Exception):
    """Raised when the Mailgun API returns an error."""


class EmailService:
    """Handles Mailgun API interactions and template rendering."""

    def __init__(self) -> None:
        self.api_key = settings.mailgun_api_key
        self.domain = settings.mailgun_domain
        self.sender = settings.mailgun_sender_email
        self.base_url = f"https://api.mailgun.net/v3/{self.domain}"

    def render_template(
        self,
        subject_template: str,
        body_html_template: str,
        variables: dict[str, Any],
        body_text_template: str | None = None,
    ) -> dict[str, str]:
        """Render subject and body templates with the given variables.

        Raises TemplateRenderError if any referenced variable is missing or the
        template syntax is invalid.
        """
        try:
            subject = _jinja_env.from_string(subject_template).render(variables)
            body_html = _jinja_env.from_string(body_html_template).render(variables)

            # Append CAN-SPAM physical address footer
            footer = (
                f'<br><hr style="margin-top:40px"><p style="font-size:11px;color:#999;">'
                f"{settings.app_physical_address}<br>"
                f'<a href="{{{{unsubscribe_url}}}}">Unsubscribe</a></p>'
            )
            body_html += footer

            body_text: str | None = None
            if body_text_template:
                body_text = _jinja_env.from_string(body_text_template).render(variables)
                body_text += (
                    f"\n\n---\n{settings.app_physical_address}\n"
                    "To unsubscribe, reply with UNSUBSCRIBE."
                )

            result: dict[str, str] = {"subject": subject, "body_html": body_html}
            if body_text:
                result["body_text"] = body_text
            return result

        except UndefinedError as exc:
            raise TemplateRenderError(
                f"Missing template variable: {exc}"
            ) from exc
        except TemplateSyntaxError as exc:
            raise TemplateRenderError(
                f"Template syntax error: {exc}"
            ) from exc

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str | None = None,
        custom_variables: dict[str, str] | None = None,
    ) -> str | None:
        """Send an email via the Mailgun API.

        Returns the Mailgun message ID on success, or None on failure.
        Includes the List-Unsubscribe header for compliance.
        """
        data: dict[str, Any] = {
            "from": self.sender,
            "to": [to_email],
            "subject": subject,
            "html": body_html,
            "h:List-Unsubscribe": f"<mailto:unsubscribe@{self.domain}>",
        }
        if body_text:
            data["text"] = body_text

        # Attach custom tracking variables for webhook correlation
        if custom_variables:
            for key, value in custom_variables.items():
                data[f"v:{key}"] = value

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/messages",
                    auth=("api", self.api_key),
                    data=data,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                message_id = result.get("id", "").strip("<>")
                logger.info("Email sent to %s, Mailgun ID: %s", to_email, message_id)
                return message_id

            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Mailgun API error sending to %s: %s %s",
                    to_email,
                    exc.response.status_code,
                    exc.response.text,
                )
                raise EmailSendError(
                    f"Mailgun API returned {exc.response.status_code}"
                ) from exc
            except httpx.RequestError as exc:
                logger.error("Network error sending email to %s: %s", to_email, exc)
                raise EmailSendError(f"Network error: {exc}") from exc

    async def verify_email(self, email: str) -> dict[str, Any] | None:
        """Validate an email address using the Mailgun validation API.

        Returns the validation result dict, or None if the API call fails.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.mailgun.net/v4/address/validate",
                    auth=("api", self.api_key),
                    params={"address": email},
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                logger.error("Mailgun validation API error for %s: %s", email, exc)
                return None
