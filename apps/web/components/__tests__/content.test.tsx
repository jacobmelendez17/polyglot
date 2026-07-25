/**
 * The intermission popup and the footer.
 *
 * The popup's job is to be easy to leave — there's nothing to answer — and to
 * render admin-authored text without ever handing it to innerHTML.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { IntermissionCard, renderEmphasis } from "../intermission-modal";
import { Footer } from "../footer";
import { changelog } from "@/lib/content-api";

jest.mock("@/lib/content-api", () => ({
  changelog: { unread: jest.fn(), list: jest.fn(), markRead: jest.fn() },
  intermissions: { pending: jest.fn(), markViewed: jest.fn(), history: jest.fn() },
  immersion: { get: jest.fn(), set: jest.fn() },
  CHANGELOG_TYPE_LABEL: { feature: "new" },
}));

jest.mock("@/lib/i18n", () => ({
  useUiText: () => ({ t: (k: string) => k.split(".").pop() ?? k, locale: "en" }),
}));

const item = {
  id: "abc",
  title: "the five vowels never move",
  body: "Spanish vowels are steady.\n\nGive every vowel its **full value**.",
  kind: "pronunciation",
  trigger_description: "starting level 1",
  viewed_at: null,
};

describe("IntermissionCard", () => {
  it("shows the title and body as paragraphs", () => {
    render(<IntermissionCard intermission={item} onClose={jest.fn()} />);
    expect(screen.getByText(item.title)).toBeInTheDocument();
    expect(screen.getByText(/Spanish vowels are steady/)).toBeInTheDocument();
  });

  it("labels the kind of reading", () => {
    render(<IntermissionCard intermission={item} onClose={jest.fn()} />);
    expect(screen.getByText("HOW IT SOUNDS")).toBeInTheDocument();
  });

  it("is a labelled modal dialog", () => {
    render(<IntermissionCard intermission={item} onClose={jest.fn()} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName(item.title);
  });

  it("closes on the button", () => {
    const onClose = jest.fn();
    render(<IntermissionCard intermission={item} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "got it" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("closes on Escape", () => {
    const onClose = jest.fn();
    render(<IntermissionCard intermission={item} onClose={onClose} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("says how many more are queued", () => {
    render(<IntermissionCard intermission={item} remaining={2} onClose={jest.fn()} />);
    expect(screen.getByText("2 MORE")).toBeInTheDocument();
  });

  it("does not announce a count when it is the last one", () => {
    render(<IntermissionCard intermission={item} remaining={0} onClose={jest.fn()} />);
    expect(screen.queryByText(/MORE/)).not.toBeInTheDocument();
  });
});

describe("renderEmphasis", () => {
  it("turns **bold** into a strong element", () => {
    render(<p>{renderEmphasis("give it **full value** now")}</p>);
    expect(screen.getByText("full value").tagName).toBe("STRONG");
  });

  it("renders markup in the source as literal text, never as HTML", () => {
    // Admin-authored is not the same as safe: one compromised editor account
    // should not become stored XSS.
    render(<p>{renderEmphasis("<img src=x onerror=alert(1)>")}</p>);
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });

  it("leaves plain text alone", () => {
    render(<p>{renderEmphasis("nothing special here")}</p>);
    expect(screen.getByText("nothing special here")).toBeInTheDocument();
  });
});

describe("Footer", () => {
  beforeEach(() => {
    (changelog.unread as jest.Mock).mockResolvedValue({ unread: 0, last_read_at: null });
  });

  it("links to the pages that exist", async () => {
    render(<Footer />);
    expect(await screen.findByRole("link", { name: /changelog/ }))
      .toHaveAttribute("href", "/changelog");
    expect(screen.getByRole("link", { name: /intermissions/ }))
      .toHaveAttribute("href", "/intermissions");
  });

  it("marks unbuilt destinations as soon rather than linking to a 404", () => {
    render(<Footer />);
    expect(screen.queryByRole("link", { name: /pricing/ })).not.toBeInTheDocument();
    expect(screen.getAllByText("SOON").length).toBeGreaterThan(0);
  });

  it("shows an unread badge on the changelog", async () => {
    (changelog.unread as jest.Mock).mockResolvedValue({ unread: 3, last_read_at: null });
    render(<Footer />);
    expect(await screen.findByLabelText("3 unread")).toBeInTheDocument();
  });

  it("still renders when the unread count cannot be fetched", async () => {
    (changelog.unread as jest.Mock).mockRejectedValue(new Error("signed out"));
    render(<Footer />);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: /changelog/ })).toBeInTheDocument(),
    );
  });

  it("groups links under labelled navs", () => {
    render(<Footer />);
    expect(screen.getByRole("navigation", { name: "Product" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Resources" })).toBeInTheDocument();
  });
});
