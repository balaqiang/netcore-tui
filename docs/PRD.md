# NetCore TUI — Product Requirements Document (PRD)

| Field          | Value                                                     |
| -------------- | --------------------------------------------------------- |
| Product        | NetCore TUI — Data Center Network Management & Traffic Simulator |
| Document owner | ORCHESTRATOR (maintained), human product owner (approves) |
| Status         | Draft v1.0 — approved baseline for Phase 1                |
| Last updated   | 2026-11-27                                                |
| Related docs   | ARCHITECTURE.md, NETWORK_SPEC.md, UI_SPEC.md, UML.md      |

---

## 1. Product Summary

NetCore TUI is a Python terminal application (Textual framework) that
simulates the management of network infrastructure inside a data center.
The user acts as a **Network Administrator** who:

- manages routers, switches and servers,
- allocates and validates IPv4 addresses (IPAM),
- configures routing tables,
- connects devices through links and switch ports,
- visualizes the network topology,
- simulates packet forwarding hop by hop,
- monitors device status and traffic statistics,
- reads an audit trail of network events,
- injects failures (device down, link down) to practise troubleshooting.

All networking behaviour is **virtual**. The application never touches
physical infrastructure or the host network stack. Its value is
educational: it makes routing, switching, subnetting, packet forwarding,
TTL and ARP observable and explainable, while mirroring part of a
professional data center administrator's workflow.

The project is developed with **Spec-Driven Development**,
**Hierarchical Multi-Agent Orchestration** and **Skill-Based Execution**
(see `CLAUDE.md` and `.ai/`).

## 2. Problem Statement

Students and junior engineers learning networking usually lack access to
real data center equipment. Existing simulators are either GUI-heavy,
proprietary, or hide the forwarding decision process. Learners need a
lightweight, keyboard-driven tool that:

1. Runs anywhere a terminal runs.
2. Shows *why* a packet was forwarded or dropped at every hop.
3. Enforces real protocol rules (CIDR validation, longest prefix match,
   TTL, MAC-based switching) instead of shortcuts.
4. Persists lab setups so they can be resumed and shared.

The original UTS (mid-term) codebase provided a minimal OOP foundation
but contained protocol errors (see `.ai/context/PROJECT_STATE.md`,
"Known Issues"). NetCore TUI corrects these while preserving the OOP
class model.

## 3. Goals and Non-Goals

### 3.1 Goals

| ID   | Goal                                                                 |
| ---- | -------------------------------------------------------------------- |
| G-01 | Provide a correct, deterministic simulation of L2 switching and L3 routing for IPv4. |
| G-02 | Provide a professional, keyboard-first Textual interface with 10 screens. |
| G-03 | Persist topology, configuration and event history in SQLite.        |
| G-04 | Make every forwarding decision explainable (trace per hop).         |
| G-05 | Support failure injection and troubleshooting workflows.            |
| G-06 | Keep a clean layered architecture that AI agents can extend safely. |
| G-07 | Enforce quality gates: pytest, Ruff (lint + format), ty (types).    |

### 3.2 Non-Goals (Out of Scope for v1)

| ID    | Non-goal                                                            |
| ----- | ------------------------------------------------------------------- |
| NG-01 | Real device integration (SSH, SNMP, NETCONF, RESTCONF).             |
| NG-02 | Sending or capturing real packets (raw sockets, pcap).             |
| NG-03 | IPv6, VLAN trunking (802.1Q), STP, dynamic routing (OSPF/BGP/RIP).  |
| NG-04 | NAT, ACL/firewall rule engines, QoS queueing models.               |
| NG-05 | Multi-user access, authentication, remote/web UI.                  |
| NG-06 | Real throughput/latency measurement of the host machine.           |

Non-goals may be revisited only through a human-approved change to this
PRD and a new decision record in `.ai/context/DECISIONS.md`.

## 4. Personas

| Persona               | Description                                   | Primary needs |
| --------------------- | --------------------------------------------- | ------------- |
| **Student (primary)** | Networking / OOP course student.              | Learn routing, subnetting, TTL; see explanations. |
| **Junior NetAdmin**   | Practising DC operations before production.   | Build topologies fast, simulate failures, read logs. |
| **Lecturer**          | Prepares lab scenarios and grades results.    | Reproducible scenarios, saved labs, clear event logs. |
| **Developer / Agent** | Human or AI contributor extending the code.   | Clear specs, stable interfaces, fast test suite. |

## 5. User Stories

Format: `US-<area>-<n>` — *As a … I want … so that …*.
Priority uses MoSCoW (M = Must, S = Should, C = Could).

### 5.1 Device Management (DEV)

