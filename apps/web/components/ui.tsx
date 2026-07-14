"use client";

// Small set of Terraza-styled primitives so forms and the dashboard stay
// consistent. All derive from the design tokens in globals.css.

import Link from "next/link";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-card border border-terraza-dash bg-terraza-card p-6 ${className}`}
      style={{ boxShadow: "0 2px 0 var(--lg-dash)" }}
    >
      {children}
    </div>
  );
}

export function Label({ htmlFor, children }: { htmlFor: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-xs tracking-label text-terraza-soft">
      {children}
    </label>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full rounded-[14px] border border-terraza-dash bg-terraza-bg px-4 py-3 tracking-cozy outline-none focus-visible:ring-2 focus-visible:ring-terraza-accent"
    />
  );
}

export function Button({
  children, variant = "primary", ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" }) {
  const base =
    "rounded-full px-6 py-3 tracking-cozy transition-transform hover:-translate-y-0.5 disabled:opacity-50 disabled:hover:translate-y-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink";
  const styles =
    variant === "primary"
      ? "bg-terraza-accent text-terraza-accentInk"
      : "bg-terraza-pill text-terraza-ink";
  return (
    <button {...props} className={`${base} ${styles}`}>
      {children}
    </button>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="rounded-[12px] border border-terraza-danger/40 bg-terraza-danger/10 px-4 py-2 text-sm text-terraza-danger"
    >
      {message}
    </p>
  );
}

export function TextLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="text-terraza-accent underline underline-offset-2">
      {children}
    </Link>
  );
}
