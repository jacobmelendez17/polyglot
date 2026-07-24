/**
 * The guided tour. The behaviours worth pinning are the ones that make a modal
 * overlay safe: it never traps you, Escape always works, and a finished tour
 * does not come back on its own.
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { GuidedTour, type TourStep } from "../tour";
import { tours } from "@/lib/dashboard-api";

jest.mock("@/lib/dashboard-api", () => ({
  tours: {
    get: jest.fn(),
    step: jest.fn(),
    complete: jest.fn(),
    restart: jest.fn(),
  },
}));

const mocked = tours as jest.Mocked<typeof tours>;

const STEPS: TourStep[] = [
  { anchor: "one", title: "first stop", body: "body one" },
  { anchor: "two", title: "second stop", body: "body two" },
  { anchor: "three", title: "third stop", body: "body three" },
];

function state(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    tour_key: "dashboard", step_index: 0, completed: false,
    skipped: false, completed_at: null, ...overrides,
  } as never;
}

beforeEach(() => {
  jest.clearAllMocks();
  mocked.step.mockResolvedValue(state());
  mocked.complete.mockResolvedValue(state({ completed: true }));
  mocked.restart.mockResolvedValue(state());
});

async function renderTour(initial = state()) {
  mocked.get.mockResolvedValue(initial);
  const view = render(<GuidedTour steps={STEPS} />);
  await screen.findByRole("dialog").catch(() => null);
  return view;
}

describe("GuidedTour", () => {
  it("starts at the first step for someone who has not seen it", async () => {
    await renderTour();
    expect(await screen.findByText("first stop")).toBeInTheDocument();
    expect(screen.getByText("STEP 1 OF 3")).toBeInTheDocument();
  });

  it("does not start for someone who already finished it", async () => {
    mocked.get.mockResolvedValue(state({ completed: true, completed_at: "now" }));
    render(<GuidedTour steps={STEPS} />);
    await waitFor(() =>
      expect(screen.getByText("replay the tour")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("resumes where the learner left off", async () => {
    await renderTour(state({ step_index: 2 }));
    expect(await screen.findByText("third stop")).toBeInTheDocument();
  });

  it("advances with the next button and records the step", async () => {
    await renderTour();
    fireEvent.click(await screen.findByRole("button", { name: "next" }));
    expect(await screen.findByText("second stop")).toBeInTheDocument();
    expect(mocked.step).toHaveBeenCalledWith("dashboard", 1);
  });

  it("advances and goes back with the arrow keys", async () => {
    await renderTour();
    await screen.findByText("first stop");
    act(() => { fireEvent.keyDown(window, { key: "ArrowRight" }); });
    expect(await screen.findByText("second stop")).toBeInTheDocument();
    act(() => { fireEvent.keyDown(window, { key: "ArrowLeft" }); });
    expect(await screen.findByText("first stop")).toBeInTheDocument();
  });

  it("escape skips the tour and records it as skipped", async () => {
    await renderTour();
    await screen.findByText("first stop");
    act(() => { fireEvent.keyDown(window, { key: "Escape" }); });
    await waitFor(() =>
      expect(mocked.complete).toHaveBeenCalledWith("dashboard", true),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("the skip button is available on every step", async () => {
    await renderTour();
    expect(await screen.findByRole("button", { name: "skip" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "next" }));
    expect(await screen.findByRole("button", { name: "skip" })).toBeInTheDocument();
  });

  it("the last step finishes rather than skipping", async () => {
    await renderTour(state({ step_index: 2 }));
    fireEvent.click(await screen.findByRole("button", { name: "done" }));
    await waitFor(() =>
      expect(mocked.complete).toHaveBeenCalledWith("dashboard", false),
    );
  });

  it("has no back button on the first step", async () => {
    await renderTour();
    await screen.findByText("first stop");
    expect(screen.queryByRole("button", { name: "back" })).not.toBeInTheDocument();
  });

  it("is a labelled modal dialog", async () => {
    await renderTour();
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName("first stop");
  });

  it("shows progress as text, not only as dots", async () => {
    await renderTour(state({ step_index: 1 }));
    expect(await screen.findByText("STEP 2 OF 3")).toBeInTheDocument();
  });

  it("survives a failed state lookup instead of blocking the dashboard", async () => {
    mocked.get.mockRejectedValue(new Error("offline"));
    render(<GuidedTour steps={STEPS} />);
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });

  it("keeps running when a step cannot be saved", async () => {
    mocked.step.mockRejectedValue(new Error("offline"));
    await renderTour();
    fireEvent.click(await screen.findByRole("button", { name: "next" }));
    expect(await screen.findByText("second stop")).toBeInTheDocument();
  });

  it("replays only when explicitly asked", async () => {
    mocked.get.mockResolvedValue(state({ completed: true, completed_at: "now" }));
    render(<GuidedTour steps={STEPS} />);
    fireEvent.click(await screen.findByText("replay the tour"));
    await waitFor(() => expect(mocked.restart).toHaveBeenCalledWith("dashboard"));
    expect(await screen.findByText("first stop")).toBeInTheDocument();
  });
});
