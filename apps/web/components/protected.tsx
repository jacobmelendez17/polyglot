"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

// Client-side guard: while auth is bootstrapping, show a gentle loading state;
// if unauthenticated, redirect to login. (A server-side check via middleware
// arrives when Auth.js cookies replace localStorage.)
export function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-empty italic text-terraza-soft">un momento ~</p>
      </div>
    );
  }
  if (!user) return null;
  return <>{children}</>;
}
