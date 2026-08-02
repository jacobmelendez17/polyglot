// Billing / subscription client.
import { request } from "./http";

export interface Entitlements {
  tier: string;
  status: string;
  entitled: boolean;
  free_max_level: number;
  current_period_end: string | null;
  canceled_at: string | null;
}

export interface Plan {
  plan: string;
  label: string;
  amount: number;
  currency: string;
  interval: string;
}

export const billing = {
  entitlements: () => request<Entitlements>("/api/v1/me/entitlements"),
  plans: () => request<Plan[]>("/api/v1/billing/plans"),
  checkout: (plan: string, success_url = "/dashboard", cancel_url = "/pricing") =>
    request<{ url: string }>("/api/v1/billing/checkout",
      { method: "POST", body: JSON.stringify({ plan, success_url, cancel_url }) }),
  portal: (return_url = "/settings") =>
    request<{ url: string }>("/api/v1/billing/portal",
      { method: "POST", body: JSON.stringify({ return_url }) }),
};

export function priceText(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: currency.toUpperCase() })
    .format(amount / 100);
}
