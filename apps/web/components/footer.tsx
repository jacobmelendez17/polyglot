"use client";

// Site footer (spec §21).
//
// Several of these destinations don't exist yet. Rather than link to a 404, the
// unbuilt ones render as plain text with a quiet "soon" marker — a link that
// goes nowhere is worse than an honest gap, and this way the footer's shape is
// settled now and each page just flips a flag when it ships.

import Link from "next/link";
import { useEffect, useState } from "react";
import { changelog } from "@/lib/content-api";
import { useUiText } from "@/lib/i18n";

interface FooterLink {
  key: string;
  href: string | null;      // null = not built yet
  badge?: number;
}

export function Footer() {
  const { t } = useUiText();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let live = true;
    changelog.unread()
      .then((r) => { if (live) setUnread(r.unread); })
      .catch(() => { /* signed out, or offline — the footer still renders */ });
    return () => { live = false; };
  }, []);

  const product: FooterLink[] = [
    { key: "footer.features", href: null },
    { key: "footer.how", href: null },
    { key: "footer.pricing", href: null },
    { key: "footer.changelog", href: "/changelog", badge: unread },
  ];

  const resources: FooterLink[] = [
    { key: "footer.support", href: null },
    { key: "footer.faq", href: null },
    { key: "footer.intermissions", href: "/intermissions" },
    { key: "footer.community", href: null },
  ];

  return (
    <footer className="mt-16 border-t border-terraza-dash">
      <div className="mx-auto flex max-w-7xl flex-wrap gap-10 px-4 py-10">
        <div className="mr-auto max-w-xs">
          <p className="text-lg lowercase tracking-cozy">
            polyglot <span className="text-terraza-accent">✦</span>
          </p>
          <p className="mt-2 text-sm text-terraza-soft">
            a spaced-repetition journey through latin american spanish.
          </p>
        </div>

        <FooterColumn title={t("footer.product")} links={product} t={t} />
        <FooterColumn title={t("footer.resources")} links={resources} t={t} />
      </div>

      <div className="mx-auto max-w-7xl px-4 pb-8">
        <p className="text-xs text-terraza-soft">
          © {new Date().getFullYear()} polyglot · built slowly, on purpose
        </p>
      </div>
    </footer>
  );
}

function FooterColumn({
  title, links, t,
}: { title: string; links: FooterLink[]; t: (k: string) => string }) {
  return (
    <nav aria-label={title}>
      <h2 className="mb-3 text-xs tracking-label text-terraza-soft">
        {title.toUpperCase()}
      </h2>
      <ul className="flex flex-col gap-2 text-sm">
        {links.map((link) => (
          <li key={link.key}>
            {link.href ? (
              <Link
                href={link.href}
                className="inline-flex items-center gap-2 text-terraza-ink hover:underline hover:underline-offset-2"
              >
                {t(link.key)}
                {link.badge ? (
                  <span
                    className="rounded-full bg-terraza-accent px-2 py-0.5 text-[10px] text-terraza-accentInk"
                    aria-label={`${link.badge} unread`}
                  >
                    {link.badge}
                  </span>
                ) : null}
              </Link>
            ) : (
              <span className="inline-flex items-center gap-2 text-terraza-soft">
                {t(link.key)}
                <span className="rounded-full bg-terraza-pill px-2 py-0.5 text-[10px] tracking-label">
                  SOON
                </span>
              </span>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}
