/** Language switcher (slice 41): flag trigger + coming-soon for not-ready langs. */
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { LanguageSwitcher, flagFor } from "../language-switcher";

const active = jest.fn();
const list = jest.fn();
jest.mock("@/lib/languages-api", () => ({
  languages: {
    active: () => active(),
    list: () => list(),
    setActive: jest.fn(),
  },
}));

describe("flagFor", () => {
  it("maps known codes to flags", () => {
    expect(flagFor("es-MX")).toBe("🇲🇽");
    expect(flagFor("tl")).toBe("🇵🇭");
  });
  it("derives a flag from the region subtag", () => {
    expect(flagFor("xx-FR")).toBe("🇫🇷");
  });
  it("falls back to a globe for unknown codes", () => {
    expect(flagFor("zz")).toBe("🌐");
  });
});

describe("LanguageSwitcher", () => {
  beforeEach(() => {
    active.mockReset();
    list.mockReset();
  });

  it("shows the active language as a flag with an accessible name", async () => {
    active.mockResolvedValue({ code: "es-MX", name: "Spanish (Latin American)", ready: true });
    render(<LanguageSwitcher />);
    const trigger = await screen.findByRole("button", { name: /language: Spanish/i });
    expect(trigger.textContent).toContain("🇲🇽");
  });

  it("greys out a not-ready language and blocks selecting it", async () => {
    active.mockResolvedValue({ code: "es-MX", name: "Spanish", ready: true });
    list.mockResolvedValue([
      { code: "es-MX", name: "Spanish", ready: true },
      { code: "tl", name: "Tagalog", ready: false },
    ]);
    render(<LanguageSwitcher />);
    fireEvent.click(await screen.findByRole("button", { name: /language: Spanish/i }));

    const tagalog = await screen.findByText("Tagalog");
    const btn = tagalog.closest("button")!;
    expect(btn).toHaveAttribute("aria-disabled", "true");
    // a "coming soon" tooltip is present for the not-ready option
    expect(screen.getByRole("tooltip")).toHaveTextContent(/coming soon/i);
  });
});
