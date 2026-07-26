"""Email bodies. Plain text with an HTML alternative; original copy only.

Kept apart from the provider and the service so the wording can change without
touching delivery or business logic. The link is passed in already-built — this
module never sees a raw token except as part of that URL.
"""
from __future__ import annotations

from app.email.provider import OutgoingEmail

_SIG = "— the polyglot team"


def _shell(title: str, lines: list[str], button_label: str, url: str) -> str:
    body = "".join(f"<p style='margin:0 0 14px'>{line}</p>" for line in lines)
    return f"""\
<div style="font-family:system-ui,sans-serif;max-width:520px;margin:auto;color:#3a2f2a">
  <h1 style="font-size:20px;font-weight:600">{title}</h1>
  {body}
  <p style="margin:24px 0">
    <a href="{url}"
       style="background:#e8825a;color:#fff;padding:12px 22px;border-radius:999px;
              text-decoration:none;display:inline-block">{button_label}</a>
  </p>
  <p style="color:#8a7d76;font-size:13px">
    If the button doesn't work, paste this link into your browser:<br>{url}
  </p>
  <p style="color:#8a7d76;font-size:13px;margin-top:24px">{_SIG}</p>
</div>"""


def password_reset(to: str, url: str) -> OutgoingEmail:
    lines = [
        "Someone asked to reset the password for your polyglot account.",
        "If it was you, use the link below. It's good for one hour and can only "
        "be used once.",
        "If it wasn't you, you can ignore this email — nothing has changed.",
    ]
    text = (
        "Reset your polyglot password\n\n"
        + "\n\n".join(lines)
        + f"\n\nReset it here: {url}\n\n{_SIG}\n"
    )
    return OutgoingEmail(
        to=to,
        subject="Reset your polyglot password",
        text=text,
        html=_shell("reset your password", lines, "reset password", url),
    )


def email_verification(to: str, url: str) -> OutgoingEmail:
    lines = [
        "Welcome to polyglot! Confirm this email address to finish setting up "
        "your account.",
        "This link is good for 24 hours.",
    ]
    text = (
        "Confirm your email\n\n"
        + "\n\n".join(lines)
        + f"\n\nConfirm here: {url}\n\n{_SIG}\n"
    )
    return OutgoingEmail(
        to=to,
        subject="Confirm your email for polyglot",
        text=text,
        html=_shell("confirm your email", lines, "confirm email", url),
    )
