"use client";

import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import {
  ForecastWidget, LessonWidget, ProgressionWidget, ReviewsWidget,
  WelcomeWidget, XpWidget,
} from "@/components/widgets";

export default function DashboardPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <WelcomeWidget />
          <ReviewsWidget />
          <LessonWidget />
          <ProgressionWidget />
          <XpWidget />
          <ForecastWidget />
        </div>
      </main>
    </Protected>
  );
}
