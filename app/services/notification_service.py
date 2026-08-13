"""Facility 5 support: Slack notification when a workflow pauses for human approval.

Posting to Slack is a best-effort side channel. If no bot token/channel
is configured, or the Slack API call fails, the workflow still pauses
correctly and waits on POST /brain-os/resume -- only the notification is
skipped, and that is logged rather than silently swallowed.
"""

from __future__ import annotations

import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, slack_bot_token: str, slack_channel: str) -> None:
        self._channel = slack_channel
        self._client = WebClient(token=slack_bot_token) if slack_bot_token and slack_channel else None

    def notify_approval_needed(self, workflow_id: str, vendor: str | None, amount: float | None, risk_score: float) -> bool:
        """Posts a Slack message asking a human to resume the workflow. Returns True if sent."""
        if self._client is None:
            logger.info("Slack not configured; skipping approval notification for workflow %s.", workflow_id)
            return False

        amount_display = f"${amount:,.2f}" if amount is not None else "unknown"
        text = (
            f":rotating_light: Invoice approval needed - workflow `{workflow_id}`\n"
            f"Vendor: {vendor or 'unknown'} | Amount: {amount_display} | Risk score: {risk_score}/100\n"
            f'Resume with: POST /brain-os/resume {{"workflow_id": "{workflow_id}", "decision": "approved"|"rejected"}}'
        )
        try:
            self._client.chat_postMessage(channel=self._channel, text=text)
            return True
        except SlackApiError:
            logger.warning("Failed to post Slack approval notification for workflow %s.", workflow_id, exc_info=True)
            return False
