"use client";

import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { IntermissionGate } from "@/components/intermission-modal";
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
          {/* The customize controls live at the bottom of this grid now. */}
          <WidgetGrid />
        </div>

        <div className="mt-6 text-center">
          <GuidedTour />
        </div>
      </main>

      {/* Threshold intermissions ("you've learned 25 items") fire here, since
          the dashboard is where a learner lands after finishing anything. */}
      <IntermissionGate event="progress" />

      <Footer />
    </Protected>
  );
}
