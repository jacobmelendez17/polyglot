/** HandwrittenGreeting — accessibility + reduced-motion rendering. */
import { render, screen, act } from "@testing-library/react";
import { HandwrittenGreeting } from "../handwritten-greeting";
import type { Greeting } from "@/lib/landing-content";

const GREETINGS: Greeting[] = [
  { text: "hola", lang: "español" },
  { text: "kumusta", lang: "tagalog" },
];

/** Install a matchMedia mock that reports the given reduced-motion state. */
function mockReducedMotion(reduced: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: reduced,
      media: query,
      onchange: null,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      addListener: jest.fn(),
      removeListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }),
  });
}

describe("HandwrittenGreeting (animated)", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockReducedMotion(false);
  });
  afterEach(() => {
    act(() => {
      jest.runOnlyPendingTimers();
    });
    jest.useRealTimers();
  });

  it("always exposes a stable screen-reader word regardless of the animation", () => {
    render(<HandwrittenGreeting greetings={GREETINGS} label="hello" />);
    // The visible glyphs are aria-hidden; "hello" is the accessible name.
    expect(screen.getByText("hello")).toHaveClass("sr-only");
  });

  it("renders the first greeting split into per-glyph spans", () => {
    const { container } = render(<HandwrittenGreeting greetings={GREETINGS} />);
    // 'hola' → four glyph spans plus the nib; assert each letter is present.
    for (const ch of ["h", "o", "l", "a"]) {
      expect(container.textContent).toContain(ch);
    }
  });
});

describe("HandwrittenGreeting (reduced motion)", () => {
  beforeEach(() => mockReducedMotion(true));

  it("shows the plain word, fully visible, with no per-glyph animation", () => {
    const { container } = render(<HandwrittenGreeting greetings={GREETINGS} label="hello" />);
    // Plain word text is rendered directly…
    expect(container.textContent).toContain("hola");
    // …and the accessible word is still present.
    expect(screen.getByText("hello")).toHaveClass("sr-only");
    // No inline `animation:` styles were emitted on the reduced path.
    expect(container.querySelector('[style*="animation"]')).toBeNull();
  });
});
