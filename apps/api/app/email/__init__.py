"""Email delivery, behind a provider interface."""
from app.email.provider import (
    ConsoleEmailProvider,
    EmailDeliveryError,
    EmailProvider,
    MemoryEmailProvider,
    OutgoingEmail,
    SmtpEmailProvider,
    build_provider,
)

__all__ = [
    "EmailProvider", "OutgoingEmail", "ConsoleEmailProvider",
    "MemoryEmailProvider", "SmtpEmailProvider", "EmailDeliveryError",
    "build_provider",
]