| ID       | Story | Priority |
| -------- | ----- | -------- |
| US-DEV-1 | As an admin I want to add a router, switch or server with a unique hostname so that I can build a topology. | M |
| US-DEV-2 | As an admin I want to edit a device's hostname, description and location (rack/row). | M |
| US-DEV-3 | As an admin I want to delete a device, with its links and interfaces cleaned up, after confirmation. | M |
| US-DEV-4 | As an admin I want to set a device online/offline so that I can simulate failures. | M |
| US-DEV-5 | As an admin I want to filter and search the device list by type, status and name. | S |

### 5.2 Interfaces & IPAM (IP)

| ID      | Story | Priority |
| ------- | ----- | -------- |
| US-IP-1 | As an admin I want to define subnets in CIDR notation and see their capacity and usage. | M |
| US-IP-2 | As an admin I want to assign an IPv4 address/prefix to a device interface and have it validated against its subnet. | M |
| US-IP-3 | As an admin I want duplicate IP and MAC addresses to be rejected with a readable error. | M |
| US-IP-4 | As an admin I want the system to suggest the next free address in a subnet. | S |
| US-IP-5 | As an admin I want to release an address back to the pool. | M |

### 5.3 Routing (RT)

| ID      | Story | Priority |
| ------- | ----- | -------- |
| US-RT-1 | As an admin I want to add static routes (destination CIDR, next hop, egress interface, metric). | M |
| US-RT-2 | As an admin I want connected routes to appear automatically when an interface gets an address. | M |
| US-RT-3 | As an admin I want to configure a default route (0.0.0.0/0). | M |
| US-RT-4 | As an admin I want to test which route a destination IP would match (route lookup tool). | S |
| US-RT-5 | As an admin I want invalid next hops (not on a connected subnet) to be rejected. | M |

### 5.4 Switching (SW)

| ID      | Story | Priority |
| ------- | ----- | -------- |
| US-SW-1 | As an admin I want to see all ports of a switch with status, speed and connected peer. | M |
| US-SW-2 | As an admin I want to enable/disable (admin up/down) a switch port. | M |
| US-SW-3 | As an admin I want to inspect and clear the MAC address table. | M |
| US-SW-4 | As an admin I want invalid port numbers to be rejected. | M |

### 5.5 Links & Topology (TOP)

| ID       | Story | Priority |
| -------- | ----- | -------- |
| US-TOP-1 | As an admin I want to connect two device interfaces with a link that has a bandwidth capacity. | M |
| US-TOP-2 | As an admin I want to set a link up/down to simulate cable failure. | M |
| US-TOP-3 | As an admin I want an ASCII/Unicode topology view showing devices, links and their status. | M |
| US-TOP-4 | As an admin I want to see path highlighting for the last simulated packet. | C |

### 5.6 Packet Simulation (SIM)

| ID       | Story | Priority |
| -------- | ----- | -------- |
| US-SIM-1 | As a student I want to send a simulated packet (src host, dst IP, protocol, TTL, size) and see delivered/dropped. | M |
| US-SIM-2 | As a student I want a hop-by-hop trace with the decision made at each hop (ARP, MAC lookup, route match, TTL). | M |
| US-SIM-3 | As a student I want drop reasons to be explicit (no route, TTL expired, device offline, link down, ARP failure, port down). | M |
| US-SIM-4 | As a student I want to run a traceroute-style simulation with increasing TTL. | S |
| US-SIM-5 | As a lecturer I want to replay a saved simulation result. | C |

### 5.7 Traffic Monitoring (TRF)

| ID       | Story | Priority |
| -------- | ----- | -------- |
| US-TRF-1 | As an admin I want per-device and per-link counters (packets/bytes forwarded, dropped). | M |
| US-TRF-2 | As an admin I want simulated link utilization (%) clearly separated from link capacity. | M |
| US-TRF-3 | As an admin I want to generate a simulated traffic flow (N packets at a rate) between two hosts. | S |
| US-TRF-4 | As an admin I want top-talkers and most-dropped lists. | C |

### 5.8 Events & Logs (LOG)

| ID       | Story | Priority |
| -------- | ----- | -------- |
| US-LOG-1 | As an admin I want every configuration change and forwarding/drop decision recorded as an event. | M |
| US-LOG-2 | As an admin I want to filter events by severity, category, device and time range. | M |
| US-LOG-3 | As an admin I want to export events to CSV/JSON. | C |

### 5.9 Settings & Persistence (SET)

