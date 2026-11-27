# NetCore TUI — User Interface Specification

| Field          | Value                                 |
| -------------- | ------------------------------------- |
| Owner          | TUI_ENGINEER (author), ARCHITECT (review) |
| Status         | Approved baseline v1.0                |
| Framework      | Textual (Python)                      |
| Last updated   | 2026-11-27                            |

---

## 1. Design Principles

1. **Keyboard-first.** Every action has a binding; mouse is optional.
2. **One screen, one job.** Each screen maps to one service area.
3. **Show state, explain decisions.** Status uses text + icon + color.
4. **Never block.** Simulation, traffic and lab load run in workers
   with a visible progress/loading state.
5. **Errors are readable.** Show `ApplicationError.message`; never a
   raw traceback in the UI.
6. **Simulated is labelled.** Any traffic number displays a `sim`
   tag or the caption "simulated".
7. **No business logic in widgets.** Widgets render DTOs and emit
   messages; screens call services.

## 2. Global Layout

Minimum terminal size: **100 × 30**. Below that, show a centred
"Terminal too small (need 100×30, have W×H)" message instead of the
layout.

```
┌ NetCore TUI ─ lab: dc-spine-leaf ─────────────────── ● 12 online  ▲ 1 offline ─ 14:02 UTC ┐
│┌ Navigation ────┐┌ <Screen Title> ─────────────────────────────────────────────────────┐ │
││ 1 Dashboard    ││                                                                     │ │
││ 2 Devices      ││                         screen content                              │ │
││ 3 IPAM         ││                                                                     │ │
││ 4 Routing      ││                                                                     │ │
││ 5 Switch Ports ││                                                                     │ │
││ 6 Topology     ││                                                                     │ │
││ 7 Packet Lab   ││                                                                     │ │
││ 8 Traffic      ││                                                                     │ │
││ 9 Event Logs   ││                                                                     │ │
││ 0 Settings     ││                                                                     │ │
│└────────────────┘└─────────────────────────────────────────────────────────────────────┘ │
│ q Quit  ? Help  ctrl+p Commands  / Search  n New  e Edit  d Delete  r Refresh              │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Header:** app name, lab name, online/offline counts, UTC clock.
- **Sidebar** (`NavigationSidebar` widget, 18 cols): screen list with
  number keys; collapsible with `ctrl+b` (auto-collapsed below 120
  cols).
- **Content:** active screen.
- **Footer:** Textual `Footer` showing context bindings.
- **Toasts:** Textual `notify()` — severity `information`, `warning`,
  `error`; errors stay 8 s, others 4 s.

## 3. Theme

Dark theme defined in `tui/theme.tcss` using Textual design tokens.

| Token / role       | Value     | Use |
| ------------------ | --------- | --- |
| `$background`      | `#0d1117` | App background |
| `$surface`         | `#161b22` | Panels |
| `$panel`           | `#1f2630` | Table header, modal |
| `$primary`         | `#2f81f7` | Focus ring, active nav item |
| `$secondary`       | `#8b949e` | Muted text |
| `$success`         | `#3fb950` | ONLINE, DELIVERED, link up |
| `$warning`         | `#d29922` | MAINTENANCE, WARNING, utilization 70–90 % |
| `$error`           | `#f85149` | OFFLINE, DROPPED, ERROR, utilization > 90 % |
| `$accent`          | `#a371f7` | Highlighted path, selected hop |
| Text               | `#e6edf3` | Default foreground |

Status glyphs (always paired with text):

| State           | Glyph | Text          |
| --------------- | ----- | ------------- |
| ONLINE / up     | `●`   | `online`/`up` |
| OFFLINE / down  | `○`   | `offline`/`down` |
| MAINTENANCE     | `◐`   | `maint`       |
| DELIVERED       | `✔`   | `delivered`   |
| DROPPED         | `✖`   | `dropped`     |

Focus indicator: focused widget has a `tall $primary` border; focused
table row uses `$primary 30%` background and bold text.

