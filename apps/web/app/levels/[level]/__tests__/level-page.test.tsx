/** Level page (slice 40): shows grammar then vocabulary as clickable cards. */
import { render, screen, waitFor } from "@testing-library/react";
import LevelPage from "../page";

// next/navigation → fixed level param
jest.mock("next/navigation", () => ({ useParams: () => ({ level: "1" }) }));
// strip auth/layout wrappers for the unit test
jest.mock("@/components/protected", () => ({
  Protected: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock("@/components/header", () => ({ Header: () => null }));

const levelProgress = jest.fn();
jest.mock("@/lib/items-api", () => ({
  items: { levelProgress: (...a: unknown[]) => levelProgress(...a) },
}));

function item(over: Record<string, unknown>) {
  return {
    item_type: "vocabulary", item_id: "id", term: "term", translation: "gloss",
    part_of_speech: "noun", article: null, learned: false, srs_stage: 0,
    srs_stage_name: "Not learned", next_review_at: null, leech_state: "none",
    practice_stages: {}, practice_labels: {}, categories_complete: 0, perfect: false,
    ...over,
  };
}

const FIXTURE = {
  position: 1, title: "Level 1", unlocked: true,
  totals: { items: 3, learned: 1, not_started: 2, familiar_plus: 0, fluent: 0, perfect: 0, leeches: 0 },
  items: [
    item({ item_type: "grammar", item_id: "g1", term: "ser vs estar", translation: "to be", part_of_speech: "" }),
    item({ item_type: "vocabulary", item_id: "v1", term: "gato", translation: "cat", article: "el", learned: true, srs_stage: 1, srs_stage_name: "Beginner 1" }),
    item({ item_type: "vocabulary", item_id: "v2", term: "correr", translation: "to run", part_of_speech: "verb", perfect: true }),
  ],
};

describe("LevelPage", () => {
  beforeEach(() => levelProgress.mockReset());

  it("shows a loading state before data arrives", () => {
    levelProgress.mockReturnValue(new Promise(() => {})); // never resolves
    render(<LevelPage />);
    expect(screen.getByText(/un momento/i)).toBeInTheDocument();
  });

  it("renders grammar then vocabulary as cards linking to the item page", async () => {
    levelProgress.mockResolvedValue(FIXTURE);
    render(<LevelPage />);

    // section headers with counts
    await waitFor(() => expect(screen.getByText(/GRAMMAR · 1/)).toBeInTheDocument());
    expect(screen.getByText(/VOCABULARY · 2/)).toBeInTheDocument();

    // grammar card links to its item page
    const g = screen.getByText("ser vs estar").closest("a")!;
    expect(g).toHaveAttribute("href", "/items/grammar/g1");

    // vocab card shows the article and links correctly
    const v = screen.getByText("gato").closest("a")!;
    expect(v).toHaveAttribute("href", "/items/vocabulary/v1");
    expect(v.textContent).toContain("el");

    // grammar section renders before vocabulary section in the DOM
    const grammarHeader = screen.getByText(/GRAMMAR · 1/);
    const vocabHeader = screen.getByText(/VOCABULARY · 2/);
    expect(grammarHeader.compareDocumentPosition(vocabHeader) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows an empty state when the level has no items", async () => {
    levelProgress.mockResolvedValue({ ...FIXTURE, items: [] });
    render(<LevelPage />);
    await waitFor(() => expect(screen.getByText(/nothing in this level yet/i)).toBeInTheDocument());
  });

  it("shows an error state when the fetch fails", async () => {
    levelProgress.mockRejectedValue(new Error("level locked"));
    render(<LevelPage />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("level locked"));
  });
});