| ID       | Story | Priority |
| -------- | ----- | -------- |
| US-SET-1 | As a user I want my lab saved automatically to SQLite and restored at startup. | M |
| US-SET-2 | As a user I want to configure default TTL, default link bandwidth and ARP cache timeout. | S |
| US-SET-3 | As a user I want to load a sample data-center lab (spine-leaf) to start quickly. | S |
| US-SET-4 | As a user I want to reset the lab after confirmation. | M |

## 6. Functional Requirements

Requirements are traceable to user stories and to tests. Every `FR` must
be covered by at least one automated test before it is marked done in
`.ai/context/TASKS.md`.

### 6.1 Device Management

- **FR-DEV-01** The system shall support device types `ROUTER`, `SWITCH`, `SERVER`.
- **FR-DEV-02** Hostnames shall be unique (case-insensitive), 1–63 chars, matching `^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$`.
- **FR-DEV-03** Each device shall have a status: `ONLINE`, `OFFLINE`, `MAINTENANCE`.
- **FR-DEV-04** Deleting a device shall delete its interfaces, links, routes referencing it and IP assignments, in one transaction.
- **FR-DEV-05** Default port counts: switch 24 ports (configurable 1–96); router 4 interfaces (1–16); server 2 NICs (1–8).

### 6.2 IPAM

- **FR-IP-01** IPv4 addresses and CIDR prefixes shall be validated with `ipaddress` semantics (strict network for subnets).
- **FR-IP-02** An interface address must belong to an existing subnet and must not be the network or broadcast address (except /31 and /32 per RFC 3021 semantics).
- **FR-IP-03** Duplicate IPv4 addresses across the whole lab shall be rejected.
- **FR-IP-04** Duplicate MAC addresses shall be rejected; MACs are generated deterministically and unique (locally administered, `02:xx:...`).
- **FR-IP-05** Overlapping subnets shall be rejected unless explicitly marked as a sub-allocation of a parent subnet.
- **FR-IP-06** The IPAM view shall show total hosts, used, free, utilization % per subnet.

### 6.3 Routing

- **FR-RT-01** Route lookup shall use **longest prefix match** on integer prefix comparison (never string prefix comparison).
- **FR-RT-02** Ties on prefix length are broken by lowest administrative distance, then lowest metric, then insertion order.
- **FR-RT-03** Connected routes (AD 0) are derived automatically from interface addresses; static routes have AD 1.
- **FR-RT-04** A static route's next hop must be inside a connected subnet of the router at creation time.
- **FR-RT-05** Routers decrement TTL by 1 per hop; a packet whose TTL reaches 0 is dropped with `TTL_EXPIRED`.

### 6.4 Switching

- **FR-SW-01** Switches forward using **destination MAC** only; they never inspect the IP header.
- **FR-SW-02** Switches learn source MAC → ingress port; unknown unicast is flooded to all up ports except ingress.
- **FR-SW-03** Port numbers outside `1..port_count` raise `InvalidPortError`.
- **FR-SW-04** Admin-down ports neither receive nor transmit.

### 6.5 Links

- **FR-LNK-01** A link connects exactly two interfaces on two different devices; an interface has at most one link.
- **FR-LNK-02** A link has `capacity_mbps` (configured) and `utilization_pct` (simulated, derived from simulated traffic). They are never conflated.
- **FR-LNK-03** Forwarding over a link that is down or whose endpoint device is offline drops the packet.

### 6.6 Simulation

- **FR-SIM-01** Simulation is deterministic given the same topology, inputs and seed.
- **FR-SIM-02** Simulation runs off the UI thread (Textual worker) and never freezes the interface.
- **FR-SIM-03** Every hop produces a `HopRecord`; the run produces a `SimulationResult` with status `DELIVERED` or `DROPPED` and a `DropReason`.
- **FR-SIM-04** A hard hop limit (default 64) guards against forwarding loops independent of TTL.
- **FR-SIM-05** Simulated ARP shall be explicit and visible in the trace (see NETWORK_SPEC §7).

### 6.7 Monitoring & Events

