"""Stripe, behind a provider interface (same pattern as email/audio).

Real Stripe in production; a deterministic fake locally and in tests. The fake
lets the entire subscribe → webhook → entitlement flow run with no Stripe
account and no network — you can watch a subscription go active, past-due,
canceled, and lapse without ever leaving your machine.

Swapping the fake for real Stripe is a config flag (`STRIPE_SECRET_KEY` set) and
nothing else: the service layer only ever sees this interface.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class CheckoutSession:
    id: str
    url: str
    customer_id: str


class BillingProvider:
    """The interface the subscription service depends on."""

    def create_checkout(
        self, *, user_id: str, email: str, interval: str, success_url: str,
        cancel_url: str,
    ) -> CheckoutSession:  # pragma: no cover - interface
        raise NotImplementedError

    def create_billing_portal(self, *, customer_id: str, return_url: str) -> str:  # pragma: no cover
        raise NotImplementedError

    def verify_webhook(self, payload: bytes, signature: str) -> dict:  # pragma: no cover
        raise NotImplementedError


@dataclass
class FakeBillingProvider(BillingProvider):
    """A Stripe stand-in with no network. Checkout returns a local URL that the
    dev flow can 'complete' by posting a synthetic webhook."""

    created: list[dict] = field(default_factory=list)
    frontend_url: str = "http://localhost:3000"

    def create_checkout(self, *, user_id, email, interval, success_url, cancel_url):
        customer_id = f"cus_fake_{user_id[:8]}"
        session_id = f"cs_fake_{uuid.uuid4().hex[:16]}"
        self.created.append({"session_id": session_id, "user_id": user_id,
                             "interval": interval, "customer_id": customer_id})
        # Point at a local dev route that simulates Stripe redirecting back.
        url = (f"{self.frontend_url}/dev/checkout"
               f"?session={session_id}&interval={interval}&user={user_id}")
        return CheckoutSession(id=session_id, url=url, customer_id=customer_id)

    def create_billing_portal(self, *, customer_id, return_url):
        return f"{self.frontend_url}/dev/portal?customer={customer_id}"

    def verify_webhook(self, payload, signature):
        # The fake trusts its own synthetic events; real Stripe verifies a sig.
        import json
        return json.loads(payload.decode("utf-8"))


class StripeBillingProvider(BillingProvider):  # pragma: no cover - needs real Stripe
    """Real Stripe. Imported lazily so the dependency is optional until you
    actually wire billing in production."""

    def __init__(self, *, secret_key: str, webhook_secret: str,
                 price_month: str, price_year: str):
        import stripe  # optional dependency, only needed in prod

        self._stripe = stripe
        stripe.api_key = secret_key
        self._webhook_secret = webhook_secret
        self._prices = {"month": price_month, "year": price_year}

    def create_checkout(self, *, user_id, email, interval, success_url, cancel_url):
        session = self._stripe.checkout.Session.create(
            mode="subscription",
            customer_email=email,
            line_items=[{"price": self._prices[interval], "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=user_id,
            metadata={"user_id": user_id, "interval": interval},
        )
        return CheckoutSession(
            id=session.id, url=session.url, customer_id=session.customer or "",
        )

    def create_billing_portal(self, *, customer_id, return_url):
        portal = self._stripe.billing_portal.Session.create(
            customer=customer_id, return_url=return_url,
        )
        return portal.url

    def verify_webhook(self, payload, signature):
        return self._stripe.Webhook.construct_event(
            payload, signature, self._webhook_secret,
        )


def build_billing_provider(settings) -> BillingProvider:
    """Real Stripe when a secret key is set; the fake otherwise."""
    secret = (getattr(settings, "stripe_secret_key", "") or "").strip()
    if secret:
        return StripeBillingProvider(
            secret_key=secret,
            webhook_secret=getattr(settings, "stripe_webhook_secret", "") or "",
            price_month=getattr(settings, "stripe_price_month", "") or "",
            price_year=getattr(settings, "stripe_price_year", "") or "",
        )
    return FakeBillingProvider(
        frontend_url=getattr(settings, "frontend_url", "") or "http://localhost:3000",
    )
