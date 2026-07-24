"use client";

import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { GuidedTour } from "@/components/tour";
import { WidgetGrid } from "@/components/widget-grid";
import { ActionButtons } from "@/components/widgets";

export default function DashboardPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-8">
        {/* Hero: the two big action buttons. Wrapped so the tour has something
            to point at without reaching inside the widgets module. */}
        <div data-tour="actions">
          <ActionButtons />
        </div>

        <div className="mt-4">
          <WidgetGrid />
        </div>

        <div className="mt-6 text-center">
          <GuidedTour />
        </div>
      </main>
    </Protected>
  );
}
