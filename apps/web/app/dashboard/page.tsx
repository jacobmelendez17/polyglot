"use client";

import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import {
  ActionButtons, ForecastWidget, FluentWidget, LeechWidget,
  ProgressionWidget, WelcomeWidget, XpWidget,
} from "@/components/widgets";

export default function DashboardPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8">
        {/* Hero: the two big action buttons, WaniKani-style */}
        <ActionButtons />

        {/* Mixed-size widget grid below */}
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
          {/* full-width welcome */}
          <div className="md:col-span-4"><WelcomeWidget /></div>

          {/* wide progression (2 cols) + two stacked small tiles (2 cols) */}
          <div className="md:col-span-2"><ProgressionWidget /></div>
          <div className="md:col-span-1"><XpWidget /></div>
          <div className="md:col-span-1"><FluentWidget /></div>

          {/* wide forecast (2 cols) + tricky items tile */}
          <div className="md:col-span-2"><ForecastWidget /></div>
          <div className="md:col-span-2"><LeechWidget /></div>
        </div>
      </main>
    </Protected>
  );
}