- **FR-MON-01** Counters are derived only from simulated events; the UI shall label them "simulated".
- **FR-EVT-01** Events have timestamp (UTC), severity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`), category, device id (optional), message, structured payload (JSON).
- **FR-EVT-02** Events are persisted; retention default 10,000 most recent rows (configurable).

### 6.8 Persistence

- **FR-DB-01** SQLite database stored at `$XDG_DATA_HOME/netcore/netcore.db` (fallback `~/.local/share/netcore/`), overridable by `--db PATH` or `NETCORE_DB`.
- **FR-DB-02** Schema changes use numbered, forward-only migrations; destructive migrations require human approval.
- **FR-DB-03** All writes go through repositories inside a unit-of-work transaction.

## 7. Non-Functional Requirements

| ID      | Category        | Requirement |
| ------- | --------------- | ----------- |
| NFR-01  | Performance     | Single packet simulation over ≤ 50 hops completes in < 50 ms on a typical laptop. |
| NFR-02  | Performance     | Lab with 200 devices / 400 links loads in < 1 s. |
| NFR-03  | Responsiveness  | UI input latency < 100 ms; long operations run in workers with progress indication. |
| NFR-04  | Portability     | Linux, macOS, Windows Terminal; min terminal size 100×30, graceful message below that. |
| NFR-05  | Reliability     | No unhandled exception reaches the user; errors shown as notifications and logged. |
| NFR-06  | Maintainability | Domain layer has ≥ 90 % line coverage; overall ≥ 80 %. |
| NFR-07  | Quality         | `pytest`, `ruff check`, `ruff format --check`, `ty check` all pass on main. |
| NFR-08  | Security        | No network sockets, no shell execution from the TUI, no credentials in source. |
| NFR-09  | Accessibility   | Every action reachable by keyboard; status never conveyed by color alone (icon/text too). |
| NFR-10  | Python          | Python ≥ 3.12, type hints on all public functions. |

## 8. Acceptance Test Scenarios (Mandatory)

These map directly to `CLAUDE.md §11` and must exist as automated tests.

| ID     | Scenario                         | Expected result |
| ------ | -------------------------------- | --------------- |
| AT-01  | Successful packet delivery       | server-A → server-B across 2 routers: `DELIVERED`, TTL decreased by 2. |
| AT-02  | Invalid IPv4 address             | `10.0.0.256` rejected with `InvalidAddressError`. |
| AT-03  | Duplicate IP address             | Second assignment of `10.0.1.10` rejected with `DuplicateAddressError`. |
| AT-04  | Duplicate MAC address            | Creating interface with an existing MAC rejected with `DuplicateMacError`. |
| AT-05  | Missing routing entry            | Destination with no matching route and no default: `DROPPED / NO_ROUTE`. |
| AT-06  | Longest prefix match             | Routes `10.0.0.0/8` and `10.1.2.0/24`: dst `10.1.2.5` uses /24. |
| AT-07  | TTL expiration                   | TTL=1 crossing a router: `DROPPED / TTL_EXPIRED` at that router. |
| AT-08  | Offline network device           | Middle router OFFLINE: `DROPPED / DEVICE_OFFLINE`. |
| AT-09  | Disconnected network link        | Link down on path: `DROPPED / LINK_DOWN`. |
| AT-10  | Invalid switch port              | Port 99 on 24-port switch: `InvalidPortError`. |
| AT-11  | Database persistence             | Save lab, reopen DB, topology and routes are equal. |
| AT-12  | TUI keyboard navigation          | Pilot test navigates all 10 screens via bindings without mouse. |

## 9. Release Plan

| Phase | Name                     | Scope                                                         | Exit criteria |
| ----- | ------------------------ | ------------------------------------------------------------- | ------------- |
| 1     | Core Network Engine      | Domain models, validation, routing, switching, ARP, simulation engine. | AT-01..AT-10 pass headless. |
| 2     | Persistence              | SQLite schema, repositories, unit of work, migrations, seed lab. | AT-11 passes. |
| 3     | Application Services     | Use cases, event bus, monitoring aggregation.                | Service tests pass; no TUI imports in services. |
| 4     | TUI                      | 10 screens, widgets, theme, keybindings.                     | AT-12 passes; manual UX checklist. |
| 5     | Hardening & Docs         | Coverage targets, performance budgets, user guide.           | NFR-01..NFR-07 verified. |

## 10. Success Metrics

- All 12 acceptance scenarios automated and green.
- Zero known protocol-correctness defects in the issue list.
- New feature (e.g., a new screen) can be added by an agent touching
  only its own layer plus one service, without editing the domain.

## 11. Assumptions & Constraints

- Single local user, single process.
- Python ≥ 3.12, Textual as the only UI dependency.
- Runtime dependencies are minimised: `textual` (UI). Standard library
  `sqlite3`, `ipaddress`, `dataclasses`, `enum`, `logging` are preferred
  over third-party packages.
- Dev dependencies: `pytest`, `pytest-asyncio`, `ruff`, `ty`.

## 12. Open Questions

| ID    | Question | Owner | Status |
| ----- | -------- | ----- | ------ |
| OQ-01 | Is the original UTS source available to import into `legacy/` for reference? | Human | Open |
| OQ-02 | Should VLANs be added in a later phase (would affect Switch model)? | Human | Open |
| OQ-03 | Required report/export format for lecturers (CSV vs JSON vs both)? | Human | Open |