## 4. Global Key Bindings

| Key            | Action                          | Scope |
| -------------- | ------------------------------- | ----- |
| `1`…`9`, `0`   | Switch to screen 1–10           | Global (not in inputs) |
| `tab` / `shift+tab` | Move focus                 | Global |
| `ctrl+p`       | Command palette                 | Global |
| `?`            | Help overlay for current screen | Global |
| `ctrl+b`       | Toggle sidebar                  | Global |
| `q` / `ctrl+q` | Quit (confirm if worker running)| Global |
| `escape`       | Close modal / clear search      | Global |
| `/`            | Focus search/filter input       | List screens |
| `n`            | New item (opens form modal)     | List screens |
| `e` / `enter`  | Edit / open selected            | List screens |
| `d` / `delete` | Delete selected (confirm modal) | List screens |
| `r`            | Refresh from service            | All screens |
| `j` / `k`      | Move down / up in tables        | Tables |
| `g` / `G`      | First / last row                | Tables |

## 5. Screens

Each screen lives in `tui/screens/<name>.py` as a `Screen` subclass,
named `<Name>Screen`, with a stable `id` used by tests.

### 5.1 Dashboard (`1`, id `dashboard`)

Purpose: health overview at a glance.

```
┌ Dashboard ───────────────────────────────────────────────────────────┐
│ ┌ Devices ──────┐ ┌ Links ────────┐ ┌ Subnets ──────┐ ┌ Events (1h) ─┐│
│ │ 14 total      │ │ 18 total      │ │ 6 subnets     │ │ 3 warnings   ││
│ │ ● 12 online   │ │ ● 17 up       │ │ 41 % used     │ │ 0 errors     ││
│ │ ○ 1  offline  │ │ ○ 1  down     │ │               │ │              ││
│ │ ◐ 1  maint    │ │               │ │               │ │              ││
│ └───────────────┘ └───────────────┘ └───────────────┘ └──────────────┘│
│ ┌ Top link utilization (simulated) ───┐ ┌ Recent events ─────────────┐│
│ │ r1:ge0/0 ↔ r2:ge0/0  ███████░░ 72 % │ │ 14:01 WARN link down sw-b… ││
│ │ sw-a:24  ↔ r1:ge0/1  ███░░░░░░ 31 % │ │ 13:58 INFO route added r1… ││
│ └─────────────────────────────────────┘ └────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

- Widgets: `StatCard` ×4, `UtilizationBar` list, `EventFeed` (last 10).
- Auto-refresh on EventBus events (debounced 500 ms).
- Service: `MonitoringService.dashboard_summary()`.

### 5.2 Device Management (`2`, id `devices`)

- `DataTable`: Hostname, Type, Status, Interfaces, Location, Description.
- Filter bar: text search + type select + status select.
- Actions: `n` add (modal `DeviceFormModal`: hostname, type, interface
  count, location, description), `e` edit, `d` delete (confirm lists
  links/routes that will be removed), `s` toggle status cycle
  ONLINE → OFFLINE → MAINTENANCE.
- Detail panel (right, 40 %): interfaces with IP/MAC/link peer.
- Service: `DeviceService`.

### 5.3 IP Address Management (`3`, id `ipam`)

- Left: subnet table (CIDR, Name, Gateway, Total, Used, Free, Util %).
- Right: addresses in selected subnet (IP, Device, Interface, MAC).
- Actions: `n` add subnet, `a` assign address (modal with device +
  interface selects, IP input pre-filled with next free), `x` release
  address, `d` delete subnet (blocked if in use).
- Validation errors from service displayed inline under the field
  (`Input` with `.-invalid` class) and as toast.
- Service: `IpamService`.

### 5.4 Routing Table (`4`, id `routing`)

- Router selector (`Select`) at top.
- `DataTable`: Type (C/S/D), Destination, Next Hop, Interface, AD,
  Metric. Connected routes shown read-only (dimmed, cannot delete).
- Route lookup bar: input `dst IP` → highlights the matching row and
  shows "Matched 10.1.0.0/16 (prefix /16) via 10.0.0.3 ge0/1" or "No
  route".
- Actions: `n` add static route, `d` delete static route.
- Service: `RoutingService`.

### 5.5 Switch Port Management (`5`, id `switch-ports`)

- Switch selector.
- Port grid view (`PortGrid` widget): 12 per row, each cell `[ 7 ●]`
  coloured by state; arrow keys move between ports.
- Port detail: number, admin state, speed, description, connected
  peer, counters.
- MAC table tab: MAC, Port, Age (sim s).
- Actions: `space` toggle admin up/down, `e` edit port, `c` clear MAC
  table.
- Service: `SwitchService`.

### 5.6 Network Topology (`6`, id `topology`)

- `TopologyCanvas` widget rendering a layered layout:
  routers top row, switches middle, servers bottom; links drawn with
  box-drawing characters; down links dashed `┄` in `$error`.
- Arrow keys move selection between nodes; `enter` opens device detail.
- `l` add link (modal: device A/interface A, device B/interface B,
  capacity), `u` toggle selected link up/down.
- Last simulated path highlighted in `$accent` (toggle `h`).
- Fallback for large topologies (> 40 devices): adjacency list view
  (`t` toggles canvas/list).
- Service: `TopologyService`.

### 5.7 Packet Simulation Lab (`7`, id `packet-lab`)

```
┌ Packet Lab ──────────────────────────────────────────────────────────┐
│ Source [srv-a      ▼]  Destination IP [10.0.2.10    ]  Proto [ICMP ▼]│
│ TTL [64 ]  Size [64  ]  Mode (•) Single ( ) Traceroute   [ Send ⏎ ]  │
├──────────────────────────────────────────────────────────────────────┤
│ Result: ✔ DELIVERED   hops 5   TTL 64→62   latency 0.32 ms (sim)     │
│ #  Kind     Device  In→Out          TTL    Decision                  │
│ 0  SEND     srv-a   –→eth0          64     gw 10.0.1.1 (off-subnet)  │
│ 1  ARP      r1      ge0/1           –      10.0.1.1 is-at 02:…:11    │
│ 3  ROUTE    r1      ge0/1→ge0/0     64→63  10.0.2.0/24 via 10.0.12.2 │
│ …                                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

