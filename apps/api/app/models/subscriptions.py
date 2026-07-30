"""Slice 12 subscriptions.

IMPORTANT: the `subscriptions` table already exists — it was created by the
initial schema (`ee4e5b7811bd`) and its canonical model lives in
`app.models.platform`. Slice 12 must NOT define a second mapped class for the
same table, or SQLAlchemy raises "Table 'subscriptions' is already defined for
this MetaData instance" the moment both are imported.

So this module only re-exports the canonical model. The extra columns slice 12
needs (`stripe_subscription_id`, `price_interval`, `cancel_at_period_end`) are
added to `platform.Subscription` and to the table by the corrected slice-12
migration.
"""
from app.models.platform import Subscription  # noqa: F401

__all__ = ["Subscription"]
