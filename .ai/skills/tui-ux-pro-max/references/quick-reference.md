# TUI/UX Quick Reference

Rule ids are referenced from `../SKILL.md`. Each rule: **id** — rule —
*why*. "NetCore" notes tie the rule to `docs/UI_SPEC.md`.

---

## 1. Accessibility & Legibility (CRITICAL)

- **contrast-min** — Text ≥ 4.5:1 against its background; large/bold
  headings and borders ≥ 3:1. *Terminal fonts are thin; low contrast
  disappears on projectors and laptops.* NetCore: see the contrast table
  in SKILL.md.
- **contrast-table** — Re-compute contrast for every new token on all
  three surfaces (`$background`, `$surface`, `$panel`).
- **status-triple-encoding** — State is shown as glyph + word + color
  (`● online`, `○ offline`). *Color-blind users and monochrome
  terminals must read it.*
- **threshold-not-color-only** — Utilization thresholds show the number
  and, when high, a marker (`▲ 92 %`), not only a red bar.
- **no-color-fallback** — UI must remain usable with `NO_COLOR=1` or a
  16-color terminal: glyphs, bold and borders still convey structure.
- **focus-visible** — The focused widget always has a visible
  indicator (NetCore: `tall $primary` border; focused row bold +
  `$primary 30%` background). Never remove it for aesthetics.
- **dim-is-secondary** — `dim`/`$secondary` only for metadata
  (timestamps, hints). Never for errors, values or actions.
- **no-blink** — Do not use blinking text; avoid anything flashing
  more than 3 times per second.
- **readable-errors** — Error text says what happened and what to do
  ("10.0.1.0 is the network address of 10.0.1.0/24 — choose .1–.254").
- **screen-reader-limits** — Terminal screen-reader support is weak;
  prefer plain words over glyph-only content, and keep important text in
  the first columns of a row.

## 2. Keyboard Interaction (CRITICAL)

- **binding-for-everything** — Every action reachable by keyboard;
  mouse is optional. *Keyboard-first is a CLAUDE.md §09 requirement.*
- **footer-shows-primary** — Primary actions use `Binding(..., show=True)`
  so they appear in the footer; secondary ones go in the help overlay.
- **escape-backs-out** — `escape` closes a modal, clears a search, or
  cancels a pending selection — never quits the app.
- **no-binding-in-inputs** — Single-letter and number bindings must not
  fire while an `Input` has focus (check `self.focused` or use
  priority bindings carefully).
- **list-screen-keys** — Same keys on every list screen: `/` search,
  `n` new, `e`/`enter` edit, `d` delete, `r` refresh, `j`/`k`, `g`/`G`.
- **modal-keys** — First field focused on open; `tab` moves forward;
  `enter` on the last field or `ctrl+s` submits; `escape` cancels.
- **tab-order** — Focus order follows visual order (top→bottom,
  left→right). Set `can_focus=False` on decorative widgets.
- **confirm-destructive** — Delete/reset need a confirm modal naming the
  object and its side-effects; default focus on **Cancel**.
- **key-conflicts** — Check new bindings against UI_SPEC §4 before
  adding. Do not override terminal-reserved keys (`ctrl+c` handling,
  `ctrl+z`, `ctrl+s` may be swallowed by XON/XOFF on some terminals —
  provide an alternative).
- **min-focus-size** — Focusable widgets ≥ 3 cells wide and 1 row tall
  with padding, so the focus indicator is visible.

## 3. Responsiveness & Performance (HIGH)

- **worker-offload** — Anything that may take > 50 ms (simulation,
  traffic generation, lab load, export) runs in
  `@work(thread=True, exclusive=True, group=...)`.
- **main-thread-only-ui** — Touch widgets only from the main thread:
  `self.app.call_from_thread(...)` or post a `Message`.
- **progress-feedback** — Show a `LoadingIndicator` or spinner within
  100 ms of starting work; disable conflicting actions.
- **virtualise-tables** — Use `DataTable` (row virtualisation) for
  events and large lists; page or cap rows (events default 10 000).
- **debounce-refresh** — EventBus-driven refresh is debounced
  (NetCore: 500 ms dashboard); timers use `set_interval` ≥ 1 s for
  monitors.
- **incremental-update** — Update changed cells (`update_cell`) rather
  than clearing and rebuilding whole tables every tick.
