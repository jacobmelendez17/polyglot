"""Payment provider seam (spec §19).

Billing logic shouldn't depend on Stripe being reachable, so it talks to a
`PaymentProvider` interface. The MVP default is `FakeProvider`: checkout returns a
local stub URL and webhooks are accepted as plain JSON, so the whole subscribe →
webhook → entitlement flow runs (and is tested) with no Stripe account. `StripeProvider`
is the real adapter — a guarded import, so the app runs without the `stripe`
package. Select with `PAYMENT_PROVIDER` (default "fake").

Both providers speak the same normalized event shape to the billing service:
{ type, customer_id, tier, status, current_period_end }.
"""
from __future__ import annotations

import json
import os
from typing import Protocol, runtime_checkable

# Plan catalog (§19). Amounts in cents; Stripe price ids come from env.
PLANS: dict[str, dict] = {
    "monthly": {"amount": 700, "currency": "usd", "interval": "month",
                "price_env": "STRIPE_PRICE_MONTHLY", "label": "$7 / month"},
    "annual": {"amount": 6000, "currency": "usd", "interval": "year",
               "price_env": "STRIPE_PRICE_ANNUAL", "label": "$60 / year"},
}


class PaymentError(Exception):
    def __init__(self, message: str, code: str = "payment_error", status: int = 400) -> None:
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


@runtime_checkable
class PaymentProvider(Protocol):
    def create_checkout(self, *, user_id: str, email: str, plan: str,
                        success_url: str, cancel_url: str) -> str: ...
    def create_portal(self, *, customer_id: str, return_url: str) -> str: ...
    def verify_and_parse_webhook(self, payload: bytes, signature: str | None) -> dict: ...


class FakeProvider:
    """Local, deterministic. No network — for MVP/beta and tests."""

    name = "fake"

    def create_checkout(self, *, user_id, email, plan, success_url, cancel_url) -> str:
        if plan not in PLANS:
            raise PaymentError("Unknown plan.", "unknown_plan", 422)
        # A stub URL that a local page can 'complete' by posting a webhook.
        return f"/billing/fake-checkout?plan={plan}&uid={user_id}"

    def create_portal(self, *, customer_id, return_url) -> str:
        return f"/billing/fake-portal?customer={customer_id}"

    def verify_and_parse_webhook(self, payload: bytes, signature: str | None) -> dict:
        # No signature to verify in the fake — accept the JSON as the event.
        try:
            return json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise PaymentError("Malformed webhook payload.", "bad_payload", 400) from e


class StripeProvider:  # pragma: no cover - exercised only with a real Stripe account
    name = "stripe"

    def __init__(self) -> None:
        try:
            import stripe  # type: ignore
        except ImportError as e:
            raise PaymentError("PAYMENT_PROVIDER=stripe needs the `stripe` package.",
                               "stripe_missing", 500) from e
        self._stripe = stripe
        self._stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        self._webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    def _price_id(self, plan: str) -> str:
        cfg = PLANS.get(plan)
        if not cfg:
            raise PaymentError("Unknown plan.", "unknown_plan", 422)
        price_id = os.environ.get(cfg["price_env"])
        if not price_id:
            raise PaymentError(f"{cfg['price_env']} is not configured.", "no_price", 500)
        return price_id

    def create_checkout(self, *, user_id, email, plan, success_url, cancel_url) -> str:
        session = self._stripe.checkout.Session.create(
            mode="subscription", customer_email=email,
            line_items=[{"price": self._price_id(plan), "quantity": 1}],
            success_url=success_url, cancel_url=cancel_url,
            metadata={"user_id": user_id, "plan": plan},
            subscription_data={"metadata": {"user_id": user_id, "plan": plan}},
        )
        return session.url

    def create_portal(self, *, customer_id, return_url) -> str:
        session = self._stripe.billing_portal.Session.create(
            customer=customer_id, return_url=return_url)
        return session.url

    def verify_and_parse_webhook(self, payload: bytes, signature: str | None) -> dict:
        event = self._stripe.Webhook.construct_event(
            payload, signature, self._webhook_secret)
        obj = event["data"]["object"]
        return {
            "type": event["type"],
            "customer_id": obj.get("customer"),
            "tier": (obj.get("metadata") or {}).get("plan"),
            "status": obj.get("status"),
            "current_period_end": obj.get("current_period_end"),
        }


_provider: PaymentProvider | None = None


def get_provider() -> PaymentProvider:
    global _provider
    if _provider is not None:
        return _provider
    name = (os.getenv("PAYMENT_PROVIDER") or "fake").strip().lower()
    _provider = StripeProvider() if name == "stripe" else FakeProvider()
    return _provider


def reset_provider() -> None:
    """Test hook."""
    global _provider
    _provider = None
