/**
 * Progress primitives.
 *
 * The assertions lean on accessible names rather than class names: the rule
 * these components exist to satisfy is "never colour alone" (PLANNING §29), so
 * if a screen reader can read the state, the component is doing its job.
 */
import { render, screen } from "@testing-library/react";
import {
  AccuracyBar, CategoryDots, LeechPill, PerfectBadge, PracticeStageRail,
  SrsPill, StagePips, stageTone,
} from "../progress-bits";
import type { PracticeStage } from "@/lib/items-api";

function stage(partial: Partial<PracticeStage>): PracticeStage {
  return {
    category: "sentences",
    stage: 0,
    max_stage: 5,
    label: "Not started",
    complete: false,
    on_cooldown: false,
    next_available_at: null,
    stage_reached_at: null,
    ...partial,
  } as PracticeStage;
}

describe("StagePips", () => {
  it("announces the stage as text, not just colour", () => {
    render(<StagePips stage={3} label="listening" />);
    expect(screen.getByLabelText("listening: 3 of 5 stages")).toBeInTheDocument();
  });
});

describe("PracticeStageRail", () => {
  it("names each category and its Spanish stage", () => {
    render(
      <PracticeStageRail
        stages={[
          stage({ category: "sentences", stage: 2, label: "Stage Dos" }),
          stage({ category: "listening", stage: 5, label: "Stage Cinco", complete: true }),
          stage({ category: "speaking" }),
        ]}
      />,
    );
    expect(screen.getByText("stage dos")).toBeInTheDocument();
    expect(screen.getByText("✓ complete")).toBeInTheDocument();
    expect(screen.getByText("not started")).toBeInTheDocument();
    expect(screen.getByText("speaking")).toBeInTheDocument();
  });

  it("explains the 24-hour wait when a category is cooling down", () => {
    const soon = new Date(Date.now() + 4 * 3600_000).toISOString();
    render(
      <PracticeStageRail
        stages={[stage({ stage: 1, label: "Stage Uno", on_cooldown: true, next_available_at: soon })]}
      />,
    );
    expect(screen.getByText(/next stage in 4 hrs/)).toBeInTheDocument();
  });
});

describe("PerfectBadge", () => {
  it("shows perfect once earned", () => {
    render(<PerfectBadge perfect />);
    expect(screen.getByText("perfect")).toBeInTheDocument();
  });

  it("shows the almost state when only the SRS is missing", () => {
    render(<PerfectBadge perfect={false} ready />);
    expect(screen.getByText("almost perfect")).toBeInTheDocument();
  });

  it("renders nothing when the item is nowhere near", () => {
    const { container } = render(<PerfectBadge perfect={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("LeechPill", () => {
  it("labels a tricky item in words", () => {
    render(<LeechPill state="leech" />);
    expect(screen.getByText("tricky item")).toBeInTheDocument();
  });

  it("renders nothing for a healthy item", () => {
    const { container } = render(<LeechPill state="none" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("SrsPill", () => {
  it("renders the stage name", () => {
    render(<SrsPill stage={5} name="Familiar 1" />);
    expect(screen.getByText("FAMILIAR 1")).toBeInTheDocument();
  });

  it("tones by stage group", () => {
    expect(stageTone(0)).not.toBe(stageTone(9));
    expect(stageTone(1)).toBe(stageTone(4));
    expect(stageTone(5)).toBe(stageTone(6));
  });
});

describe("AccuracyBar", () => {
  it("exposes the percentage to assistive tech", () => {
    render(<AccuracyBar correct={3} total={4} />);
    const meter = screen.getByRole("meter");
    expect(meter).toHaveAttribute("aria-valuenow", "75");
    expect(screen.getByText(/3 of 4 answers correct/)).toBeInTheDocument();
  });

  it("has an empty state instead of a divide by zero", () => {
    render(<AccuracyBar correct={0} total={0} />);
    expect(screen.getByText(/no answers yet/)).toBeInTheDocument();
  });
});

describe("CategoryDots", () => {
  it("summarises how many categories are finished", () => {
    render(
      <CategoryDots stages={{ sentences: 5, listening: 2, speaking: 0 }} />,
    );
    expect(
      screen.getByLabelText("1 of 3 practice categories complete"),
    ).toBeInTheDocument();
  });
});
