from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

import sentry_sdk

from sentry.integrations.msteams.card_builder.block import AdaptiveCard
from sentry.integrations.msteams.utils import get_user_conversation_id
from sentry.integrations.notifications import get_context, get_integrations_by_channel_by_recipient
from sentry.integrations.types import ExternalProviders
from sentry.notifications.notifications.activity.assigned import AssignedActivityNotification
from sentry.notifications.notifications.activity.base import GroupActivityNotification
from sentry.notifications.notifications.activity.escalating import EscalatingActivityNotification
from sentry.notifications.notifications.activity.note import NoteActivityNotification
from sentry.notifications.notifications.activity.regression import RegressionActivityNotification
from sentry.notifications.notifications.activity.release import ReleaseActivityNotification
from sentry.notifications.notifications.activity.resolved import ResolvedActivityNotification
from sentry.notifications.notifications.activity.resolved_in_release import (
    ResolvedInReleaseActivityNotification,
)
from sentry.notifications.notifications.activity.unassigned import UnassignedActivityNotification
from sentry.notifications.notifications.base import BaseNotification
from sentry.notifications.notifications.rules import AlertRuleNotification
from sentry.notifications.notify import register_notification_provider
from sentry.types.actor import Actor
from sentry.utils import metrics

from .card_builder.notifications import (
    MSTeamsIssueNotificationsMessageBuilder,
    MSTeamsNotificationsMessageBuilder,
)
from .client import MsTeamsClient

logger = logging.getLogger("sentry.notifications.msteams")

SUPPORTED_NOTIFICATION_TYPES = [
    NoteActivityNotification,
    AssignedActivityNotification,
    UnassignedActivityNotification,
    AlertRuleNotification,
    ResolvedActivityNotification,
    ResolvedInReleaseActivityNotification,
    ReleaseActivityNotification,
    RegressionActivityNotification,
    EscalatingActivityNotification,
]

BASE_MESSAGE_BUILDERS = {
    "SlackNotificationsMessageBuilder": MSTeamsNotificationsMessageBuilder,
}

# For Group-based notifications, it is possible we use a builder that is generic OR uses a group-specific builder
GROUP_MESSAGE_BUILDERS = BASE_MESSAGE_BUILDERS | {
    "IssueNotificationMessageBuilder": MSTeamsIssueNotificationsMessageBuilder,
}


def is_supported_notification_type(notification: BaseNotification) -> bool:
    return any(
        [
            isinstance(notification, notification_type)
            for notification_type in SUPPORTED_NOTIFICATION_TYPES
        ]
    )


def get_group_notification_card(
    notification: GroupActivityNotification | AlertRuleNotification,
    context: Mapping[str, Any],
    recipient: Actor,
) -> AdaptiveCard:
    cls = GROUP_MESSAGE_BUILDERS[notification.message_builder]
    return cls(notification, context, recipient).build_notification_card()


def get_base_notification_card(
    notification: BaseNotification, context: Mapping[str, Any], recipient: Actor
) -> AdaptiveCard:
    cls = BASE_MESSAGE_BUILDERS[notification.message_builder]
    return cls(notification, context, recipient).build_notification_card()


@register_notification_provider(ExternalProviders.MSTEAMS)
def send_notification_as_msteams(
    notification: BaseNotification,
    recipients: Iterable[Actor],
    shared_context: Mapping[str, Any],
    extra_context_by_actor: Mapping[Actor, Mapping[str, Any]] | None,
):
    if not is_supported_notification_type(notification):
        logger.info(
            "Unsupported notification type for Microsoft Teams %s", notification.__class__.__name__
        )
        return

    with sentry_sdk.start_span(op="notification.send_msteams", name="gen_channel_integration_map"):
        data = get_integrations_by_channel_by_recipient(
            organization=notification.organization,
            recipients=recipients,
            provider=ExternalProviders.MSTEAMS,
        )

        for recipient, integrations_by_channel in data.items():
            with sentry_sdk.start_span(op="notification.send_msteams", name="send_one"):
                extra_context = (extra_context_by_actor or {}).get(recipient, {})
                context = get_context(notification, recipient, shared_context, extra_context)

                with sentry_sdk.start_span(op="notification.send_msteams", name="gen_attachments"):
                    if isinstance(notification, GroupActivityNotification) or isinstance(
                        notification, AlertRuleNotification
                    ):
                        card = get_group_notification_card(notification, context, recipient)
                    else:
                        card = get_base_notification_card(notification, context, recipient)

                for channel, integration in integrations_by_channel.items():
                    conversation_id = get_user_conversation_id(integration, channel)

                    client = MsTeamsClient(integration)
                    try:
                        with sentry_sdk.start_span(
                            op="notification.send_msteams", name="notify_recipient"
                        ):
                            client.send_card(conversation_id, card)

                        notification.record_notification_sent(recipient, ExternalProviders.MSTEAMS)
                    except Exception:
                        logger.exception("Exception occurred while trying to send the notification")

    metrics.incr(
        f"{notification.metrics_key}.notifications.sent",
        instance=f"msteams.{notification.metrics_key}.notification",
        skip_internal=False,
    )
