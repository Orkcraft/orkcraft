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
      out[s.file] = { w, h, frames: s.frames || 1, show: s.show || 1, doorway: s.doorway || null, hd: s.hd || null };
    }
    kit.value = out;
  });
}

/** A sprite's [w, h] in art px (one frame), or null when it is not cut. */
export const sizeOf = (file) => {
  const s = kit.value && kit.value[file];
  return s ? [s.w * s.show, s.h * s.show] : null;
};

/** A length on a whole device pixel (an ork's box and place: no sprite drawn across a pixel's edge, so none smoothed). */
export const dev = (v) => { const d = (typeof window !== "undefined" && window.devicePixelRatio) || 1; return Math.round(v * d) / d; };

/** A sprite's file for a zoom `S` (CSS px per art px): on a screen of density 2 or more, its high-density cut
 *  (tools/camp_hd.py) whose image pixels fall one on one device pixel — `S × dpr / 2` is the cut's step — else today's
 *  sprite. `hd`: whether it is the high-density one (drawn smooth, `is-hd`: at one to one nothing is resampled). */
export function orkFile(file, S) {
  const d = (typeof window !== "undefined" && window.devicePixelRatio) || 1, s = kit.value && kit.value[file];
  const k = (S * d) / 2, hd = d >= 2 && s && s.hd && Object.entries(s.hd).find(([step]) => Math.abs(Number(step) - k) < 1e-6);
  return hd ? { url: V3 + hd[1], hd: true } : { url: V3 + file, hd: false };
}

/** The same for a sprite drawn `w` CSS px wide (one frame). */
export const hdSrc = (file, w) => { const s = sizeOf(file); return orkFile(file, s ? w / s[0] : 0); };

export const has = (file) => !!(kit.value && kit.value[file]);

/** A building sprite's doorway, [x, y, w, h] in art px from its top left (tools/doorways.py), or null when it has none. */
export const doorwayOf = (file) => (kit.value && kit.value[file] && kit.value[file].doorway) || null;

/** An ork's sprite by its orkish name (`orks/roles/taskmaster.png`), else the plain capped ork. */
export function orkSprite(name, anim = "idle") {
  const role = `orks/roles/${String(name || "").toLowerCase().replace(/[^a-z]/g, "")}.png`;
  if (anim === "idle" && has(role)) return role;
  return `orks/body/${anim}.png`;
}
