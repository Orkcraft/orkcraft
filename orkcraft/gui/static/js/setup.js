// A building's setup in steps, the same for every type (docs/design/building-views.md §5): the Watchtower's
// Add a source, a Review board's setup, any wizard a type draws in its panel. A step past the first says so
// with `useSetupBack(id, back)`, and the panel puts ← Back in its bar's top right corner (js/windows.js),
// never in the step's own foot; when the setup is done, `setupDone` (js/windows.js) opens the building's Info.
import { signal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";

export const setupBack = signal({});        // building id → the step back of the setup under way

/** A setup's step: `back` takes it one step back; null on its first step (no ← Back there). */
export function useSetupBack(id, back) {
  const ref = useRef(back);
  ref.current = back;
  const on = !!back;
  useEffect(() => {
    if (!on) return undefined;
    const step = () => ref.current && ref.current();
    setupBack.value = { ...setupBack.value, [id]: step };
    return () => {
      if (setupBack.value[id] !== step) return;
      const { [id]: _, ...rest } = setupBack.value;
      setupBack.value = rest;
    };
  }, [id, on]);
}
