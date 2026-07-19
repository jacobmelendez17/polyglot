"use client";

import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import {
  ActionButtons, ForecastWidget, FluentWidget, LeechWidget,
  PracticeWidget, ProgressionWidget, WelcomeWidget, XpWidget,
} from "@/components/widgets";

export default function DashboardPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-8">
        {/* Hero: the two big action buttons, WaniKani-style */}
        <ActionButtons />

        {/* Mixed-size widget grid below */}
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-6">
          {/* full-width welcome */}
          <div className="md:col-span-6"><WelcomeWidget /></div>

          {/* progression (3) + two small tiles (1 + 1) + fluent(1) */}
          <div className="md:col-span-3"><ProgressionWidget /></div>
          <div className="md:col-span-2"><ForecastWidget /></div>
          <div className="md:col-span-1"><XpWidget /></div>

          {/* bottom row of tiles */}
          <div className="md:col-span-2"><FluentWidget /></div>
          <div className="md:col-span-2"><LeechWidget /></div>
          <div className="md:col-span-2"><PracticeWidget /></div>
        </div>
      </main>
    </Protected>
  );
}
