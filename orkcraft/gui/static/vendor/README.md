# Vendored, unchanged

The page loads these as ES modules through the import map in `../index.html`; no build step.

| file | package | version | licence |
|---|---|---|---|
| `preact.mjs` | preact (`dist/preact.mjs`) | 11.0.0 | MIT |
| `preact-hooks.mjs` | preact (`hooks/dist/hooks.mjs`) | 11.0.0 | MIT |
| `htm.mjs` | htm (`dist/htm.mjs`) | 3.1.1 | Apache-2.0 |
| `preact-signals.mjs` | @preact/signals (`dist/signals.mjs`) | 2.11.3 | MIT |
| `signals-core.mjs` | @preact/signals-core (`dist/signals-core.mjs`) | 1.14.4 | MIT |

To update one: `npm pack <package>@<version>`, copy the same file over, change the table.