- **cancel-on-leave** — Cancel or ignore results of workers whose
  screen is no longer active.

## 4. Visual Style Consistency (HIGH)

- **token-only** — Widgets use theme variables (`$success`, `$error`);
  no raw hex in Python or screen-specific CSS.
- **glyph-set** — One glyph vocabulary for the app:
  `● ○ ◐` state, `✔ ✖` result, `▲ ▼` up/down trend, `►` selection,
  `█ ▓ ░` bars, `┄` dashed/down link. Document new glyphs in UI_SPEC §3.
- **no-emoji** — No emoji as icons. *Emoji have inconsistent cell width
  across terminals and break alignment.*
- **box-drawing** — Use one border style per role: `round`/`tall` for
  panels, `heavy`/`tall $primary` for focus, `dashed` for disabled or
  down. Do not mix ASCII `+--+` with Unicode boxes.
- **east-asian-width** — Avoid ambiguous-width characters in aligned
  columns; test alignment with the glyph set at 100 columns.
- **consistent-casing** — Titles Title Case; status words lowercase;
  enum codes UPPER_SNAKE (`TTL_EXPIRED`) only where showing codes.

## 5. Layout & Terminal Size (HIGH)

- **min-size-guard** — Below 100×30 show "Terminal too small (need
  100×30, have W×H)" instead of a broken layout.
- **column-breakpoints** — NetCore: < 120 cols sidebar collapses,
  ≥ 120 side panels, ≥ 160 extra dashboard column. React to `Resize`.
- **fr-units** — Prefer `1fr`, percentages and `auto`; fixed widths only
  for narrow known content (sidebar 18 cols, status column).
- **no-horizontal-overflow** — Content fits the width; long text is
  truncated with `…` and available in a detail view.
- **table-column-priority** — Decide which columns drop or shrink first
  on narrow terminals (descriptions before hostnames/status).
- **large-graph-fallback** — Diagrams with more nodes than fit (NetCore:
  > 40 devices) switch to a list/adjacency view.
- **spacing-scale** — Use padding 0/1/2 cells consistently; one blank
  row between groups, none inside dense tables.

## 6. Typography & Color (MEDIUM)

- **hierarchy-by-weight** — Screen title bold; section headers bold +
  border title; values normal; metadata dim.
- **token-usage** — Semantic meaning only: `$success` ok/up/delivered,
  `$warning` degraded/maintenance, `$error` down/dropped/error,
  `$accent` highlight/selected path, `$primary` focus/active nav.
- **no-italic-only** — Many terminals render italic poorly; never rely
  on italic or underline as the only emphasis.
- **limited-palette** — ≤ 7 semantic colors on screen; avoid
  decorative gradients.
- **numbers-right-aligned** — Numeric columns right-aligned with fixed
  units in the header (`Load (Mbps, sim)`).
- **monospace-alignment** — Align IPs/MACs in columns; do not pad with
  tabs.

## 7. Motion (LOW–MEDIUM)

- **spinner-only** — Default motion is a spinner/loading indicator for
  work in progress.
- **change-highlight** — A brief highlight (≤ 500 ms) on a row that
  changed is allowed to draw attention; no repeated pulsing.
- **respect-animation-setting** — Honour Textual's animation level
  (`TEXTUAL_ANIMATIONS` / `App.animation_level`); with `none`, UI must be
  fully understandable.
- **no-layout-animation** — Do not animate size/position of panels;
  terminal redraws make it jumpy.

## 8. Forms & Feedback (MEDIUM)

- **visible-labels** — Every input has a label above or left of it;
  placeholder is only an example (`e.g. 10.0.1.10/24`).
- **inline-validation** — Shape checks (required, numeric range) on
  blur/submit in the UI; semantic errors from `ApplicationError` shown
  under the field with the `-invalid` class.
- **error-near-field** — Error message directly below the field, plus
  a toast for the overall outcome.
- **prefill-smart-defaults** — Prefill sensible values (next free IP,
  default TTL 64, default capacity 1000 Mbps).
- **success-toast** — Successful actions confirm with a short
  `notify(..., severity="information")`.