- Form validation: required fields; TTL 1–255; size 64–9000.
- `ctrl+enter` or `Send` button runs simulation in a worker; a
  `LoadingIndicator` replaces the table while running; form disabled.
- `HopTraceTable` widget; selecting a row shows full `reason` text in
  a detail strip.
- DROPPED shows reason in `$error` with explanation, e.g.
  "✖ DROPPED — TTL_EXPIRED at r1 (TTL reached 0)".
- History list (last 20 runs) on `ctrl+h`.
- Service: `SimulationService`.

### 5.8 Traffic Monitor (`8`, id `traffic`)

- Link table: Link, Capacity (Mbps), Load (Mbps, sim), Utilization
  bar, Tx/Rx packets, Drops.
- Device table: Device, Tx/Rx packets/bytes, Drops (top reason).
- Flow panel: active flows with remaining duration.
- `f` start flow (modal: src, dst IP, proto, size, pps, duration).
- `x` stop selected flow. `z` reset counters (confirm).
- Header caption: "All values are simulated by NetCore — not real
  measurements."
- Refresh tick: 1 s via `set_interval`, reading `MonitoringService`.

### 5.9 Event Logs (`9`, id `events`)

- `DataTable` (virtualised): Time (UTC), Severity, Category, Device,
  Message.
- Filters: severity multi-select, category select, device select, text
  search, time range (last 15 m / 1 h / 24 h / all).
- `enter` opens event detail modal showing JSON payload.
- `E` export filtered events (CSV/JSON) to a path chosen in a modal;
  path validated, never overwrites without confirmation.
