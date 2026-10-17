// One thing the v1 shell's panes share: a redraw that does not wipe what the person is doing. A pane drawn with `replaceChildren`
// would lose a half-typed line or an open "Drop this result?" whenever the town changed something else, so it is drawn again
// only when what it shows changed, and not while a field in it has the focus (the next change draws it).

/** `steady(el)` → `(signature) => boolean`: true when `el` should be drawn now. */
export function steady(el) {
  let last = null;
  return (signature) => {
    const on = document.activeElement;
    const typing = on && el.contains(on) && /^(INPUT|TEXTAREA)$/.test(on.tagName);
    if (typing || signature === last) return false;
    last = signature;
    return true;
  };
}