- **empty-state** — Empty lists explain why and what key to press
  ("No devices yet — press n to add one or load a sample lab in
  Settings (0).").
- **progress-feedback** — See §3; also show result summary on
  completion ("✔ DELIVERED in 5 hops").
- **no-silent-failure** — Unexpected exceptions are logged and shown as
  "Unexpected error — details in log file"; never swallowed.

## 9. Navigation (HIGH)

- **number-keys** — Screens `1`–`9`, `0` in UI_SPEC order; active item
  highlighted in the sidebar.
- **command-palette** — Every screen action is also available in
  `ctrl+p`.
- **help-overlay** — `?` lists the current screen's bindings.
- **preserve-context** — Returning to a screen keeps selection and
  filters (view state on the screen object) but refreshes data.
- **breadcrumbs-in-title** — Detail views show context in the border
  title (`Routing ─ r1`).
- **quit-safety** — `q` confirms when a worker is running or a form has
  unsaved input.

## 10. Data & Charts (MEDIUM)

- **bar-with-value** — Every bar shows its number (`███████░░ 72 %`).
- **simulated-label** — All traffic numbers carry "sim" or a
  "simulated" caption (NETWORK_SPEC §1, DEC-011).
- **units-in-header** — Units in column headers, not repeated in cells.
- **sparkline-context** — Sparklines show min/max or current value next
  to them.
- **legend-required** — Multi-series charts have a legend using glyph +
  color.
- **path-highlight** — Highlighted paths use `$accent` and a glyph/style
  change (bold line, `►` markers), not color alone.
- **time-in-utc** — Timestamps in UTC with explicit label (UI_SPEC header).

## 11. Textual Implementation Patterns

```python
# Bindings: primary in footer, secondary in help
BINDINGS = [
    Binding("n", "new", "New"),
    Binding("d", "delete", "Delete"),
    Binding("ctrl+h", "history", "History", show=False),
]


# Worker for long operations
@work(thread=True, exclusive=True, group="packet-lab")
def run_simulation(self, request: SendPacketRequest) -> None:
    result = self._simulation.send_packet(request)
    self.app.call_from_thread(self._show_result, result)


# Error handling at the UI edge
try:
    dto = self._ipam.assign_address(request)
except ApplicationError as exc:
    self.query_one("#ip-error", Static).update(exc.message)
    self.notify(exc.message, severity="error", timeout=8)
else:
    self.notify("Address assigned", severity="information")


# Too-small guard
def on_resize(self, event: events.Resize) -> None:
    too_small = event.size.width < 100 or event.size.height < 30
    self.set_class(too_small, "-too-small")
```

```css
/* theme.tcss — focus and status tokens */
*:focus { border: tall $primary; }
DataTable > .datatable--cursor { background: $primary 30%; text-style: bold; }
.status-online  { color: $success; }
.status-offline { color: $error; }
.status-maint   { color: $warning; }
```

## 12. Pre-Delivery Checklist

Copy into the task report and tick each item.

**Accessibility & legibility**
- [ ] All text/background pairs ≥ 4.5:1 (new tokens checked)
- [ ] Every status shows glyph + word + color
- [ ] Usable with `NO_COLOR=1` (structure still readable)
- [ ] Focus indicator visible on every focusable widget

**Keyboard**
- [ ] Every action has a binding; primary ones in footer
- [ ] `escape` closes modals / clears search
- [ ] Bindings do not fire inside inputs
- [ ] Destructive actions confirm, default focus on Cancel
- [ ] Pilot test covers the main keyboard path

**Responsiveness**
- [ ] Long work in workers; loading indicator shown
- [ ] No UI touched from worker threads directly
- [ ] Large tables virtualised / capped

**Layout**
- [ ] Works at 100×30, 120×40, 160×50
- [ ] Too-small message below 100×30
- [ ] No horizontal overflow; long text truncated with `…`

**Style**
- [ ] Theme tokens only, no raw hex outside `theme.tcss`
- [ ] Glyphs from the documented set; no emoji
- [ ] Border styles consistent with role

**Feedback**
- [ ] Labels visible; inline errors under fields
- [ ] Empty, loading, error states implemented (UI_SPEC §9)
- [ ] Success and failure toasts

**Data**
- [ ] Values shown next to bars; units in headers
- [ ] Simulated numbers labelled as simulated

Items that could not be checked (no real terminal, no 16-color
terminal) are marked **unverified** with the reason.
