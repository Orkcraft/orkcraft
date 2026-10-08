// A box that scrolls says so where scrollbars are overlay (macOS, phones, headless) and show only while
// scrolling: its edge that has more fades (`.gui-scrolls[data-more]`, layout.css), in both looks (ui.md U03).
// A box with nothing more to show has no fade, and the fade at the bottom goes once it is scrolled to its end.
import { useEffect, useRef } from "preact/hooks";

const EDGE_PX = 2;               // within this of the end counts as the end (fractional scroll positions)

/** What `el` has beyond its edges: "above", "below", "above below" or "". */
export function moreOf(el) {
  const above = el.scrollTop > EDGE_PX, below = el.scrollTop + el.clientHeight < el.scrollHeight - EDGE_PX;
  return [above && "above", below && "below"].filter(Boolean).join(" ");
}

/** Keeps `ref.current`'s `data-more` true as it scrolls, resizes or its content changes — also when the box
 *  mounts after the first render (a dialog's) or is replaced. */
export function useScrollCue(ref) {
  const bound = useRef(null);                  // { el, stop } of the box it watches
  useEffect(() => {
    const el = ref.current;
    if (bound.current && bound.current.el === el) return;
    if (bound.current) bound.current.stop();
    bound.current = el ? { el, stop: watch(el) } : null;
  });
  useEffect(() => () => { if (bound.current) bound.current.stop(); bound.current = null; }, []);
}

function watch(el) {
  const mark = () => { const m = moreOf(el); if (el.dataset.more !== m) el.dataset.more = m; };
  mark();
  el.addEventListener("scroll", mark, { passive: true });
  const sized = typeof ResizeObserver === "function" ? new ResizeObserver(mark) : null;
  if (sized) { sized.observe(el); for (const c of el.children) sized.observe(c); }
  const changed = typeof MutationObserver === "function" ? new MutationObserver(mark) : null;
  if (changed) changed.observe(el, { childList: true, subtree: true });
  return () => { el.removeEventListener("scroll", mark); if (sized) sized.disconnect(); if (changed) changed.disconnect(); };
}
