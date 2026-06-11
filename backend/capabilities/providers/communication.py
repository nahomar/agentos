from __future__ import annotations

import logging
from backend.capabilities.registry import CapabilityProvider, CapabilityResult

logger = logging.getLogger("capabilities.communication")


class TwilioCallProvider(CapabilityProvider):
    id = "communication.call"
    name = "Phone Call"
    description = "Make a phone call via Twilio"
    category = "communication"

    @property
    def available(self) -> bool:
        return bool(
            self.config.get("twilio_sid")
            and self.config.get("twilio_token")
            and self.config.get("twilio_phone")
        )

    async def execute(self, params: dict) -> CapabilityResult:
        phone = params.get("phone_number", "")
        message = params.get("message", "Hello from AgentOS")

        if not self.available:
            return CapabilityResult(
                success=True,
                data={"demo": True, "message": f"[Demo] Would call {phone}: {message}"},
            )

        try:
            from twilio.rest import Client
            client = Client(self.config["twilio_sid"], self.config["twilio_token"])
            call = client.calls.create(
                twiml=f"<Response><Say>{message}</Say></Response>",
                to=phone,
                from_=self.config["twilio_phone"],
            )
            return CapabilityResult(success=True, data={"call_sid": call.sid})
        except Exception as e:
            return CapabilityResult(success=False, error=str(e))


class TwilioSMSProvider(CapabilityProvider):
    id = "communication.sms"
    name = "Send SMS"
    description = "Send an SMS text message via Twilio"
    category = "communication"

    @property
    def available(self) -> bool:
        return bool(
            self.config.get("twilio_sid")
            and self.config.get("twilio_token")
            and self.config.get("twilio_phone")
        )

    async def execute(self, params: dict) -> CapabilityResult:
        phone = params.get("phone_number", "")
        body = params.get("body", "")

        if not self.available:
            return CapabilityResult(
                success=True,
                data={"demo": True, "message": f"[Demo] Would text {phone}: {body}"},
            )

        try:
            from twilio.rest import Client
            client = Client(self.config["twilio_sid"], self.config["twilio_token"])
            msg = client.messages.create(
                body=body,
                to=phone,
                from_=self.config["twilio_phone"],
            )
            return CapabilityResult(success=True, data={"message_sid": msg.sid})
        except Exception as e:
            return CapabilityResult(success=False, error=str(e))


class EmailProvider(CapabilityProvider):
    id = "communication.email"
    name = "Send Email"
    description = "Send an email via SMTP"
    category = "communication"

    @property
    def available(self) -> bool:
        return bool(self.config.get("smtp_host") and self.config.get("smtp_user"))

    async def execute(self, params: dict) -> CapabilityResult:
        to = params.get("to", "")
        subject = params.get("subject", "")
        body = params.get("body", "")

        if not self.available:
            return CapabilityResult(
                success=True,
                data={"demo": True, "message": f"[Demo] Would email {to}: {subject}"},
            )

        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.config["smtp_user"]
            msg["To"] = to

            with smtplib.SMTP(self.config["smtp_host"], self.config.get("smtp_port", 587)) as server:
                server.starttls()
                server.login(self.config["smtp_user"], self.config["smtp_pass"])
                server.send_message(msg)

            return CapabilityResult(success=True, data={"sent_to": to})
        except Exception as e:
            return CapabilityResult(success=False, error=str(e))


class PushNotificationProvider(CapabilityProvider):
    id = "communication.push"
    name = "Push Notification"
    description = "Send a push notification to the user's device"
    category = "communication"

    @property
    def available(self) -> bool:
        return True  # Always available via WebSocket fallback

    async def execute(self, params: dict) -> CapabilityResult:
        title = params.get("title", "AgentOS")
        body = params.get("body", "")
        # This gets handled by the notification system
        return CapabilityResult(
            success=True,
            data={"title": title, "body": body, "type": "push"},
        )
