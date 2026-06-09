import os
import requests
from typing import List
from app.services.logger import logger


class NotificationService:
    """
    Slack Bot Notification Service with Rich UI + Priority Highlighting
    """

    def __init__(self):
        self.bot_token = os.getenv("SLACK_BOT_TOKEN")

        # Team Channels
        self.marketing_channel = os.getenv("SLACK_MARKETING_CHANNEL")
        self.product_channel = os.getenv("SLACK_PRODUCT_CHANNEL")
        self.engineering_channel = os.getenv("SLACK_ENGINEERING_CHANNEL")
        self.operations_channel = os.getenv("SLACK_OPERATIONS_CHANNEL")

        # Governance + Alerts
        self.approval_channel = os.getenv("SLACK_APPROVAL_CHANNEL")
        self.alert_channel = os.getenv("SLACK_ALERT_CHANNEL")

        self.slack_url = "https://slack.com/api/chat.postMessage"

    # ---------------------------------------------------------
    # Public Entry
    # ---------------------------------------------------------
    def send_event(self, event_type: str, action) -> None:

        if not self.bot_token:
            logger.warning("Slack bot token not configured.")
            return

        try:
            channels = self._resolve_channels(event_type, action)
            blocks = self._build_blocks(event_type, action)

            for channel in channels:
                self._post_to_slack(channel, blocks)

        except Exception as e:
            logger.error(f"Slack notification error: {e}")

    # ---------------------------------------------------------
    # Channel Routing Logic
    # ---------------------------------------------------------
    def _resolve_channels(self, event_type: str, action) -> List[str]:

        channels = []

        owner_channel_map = {
            "Marketing Team": self.marketing_channel,
            "Product Team": self.product_channel,
            "Engineering Team": self.engineering_channel,
            "Operations Team": self.operations_channel,
            "SRE Team": self.engineering_channel,
        }

        team_channel = owner_channel_map.get(action.owner)

        if event_type == "sla_breached":
            if self.alert_channel:
                channels.append(self.alert_channel)
            return channels

        if event_type in ["approval_required", "approved", "rejected"]:
            if team_channel:
                channels.append(team_channel)
            if self.approval_channel:
                channels.append(self.approval_channel)
            return channels

        if team_channel:
            channels.append(team_channel)

        return channels

    # ---------------------------------------------------------
    # Priority Color Indicator
    # ---------------------------------------------------------
    def _get_priority_indicator(self, priority: str):

        mapping = {
            "P0": "🔴 P0 - Critical",
            "P1": "🟡 P1 - High",
            "P2": "🟢 P2 - Normal",
        }

        return mapping.get(priority, priority)

    def _build_blocks(self, event_type: str, action):

        event_titles = {
            "created": "🆕 Action Created",
            "approval_required": "⏳ Approval Required",
            "approved": "✅ Action Approved",
            "rejected": "❌ Action Rejected",
            "completed": "🟢 Action Completed",
            "failed": "🔴 Action Failed",
            "sla_breached": "🚨 SLA Breached",
        }

        title = event_titles.get(event_type, "📢 Action Update")

        deadline = (
            action.sla_deadline.isoformat()
            if action.sla_deadline
            else "N/A"
        )

        priority_display = self._get_priority_indicator(action.priority)

        # =====================================================
        # 🆕 LIGHTWEIGHT UI FOR "created"
        # =====================================================
        if event_type == "created":
            return [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*🆔 ID:*\n{action.action_id}"},
                        {"type": "mrkdwn", "text": f"*👤 Owner:*\n{action.owner}"},
                        {"type": "mrkdwn", "text": f"*🔥 Priority:*\n{priority_display}"},
                    ]
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "ABOIA • Action Logged"
                        }
                    ]
                }
            ]

        # =====================================================
        # 🔥 FULL UI FOR ALL OTHER EVENTS
        # =====================================================
        blocks = [
            # Header
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title
                }
            },

            {"type": "divider"},

            # Priority Highlight
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Priority:* {priority_display}"
                }
            },

            # Full Details
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*🆔 ID:*\n{action.action_id}"},
                    {"type": "mrkdwn", "text": f"*👤 Owner:*\n{action.owner}"},
                    {"type": "mrkdwn", "text": f"*📊 Status:*\n{action.status}"},
                    {"type": "mrkdwn", "text": f"*⏳ SLA Deadline:*\n{deadline}"},
                    {"type": "mrkdwn", "text": f"*🛠 Type:*\n{action.type}"},
                ]
            }
        ]

        # Optional Error Section
        if action.error_message:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚠️ *Error:* {action.error_message}"
                }
            })

        # Footer
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "ABOIA • Autonomous Business Ops AI"
                }
            ]
        })

        return blocks

    # ---------------------------------------------------------
    # Slack API Call
    # ---------------------------------------------------------
    def _post_to_slack(self, channel: str, blocks: list):
        try:
            response = requests.post(
                self.slack_url,
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "channel": channel,
                    "blocks": blocks,
                },
                timeout=10,
            )

            response.raise_for_status()

            try:
                result = response.json()
            except ValueError as json_err:
                logger.error(f"Slack returned non-JSON response: {json_err}")
                return

            if not result.get("ok"):
                logger.error(f"Slack API error: {result}")

        except requests.RequestException as req_err:
            logger.error(f"Slack request failed: {req_err}")

        except Exception as e:
            logger.error(f"Unexpected Slack notification error: {e}")