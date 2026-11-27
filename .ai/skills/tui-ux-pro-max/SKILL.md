---
name: tui-ux-pro-max
description: "TUI/UX design intelligence for terminal interfaces built with Textual. Use when designing, building, reviewing, or fixing NetCore TUI screens, widgets, modals, themes, key bindings, layout, focus, color, glyphs, data tables, charts, feedback states, or keyboard interaction. Adapted from the web/mobile ui-ux-pro-max skill for terminal constraints: character cells, monospace fonts, keyboard-first input, limited color depth, and no images."
---

# TUI/UX Pro Max — Terminal Design Intelligence

Design and quality rules for keyboard-driven terminal UIs, tuned for
**Textual** and **NetCore TUI**. This is the terminal counterpart of the
web/mobile `ui-ux-pro-max` skill: touch targets become key bindings,
pixels become character cells, breakpoints become columns × rows, and
images/emoji become box-drawing characters and Unicode glyphs.

Project-specific source of truth stays in `docs/UI_SPEC.md`. This skill
explains *how* to apply it well; it never overrides the spec,
`CLAUDE.md`, or the human. If this skill and UI_SPEC disagree, follow
UI_SPEC and raise the gap with `.ai/skills/spec-change.md`.

## When to Apply

Apply when a task changes how the TUI **looks, reads, responds, or is
navigated**:

- new or refactored screen, modal or widget (`src/netcore/tui/**`)
- theme / `.tcss` changes, color, glyphs, spacing, borders
- key bindings, focus order, navigation between screens
- tables, trees, topology canvas, sparklines, utilization bars
- loading, empty, error and confirmation states
- UI review (CODE_REVIEWER §4.x, TUI_ENGINEER checklists)

Skip for domain logic, routing algorithms, SQL, or services — unless
their output shape changes what the user sees (e.g., a new DTO field
shown in a table).

## Rule Categories by Priority

Work top-down: fix category 1 before polishing category 10. Full rules
with rationale are in [references/quick-reference.md](references/quick-reference.md);
read the relevant section on demand.

| P | Category | Impact | Must have | Avoid |
| - | -------- | ------ | --------- | ----- |
| 1 | Accessibility & Legibility | CRITICAL | Contrast ≥ 4.5:1, status = glyph + text + color, works in 16-color and `NO_COLOR`, visible focus | Color-only meaning, removing focus border, dim text for important info |
| 2 | Keyboard Interaction | CRITICAL | Every action has a binding, footer shows primary keys, `escape` always backs out, predictable `tab` order | Mouse-only actions, bindings that fire inside text inputs, conflicting keys |
| 3 | Responsiveness & Performance | HIGH | Long work in `@work` workers, loading indicator, virtualised tables, debounced refresh | Blocking the event loop, full re-render every tick, unbounded tables |
| 4 | Visual Style Consistency | HIGH | One border style per role, one glyph set, theme tokens only | Emoji as icons, mixing ASCII and Unicode boxes, raw hex in widgets |
| 5 | Layout & Terminal Size | HIGH | Min 100×30 guard, `fr` units, breakpoints by columns, no horizontal overflow | Fixed widths that clip, content hidden off-screen, wrapping tables |
| 6 | Typography & Color | MEDIUM | Bold for hierarchy, dim only for secondary, semantic tokens (`$success` …) | Italic/underline as only emphasis, blinking text, rainbow palettes |
| 7 | Motion | LOW–MEDIUM | Motion only to show change (spinner, highlight flash), honours `TEXTUAL_ANIMATIONS` | Decorative animation, animated layout shifts, flashing > 3 Hz |
| 8 | Forms & Feedback | MEDIUM | Visible labels, inline error under field, toast for outcome, confirm destructive | Placeholder-only labels, errors only in toasts, silent failure |
| 9 | Navigation | HIGH | Number keys for screens, consistent per-screen actions, command palette, help overlay | Hidden screens, different keys for the same action on different screens |
| 10 | Data & Charts | MEDIUM | Units and "simulated" labels, numbers next to bars, legends | Bars without values, unlabeled axes, color-only series |

## Workflow

### Step 1 — Analyse the request

Extract:

- **Screen / component**: which UI_SPEC §5 screen or §6 widget.
- **User goal**: what the administrator is trying to do in one sentence.
- **Data shape**: which DTOs are displayed; how many rows at worst.
- **Interaction**: read-only, form, selection, destructive action, long-running job.
- **Terminal context**: min 100×30; consider 120 and 160 columns too.

Stack is fixed: **Python + Textual** (DEC-001). Do not suggest web or
mobile frameworks.

### Step 2 — Use the project design system

NetCore already has a design system; do not invent a new one.

