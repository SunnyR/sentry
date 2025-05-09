import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, TypedDict
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

from django.utils.functional import cached_property
from requests import RequestException
from requests.models import Response

from sentry.sentry_apps.external_requests.utils import send_and_save_sentry_app_request
from sentry.sentry_apps.metrics import (
    SentryAppEventType,
    SentryAppExternalRequestFailureReason,
    SentryAppExternalRequestHaltReason,
    SentryAppInteractionEvent,
    SentryAppInteractionType,
)
from sentry.sentry_apps.models.sentry_app_installation import SentryAppInstallation
from sentry.sentry_apps.services.app.model import RpcSentryAppInstallation
from sentry.sentry_apps.utils.errors import SentryAppErrorType
from sentry.utils import json

DEFAULT_SUCCESS_MESSAGE = "Success!"
DEFAULT_ERROR_MESSAGE = "Something went wrong!"
FAILURE_REASON_BASE = f"{SentryAppEventType.ALERT_RULE_ACTION_REQUESTED}.{{}}"


logger = logging.getLogger("sentry.sentry_apps.external_requests")


class SentryAppAlertRuleActionResult(TypedDict, total=False):
    success: bool
    message: str
    error_type: SentryAppErrorType | None
    webhook_context: dict[str, Any] | None
    public_context: dict[str, Any] | None
    status_code: int | None


@dataclass
class SentryAppAlertRuleActionRequester:
    install: SentryAppInstallation | RpcSentryAppInstallation
    uri: str
    fields: Sequence[Mapping[str, str]] = field(default_factory=list)
    http_method: str | None = "POST"

    def run(self) -> SentryAppAlertRuleActionResult:
        event = SentryAppEventType.ALERT_RULE_ACTION_REQUESTED
        with SentryAppInteractionEvent(
            operation_type=SentryAppInteractionType.EXTERNAL_REQUEST,
            event_type=event,
        ).capture() as lifecycle:
            extras: dict[str, Any] = {
                "uri": self.uri,
                "installation_uuid": self.install.uuid,
                "sentry_app_slug": self.sentry_app.slug,
            }
            try:

                response = send_and_save_sentry_app_request(
                    url=self._build_url(),
                    sentry_app=self.sentry_app,
                    org_id=self.install.organization_id,
                    event=event,
                    headers=self._build_headers(),
                    method=self.http_method,
                    data=self.body,
                )

            except RequestException as e:
                halt_reason = FAILURE_REASON_BASE.format(
                    SentryAppExternalRequestHaltReason.BAD_RESPONSE
                )
                lifecycle.record_halt(halt_reason=e, extra={"halt_reason": halt_reason, **extras})

                return SentryAppAlertRuleActionResult(
                    success=False,
                    message=self._get_response_message(e.response, DEFAULT_ERROR_MESSAGE),
                    error_type=SentryAppErrorType.INTEGRATOR,
                    webhook_context={"error_type": halt_reason, **extras},
                    status_code=500,
                )
            except Exception as e:
                failure_reason = FAILURE_REASON_BASE.format(
                    SentryAppExternalRequestFailureReason.UNEXPECTED_ERROR
                )
                lifecycle.record_failure(
                    failure_reason=e, extra={"failure_reason": failure_reason, **extras}
                )

                return SentryAppAlertRuleActionResult(
                    success=False,
                    message=DEFAULT_ERROR_MESSAGE,
                    error_type=SentryAppErrorType.SENTRY,
                    webhook_context={"error_type": failure_reason, **extras},
                    status_code=500,
                )

            return SentryAppAlertRuleActionResult(
                success=True, message=self._get_response_message(response, DEFAULT_SUCCESS_MESSAGE)
            )

    def _build_url(self) -> str:
        urlparts = list(urlparse(self.sentry_app.webhook_url))
        urlparts[2] = self.uri
        return urlunparse(urlparts)

    def _build_headers(self) -> dict[str, str]:
        request_uuid = uuid4().hex

        return {
            "Content-Type": "application/json",
            "Request-ID": request_uuid,
            "Sentry-App-Signature": self.sentry_app.build_signature(self.body),
        }

    def _get_response_message(self, response: Response | None, default_message: str) -> str:
        """
        Returns the message from the response body, if in the expected location.
        Used to bubble up info from the Sentry App to the UI.
        The location should be coordinated with the docs on Alert Rule Action UI Components.
        """
        if response is None:
            message = default_message
        else:
            try:
                message = response.json().get("message", default_message)
            except Exception:
                message = default_message

        return f"{self.sentry_app.name}: {message}"

    @cached_property
    def body(self):
        return json.dumps(
            {
                "fields": self.fields,
                "installationId": self.install.uuid,
            }
        )

    @cached_property
    def sentry_app(self):
        return self.install.sentry_app
