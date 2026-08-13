/** Onboarding (slice 45): spring slides, dots below the art, sticky footer.
 *  Motion is mocked so the test exercises structure/behavior, not animation. */
import { render, screen, fireEvent } from "@testing-library/react";
import WelcomePage from "../page";

// Mock Motion: motion.<tag> → the plain tag; AnimatePresence → passthrough.
jest.mock("motion/react", () => {
  const React = require("react");
  const motion = new Proxy(
    {},
    { get: (_t, tag: string) => (props: Record<string, unknown>) => {
        const { children, ...rest } = props as { children?: unknown };
        // drop animation-only props so they don't hit the DOM as attributes
        const { initial, animate, exit, variants, custom, transition, ...dom } = rest as Record<string, unknown>;
        void initial; void animate; void exit; void variants; void custom; void transition;
        return React.createElement(tag as string, dom, children as React.ReactNode);
      } },
  );
  return {
    motion,
    AnimatePresence: ({ children }: { children: React.ReactNode }) => children,
    useReducedMotion: () => true,
  };
});

jest.mock("@/components/protected", () => ({
  Protected: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
const push = jest.fn();
jest.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
jest.mock("@/lib/feedback-api", () => ({ onboarding: { complete: jest.fn().mockResolvedValue({}) } }));

describe("Onboarding", () => {
  beforeEach(() => push.mockReset());

  it("starts on the first slide with skip + next", () => {
    render(<WelcomePage />);
    expect(screen.getByText("bienvenido a polyglot")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /skip/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next/i })).toBeInTheDocument();
  });

  it("advances with next and shows back", () => {
    render(<WelcomePage />);
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText("learn it, then keep it")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back/i })).toBeInTheDocument();
  });

  it("renders the step-of announcement below the slide", () => {
    render(<WelcomePage />);
    expect(screen.getByText(/step 1 of 5/i)).toBeInTheDocument();
  });

  it("finishes on the last slide", () => {
    render(<WelcomePage />);
    const next = () => fireEvent.click(screen.getByRole("button", { name: /next|empezar/i }));
    next(); next(); next(); next(); // to slide 5
    expect(screen.getByText(/empezar/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /empezar/i }));
    expect(push).toHaveBeenCalledWith("/choose-language");
  });
});
