// The v3 sprites (design-system/sprites/v3/, cut by tools/camp_sheet.py --v3): their manifest, read once, says which
// are cut, each one's frame and frame count. A sprite is drawn at its own art pixel times its layer's zoom, never
// resampled (design-system-v3.md §3).
import { signal } from "@preact/signals";

export const V3 = "/ds/sprites/v3/";
export const kit = signal(null);           // file → {w, h, frames} (a frame's size), once the manifest is read

let asked = false;
/** Reads the manifest once; `kit` is set when it is here (an empty kit when it cannot be read: blocks are drawn). */
export function loadKit() {
  if (asked) return;
  asked = true;
  fetch(`${V3}manifest.json`).then((r) => (r.ok ? r.json() : { sprites: [] })).catch(() => ({ sprites: [] })).then((m) => {
    const out = {};
    for (const s of m.sprites || []) {
      const [w, h] = s.frame || s.size || [0, 0];
      out[s.file] = { w, h, frames: s.frames || 1, show: s.show || 1 };
    }
    kit.value = out;
  });
}

/** A sprite's [w, h] in art px (one frame), or null when it is not cut. */
export const sizeOf = (file) => {
  const s = kit.value && kit.value[file];
  return s ? [s.w * s.show, s.h * s.show] : null;
};

export const has = (file) => !!(kit.value && kit.value[file]);

/** An ork's sprite by its orkish name (`orks/roles/taskmaster.png`), else the plain capped ork. */
export function orkSprite(name, anim = "idle") {
  const role = `orks/roles/${String(name || "").toLowerCase().replace(/[^a-z]/g, "")}.png`;
  if (anim === "idle" && has(role)) return role;
  return `orks/body/${anim}.png`;
}
