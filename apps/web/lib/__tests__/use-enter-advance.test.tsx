/**
 * The Enter-to-continue shortcut.
 *
 * The interesting cases are all the ones where Enter must NOT advance:
 * auto-repeat, modifier combos, a focused button (which already activates on
 * Enter), and the brief arming window right after the feedback panel appears.
 */
import { fireEvent, render } from "@testing-library/react";
import { useEnterAdvance } from "../use-enter-advance";

function Harness({
  active, onAdvance, armDelayMs = 0,
}: { active: boolean; onAdvance: () => void; armDelayMs?: number }) {
  useEnterAdvance({ active, onAdvance, armDelayMs });
  return (
    <div>
      <button type="button">continue</button>
      <textarea aria-label="notes" />
    </div>
  );
}

describe("useEnterAdvance", () => {
  it("advances on Enter while the feedback panel is showing", () => {
    const onAdvance = jest.fn();
    render(<Harness active onAdvance={onAdvance} />);
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onAdvance).toHaveBeenCalledTimes(1);
  });

  it("does nothing while the learner is still answering", () => {
    const onAdvance = jest.fn();
    render(<Harness active={false} onAdvance={onAdvance} />);
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onAdvance).not.toHaveBeenCalled();
  });

  it("ignores other keys", () => {
    const onAdvance = jest.fn();
    render(<Harness active onAdvance={onAdvance} />);
    fireEvent.keyDown(window, { key: "a" });
    fireEvent.keyDown(window, { key: " " });
    expect(onAdvance).not.toHaveBeenCalled();
  });

  it("ignores key auto-repeat so holding Enter cannot skip a session", () => {
    const onAdvance = jest.fn();
    render(<Harness active onAdvance={onAdvance} />);
    fireEvent.keyDown(window, { key: "Enter", repeat: true });
    expect(onAdvance).not.toHaveBeenCalled();
  });

  it("ignores Enter with a modifier held", () => {
    const onAdvance = jest.fn();
    render(<Harness active onAdvance={onAdvance} />);
    fireEvent.keyDown(window, { key: "Enter", shiftKey: true });
    fireEvent.keyDown(window, { key: "Enter", metaKey: true });
    fireEvent.keyDown(window, { key: "Enter", ctrlKey: true });
    fireEvent.keyDown(window, { key: "Enter", altKey: true });
    expect(onAdvance).not.toHaveBeenCalled();
  });

  it("leaves a focused button to its own activation, so it fires once", () => {
    const onAdvance = jest.fn();
    const { getByRole } = render(<Harness active onAdvance={onAdvance} />);
    fireEvent.keyDown(getByRole("button"), { key: "Enter" });
    expect(onAdvance).not.toHaveBeenCalled();
  });

  it("does not steal Enter from a textarea", () => {
    const onAdvance = jest.fn();
    const { getByLabelText } = render(<Harness active onAdvance={onAdvance} />);
    fireEvent.keyDown(getByLabelText("notes"), { key: "Enter" });
    expect(onAdvance).not.toHaveBeenCalled();
  });

  it("stays disarmed during the arming window", () => {
    const onAdvance = jest.fn();
    render(<Harness active onAdvance={onAdvance} armDelayMs={5000} />);
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onAdvance).not.toHaveBeenCalled();
  });

  it("stops listening once the feedback panel goes away", () => {
    const onAdvance = jest.fn();
    const { rerender } = render(<Harness active onAdvance={onAdvance} />);
    rerender(<Harness active={false} onAdvance={onAdvance} />);
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onAdvance).not.toHaveBeenCalled();
  });

  it("removes its listener on unmount", () => {
    const onAdvance = jest.fn();
    const { unmount } = render(<Harness active onAdvance={onAdvance} />);
    unmount();
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onAdvance).not.toHaveBeenCalled();
  });
});