- Live tail toggle `t` (auto-scroll on new events).
- Service: `EventLogService`.

### 5.10 Settings (`0`, id `settings`)

- Form: default TTL, default link capacity, ARP timeout, MAC table
  timeout, max hops, event retention, simulation seed, DB path
  (read-only, shown), theme (dark only in v1).
- `ctrl+s` save; invalid values highlighted inline.
- Lab actions: Load sample lab (spine-leaf / two-router), Reset lab
  (double confirm: type lab name).
- Service: `SettingsService`.

## 6. Reusable Widgets (`tui/widgets/`)

| Widget              | Input DTO                  | Emits message           |
| ------------------- | -------------------------- | ----------------------- |
| `NavigationSidebar` | list of screen entries     | `NavigateRequested(id)` |
| `StatCard`          | title, value, breakdown    | —                       |
| `StatusBadge`       | status enum                | —                       |
| `UtilizationBar`    | pct, capacity, label       | —                       |
| `EventFeed`         | list[`EventDTO`]           | `EventSelected(id)`     |
| `FilterBar`         | filter spec                | `FilterChanged(spec)`   |
| `PortGrid`          | list[`SwitchPortDTO`]      | `PortSelected(n)`, `PortToggleRequested(n)` |
| `TopologyCanvas`    | `TopologyDTO`, highlighted path | `NodeSelected(id)` |
| `HopTraceTable`     | `SimulationResultDTO`      | `HopSelected(index)`    |
| `FormField`         | label, input, error text   | —                       |

Modals (`tui/modals/`): `ConfirmModal`, `DeviceFormModal`,
`SubnetFormModal`, `AssignAddressModal`, `RouteFormModal`,
`LinkFormModal`, `PortEditModal`, `FlowFormModal`, `ExportModal`,
`EventDetailModal`, `HelpModal`.

All modals: `escape` cancels, `ctrl+s`/`enter` on last field submits,
first field focused on open.

## 7. Responsive Rules

| Width       | Behaviour |
| ----------- | --------- |
| < 100 cols  | "Terminal too small" screen |
| 100–119     | Sidebar collapsed to numbers only; detail panels stacked below tables |
| ≥ 120       | Full sidebar; side-by-side detail panels |
| ≥ 160       | Dashboard shows 3-column bottom row |

Height < 30 rows → too-small message. Tables always fill available
height (`height: 1fr`).

## 8. Async & State Rules

- Service calls that can exceed 50 ms run in `@work(thread=True,
  exclusive=True, group="<screen>")`.
- Workers post results back with `self.app.call_from_thread` or
  Textual messages; UI widgets are only touched on the main thread.
- EventBus → TUI bridge: `TuiEventBridge` subscribes to the bus and
  posts `DomainEventReceived` messages to the App; screens refresh on
  relevant categories.
- Screens hold only view state (selection, filters). Lab state lives in
  the database; screens re-query services on `on_screen_resume`.

## 9. Error & Empty States

| Situation           | UI behaviour |
| ------------------- | ------------ |
| Validation error    | Inline field error + toast (`error`). |
| Not found           | Toast `warning`, refresh list. |
| Unexpected error    | Toast "Unexpected error — details in log file", event `SYSTEM/ERROR`. |
| Empty list          | Centred hint, e.g. "No devices yet — press n to add one or load a sample lab in Settings (0)." |
| Worker running      | Loading indicator; conflicting actions disabled. |

## 10. TUI Test Requirements

Using `App.run_test()` and `Pilot` (pytest-asyncio):

- AT-12: press `1`…`0` → assert `app.screen.id` for each screen.
- Each list screen: `n` opens its modal; `escape` closes it.
- Device add flow end-to-end against an in-memory SQLite service stack.
- Packet lab: submit form → wait for worker → result label contains
  `DELIVERED` on the reference topology.
- Too-small terminal: `run_test(size=(80, 24))` shows the warning.
- Snapshot tests (`pytest-textual-snapshot`) are optional and require
  a human-approved dependency addition.
