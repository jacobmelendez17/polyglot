/** Profile page (slice 42): tabs for profile, achievements, add-friends. */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import ProfilePage from "../page";

jest.mock("@/components/protected", () => ({
  Protected: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock("@/components/header", () => ({ Header: () => null }));

const getProfile = jest.fn();
jest.mock("@/lib/account-api", () => ({
  account: {
    getProfile: () => getProfile(),
    updateProfile: jest.fn(),
  },
}));

const PROFILE = {
  display_name: "Jacob", bio: "hola", timezone: "America/Phoenix",
  email: "j@example.com", role: "owner",
  xp_total: 1200, points_balance: 0, rank_level: 5,
  streak_current: 7, streak_best: 9, immersion_unlocked: false,
};

describe("ProfilePage tabs", () => {
  beforeEach(() => getProfile.mockReset());

  it("shows the profile tab with editable name and stats by default", async () => {
    getProfile.mockResolvedValue(PROFILE);
    render(<ProfilePage />);
    await waitFor(() => expect(screen.getByDisplayValue("Jacob")).toBeInTheDocument());
    expect(screen.getByText("1200")).toBeInTheDocument(); // xp stat
  });

  it("switches to achievements (coming soon, no fabricated data)", async () => {
    getProfile.mockResolvedValue(PROFILE);
    render(<ProfilePage />);
    await waitFor(() => screen.getByDisplayValue("Jacob"));
    fireEvent.click(screen.getByRole("tab", { name: "achievements" }));
    expect(screen.getByText(/no achievements yet/i)).toBeInTheDocument();
  });

  it("opens the add-friends panel from the icon", async () => {
    getProfile.mockResolvedValue(PROFILE);
    render(<ProfilePage />);
    await waitFor(() => screen.getByDisplayValue("Jacob"));
    fireEvent.click(screen.getByRole("tab", { name: /add friends/i }));
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
  });
});
