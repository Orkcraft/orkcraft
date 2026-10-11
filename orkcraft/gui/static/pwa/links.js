// The roads on the phone (docs/design/mobile.md §10): not drawn as lines — a phone's grid has no map — but as
// the grid's order, one block per chain of linked buildings, each in the order its work flows; and on a long
// press, a building's neighbours lit. `roads` is the compact snapshot's [from, to] pairs.

/** {into: id → [ids it sends to], from: id → [ids it takes from]}. */
export function links(roads) {
  const into = new Map();
  const from = new Map();
  for (const [a, b] of roads || []) {
    if (!into.has(a)) into.set(a, []);
    if (!from.has(b)) from.set(b, []);
    into.get(a).push(b);
    from.get(b).push(a);
  }
  return { into, from };
}

/** The buildings in chains: each group the buildings linked by roads (either way), sources first and the rest
 *  as the work flows (a loop keeps the town's order), the groups in the town's order of their first building;
 *  then one group of the buildings no road touches. [{linked, ids}]. */
export function chains(ids, roads) {
  const { into, from } = links(roads);
  const order = new Map(ids.map((id, i) => [id, i]));
  const byOrder = (x, y) => order.get(x) - order.get(y);
  const seen = new Set();
  const groups = [];
  const alone = [];
  for (const id of ids) {
    if (seen.has(id)) continue;
    const part = [];                    // the component, by a walk over the roads both ways
    const stack = [id];
    seen.add(id);
    while (stack.length) {
      const at = stack.pop();
      part.push(at);
      for (const next of [...(into.get(at) || []), ...(from.get(at) || [])]) {
        if (order.has(next) && !seen.has(next)) { seen.add(next); stack.push(next); }
      }
    }
    if (part.length === 1) { alone.push(id); continue; }
    groups.push({ linked: true, ids: flow(part.sort(byOrder), into, from) });
  }
  if (alone.length) groups.push({ linked: false, ids: alone });
  return groups;
}

// Kahn's order inside one chain: a building comes once every building it takes from has; ties (and a loop's
// rest) by the town's order, which `part` is sorted in.
function flow(part, into, from) {
  const inside = new Set(part);
  const left = new Map(part.map((id) => [id, (from.get(id) || []).filter((x) => inside.has(x) && x !== id).length]));
  const out = [];
  const done = new Set();
  while (out.length < part.length) {
    let next = part.find((id) => !done.has(id) && left.get(id) === 0);
    if (next === undefined) next = part.find((id) => !done.has(id));      // a loop: take the first left
    done.add(next);
    out.push(next);
    for (const to of into.get(next) || []) if (inside.has(to) && !done.has(to)) left.set(to, left.get(to) - 1);
  }
  return out;
}
