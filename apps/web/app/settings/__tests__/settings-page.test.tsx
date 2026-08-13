/** Settings page (slice 42): left sidebar switches setting categories. */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import SettingsPage from "../page";

jest.mock("@/components/protected", () => ({
  Protected: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock("@/components/header", () => ({ Header: () => null }));
jest.mock("@/lib/auth-context", () => ({ useAuth: () => ({ logout: jest.fn() }) }));

const getSettings = jest.fn();
jest.mock("@/lib/account-api", () => ({
  account: { getSettings: () => getSettings(), updateSettings: jest.fn() },
}));

const SETTINGS = {
  theme: "system", font_size: "md", color_theme: "terraza",
  lesson_batch_size: 5, review_order: "newest_first", curriculum_mode: "default_dispersed",
  back_to_back: true, back_to_back_order: "es_first", show_srs_indicator: true,
  leech_threshold: 1, review_batch_enabled: true, review_batch_size: 20,
  reveal_full_answer: false, allow_cheating: false, allow_skipping: false, undo_enabled: true,
  accept_user_synonyms: false, intermissions_enabled: true, immersion_mode: false,
  dialect: "latam_mx", audio_autoplay: true, audio_voice: "", audio_rate: 1,
  immersion_unlocked: false,
};

describe("Settings sidebar", () => {
  beforeEach(() => getSettings.mockReset());

  it("renders all six categories in the sidebar", async () => {
    getSettings.mockResolvedValue(SETTINGS);
    render(<SettingsPage />);
    await waitFor(() => screen.getByRole("navigation", { name: /settings sections/i }));
    for (const label of ["lessons", "reviews", "appearance", "curriculum", "intermissions", "danger zone"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("defaults to lessons and switches panels on sidebar click", async () => {
    getSettings.mockResolvedValue(SETTINGS);
    render(<SettingsPage />);
    // lessons panel shows the batch-size control
    await waitFor(() => expect(screen.getByText("batch size")).toBeInTheDocument());

    // switch to appearance → theme control appears
    fireEvent.click(screen.getByRole("button", { name: "appearance" }));
    expect(screen.getByText("theme")).toBeInTheDocument();

    // danger zone → log out + delete controls
    fireEvent.click(screen.getByRole("button", { name: "danger zone" }));
    expect(screen.getByRole("button", { name: "log out" })).toBeInTheDocument();
    expect(screen.getByText("delete account")).toBeInTheDocument();
  });
});
