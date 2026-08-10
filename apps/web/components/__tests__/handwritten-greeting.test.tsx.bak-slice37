/** HandwrittenGreeting — a11y + rendering (animated and reduced-motion). */
import { render, screen, act } from "@testing-library/react";
import { HandwrittenGreeting } from "../handwritten-greeting";
import type { HeroWord } from "@/lib/hero-strokes";

const WORDS: HeroWord[] = [
  {
    text: "hi",
    lang: "english",
    vb: [0, 0, 20, 10],
    aspect: 2,
    totalLen: 30,
    strokes: [
      { d: "M0,0 L0,10", t: [0, 0], len: 10 },
      { d: "M5,0 L5,10", t: [0, 0], len: 20 },
    ],
  },
  {
    text: "ok",
    lang: "english",
    vb: [0, 0, 20, 10],
    aspect: 2,
    totalLen: 20,
    strokes: [{ d: "M0,0 L10,10", t: [0, 0], len: 20 }],
  },
];

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

  it("exposes a stable screen-reader word regardless of the animation", () => {
    render(<HandwrittenGreeting words={WORDS} label="hello" />);
    expect(screen.getByText("hello")).toHaveClass("sr-only");
  });

  it("draws the first word as SVG stroke paths (one per stroke)", () => {
    const { container } = render(<HandwrittenGreeting words={WORDS} label="hello" />);
    const paths = container.querySelectorAll("path");
    expect(paths).toHaveLength(WORDS[0].strokes.length);
    // While writing, each stroke starts hidden (dashoffset == its length).
    expect(paths[0].getAttribute("style")).toContain("stroke-dashoffset");
  });

  it("does not render any emoji/pen glyph text", () => {
    const { container } = render(<HandwrittenGreeting words={WORDS} label="hello" />);
    // Only the sr-only label should contribute readable text.
    expect(container.textContent).toBe("hello");
  });
});

describe("HandwrittenGreeting (reduced motion)", () => {
  beforeEach(() => mockReducedMotion(true));

  it("shows the word fully drawn with no animation", () => {
    const { container } = render(<HandwrittenGreeting words={WORDS} label="hello" />);
    const paths = container.querySelectorAll("path");
    expect(paths.length).toBe(WORDS[0].strokes.length);
    // No inline animation on the reduced path.
    expect(container.querySelector('[style*="animation"]')).toBeNull();
    // Accessible word still present.
    expect(screen.getByText("hello")).toHaveClass("sr-only");
  });
});