| Need | Source |
| ---- | ------ |
| Color tokens, glyphs, focus style | `docs/UI_SPEC.md §3` → `src/netcore/tui/theme.tcss` |
| Global keys | `docs/UI_SPEC.md §4` → `src/netcore/tui/bindings.py` |
| Screen layouts | `docs/UI_SPEC.md §5` |
| Widget catalogue | `docs/UI_SPEC.md §6` |
| Breakpoints | `docs/UI_SPEC.md §7` |
| Error / empty states | `docs/UI_SPEC.md §9` |

**Master + overrides pattern (TUI version):**

- **Master** = `theme.tcss` global rules and tokens.
- **Screen override** = selectors scoped by screen id
  (`#packet-lab HopTraceTable { ... }`), kept in the same file under a
  `/* === packet-lab === */` section.
- New tokens or glyphs → update UI_SPEC §3 first (TUI_ENGINEER owns it;
  ARCHITECT reviews), then `theme.tcss`.

### Step 3 — Apply the priority rules

Walk the 10 categories for the component. For each, check the matching
section of `references/quick-reference.md`. Typical lookups:

| Situation | Read |
| --------- | ---- |
| Status badge or link state | §1 `status-triple-encoding`, §4 `glyph-set` |
| New list screen | §2 `list-screen-keys`, §3 `virtualise-tables`, §8 `empty-state` |
| Form modal | §2 `modal-keys`, §8 `inline-validation`, `focus-first-field` |
| Long simulation | §3 `worker-offload`, §7 `spinner-only`, §8 `progress-feedback` |
| Topology / diagram | §4 `box-drawing`, §5 `large-graph-fallback`, §10 `path-highlight` |
| Utilization display | §10 `bar-with-value`, `simulated-label`, §1 `threshold-not-color-only` |
| Dark theme contrast | §1 `contrast-table`, §6 `token-usage` |

### Step 4 — Textual implementation patterns

Use the patterns in `references/quick-reference.md §11` (workers,
bindings, focus, `notify`, `DataTable`, reactive updates). Also apply
`.ai/skills/textual-screen.md` for the screen file layout.

### Step 5 — Verify before delivery

Run the **Pre-Delivery Checklist** in
[references/quick-reference.md §12](references/quick-reference.md#12-pre-delivery-checklist),
then `.ai/skills/quality-gates.md`. Pilot tests must cover keyboard
paths. Manual checks that could not be done (e.g., no real terminal,
no 16-color terminal available) are reported as **unverified**.

## Verified Palette Contrast (UI_SPEC §3)

WCAG 2.x contrast ratios, computed from the hex values in UI_SPEC §3:

| Foreground | on `$background` #0d1117 | on `$surface` #161b22 | on `$panel` #1f2630 |
| ---------- | ------------------------ | --------------------- | ------------------- |
| Text #e6edf3      | 16.02 | 14.64 | 12.90 |
| `$secondary` #8b949e | 6.15 | 5.62 | 4.95 |
| `$primary` #2f81f7 | 5.05 | 4.62 | **4.07 ✖** |
| `$success` #3fb950 | 7.45 | 6.81 | 6.00 |
| `$warning` #d29922 | 7.50 | 6.85 | 6.04 |
| `$error` #f85149   | 5.65 | 5.16 | 4.55 |
| `$accent` #a371f7  | 5.64 | 5.16 | 4.54 |

Rule from this table: **do not use `$primary` as text color on `$panel`**
(table headers, modals). Use it there only as a border or a background
behind light text, or use bold text-colored foreground instead. Any new
color must be checked the same way before it enters `theme.tcss`.

## If Guidance Is Missing

Do not invent rules and present them as project standards. If neither
UI_SPEC nor this skill covers the case:

1. Choose the most conservative option consistent with the priority
   table (keyboard-first, readable, no color-only meaning).
2. Say in the report that it is a fallback, not a spec rule.
3. Propose a UI_SPEC addition via `.ai/skills/spec-change.md`.

## Differences From the Web/Mobile Skill

| Web/mobile concept | TUI equivalent here |
| ------------------ | ------------------- |
| Touch target 44×44 px | Key binding + visible footer hint; focusable widget ≥ 3 cells wide |
| Pixel breakpoints | Column/row breakpoints (100 / 120 / 160 cols, 30 rows) |
| SVG icons (no emoji) | Unicode glyphs from one set (`● ○ ◐ ✔ ✖ ▲ ▼ ►`), no emoji |
| Font pairings | Single monospace font (user's terminal); hierarchy via bold/dim/case/borders |
| Images, WebP, lazy-load | Not applicable; virtualise rows, defer heavy widgets |
| CSS / Tailwind | Textual CSS (`.tcss`) with theme variables |
| Hover states | Focus and highlight states (hover is optional, never required) |
| GSAP animation | Textual `animate`/`styles.animate`, spinners; minimal by default |
| Search script + CSV database | Not bundled; rules live in this skill and `docs/UI_SPEC.md` |
