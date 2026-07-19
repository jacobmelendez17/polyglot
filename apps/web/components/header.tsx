"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth-context";

const ADMIN_CAP = "admin_panel";

export function Header() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const showAdmin = user?.capabilities.includes(ADMIN_CAP);

  return (
    <header className="border-b border-terraza-dash">
      <div className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3">
        <Link href="/dashboard" className="mr-auto text-lg lowercase tracking-cozy">
          polyglot <span className="text-terraza-accent">✦</span>
        </Link>

        <nav className="flex items-center gap-1" aria-label="Main">
          <Link href="/levels" className="rounded-full px-4 py-2 text-terraza-soft hover:bg-terraza-pill">
            levels
          </Link>
          <Link href="/reviews" className="rounded-full px-4 py-2 text-terraza-soft hover:bg-terraza-pill">
            reviews
          </Link>

          <div className="relative">
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-terraza-green bg-terraza-pink"
              aria-haspopup="menu" aria-expanded={menuOpen} aria-label="Account menu"
            >
              {(user?.email?.[0] ?? "?").toUpperCase()}
            </button>
            {menuOpen && (
              <div
                role="menu"
                className="absolute right-0 z-10 mt-2 w-48 rounded-card border border-terraza-dash bg-terraza-card p-1 shadow-lg"
              >
                <div className="px-3 py-2 text-xs text-terraza-soft">{user?.email}</div>
                <MenuItem href="/dashboard">profile</MenuItem>
                <MenuItem href="/dashboard">settings</MenuItem>
                {showAdmin && <MenuItem href="/admin">admin</MenuItem>}
                <button
                  role="menuitem"
                  onClick={() => { setMenuOpen(false); logout(); }}
                  className="block w-full rounded-[10px] px-3 py-2 text-left hover:bg-terraza-pill"
                >
                  log out
                </button>
              </div>
            )}
          </div>
        </nav>
      </div>
    </header>
  );
}

function MenuItem({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link role="menuitem" href={href} className="block rounded-[10px] px-3 py-2 hover:bg-terraza-pill">
      {children}
    </Link>
  );
}
