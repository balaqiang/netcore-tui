# NETCORE — TASK BOARD

Owned by ORCHESTRATOR. Agents update only the `Status` and `Notes` of
tasks assigned to them; the ORCHESTRATOR adds, splits and re-prioritises.

## Conventions

- **ID:** `T-<phase><nn>` (e.g., `T-101` = phase 1, task 01).
- **Status:** `TODO` · `READY` (deps done) · `IN_PROGRESS` · `REVIEW` ·
  `BLOCKED` · `DONE` (verified, reviewed, state updated).
- **Owner:** one agent role. Reviewer is always `CODE_REVIEWER`.
- **Size:** S (< 1 h), M (1–3 h), L (> 3 h — should be split).
- A task moves to `DONE` only when every acceptance criterion is checked
  and the required commands were actually run (CLAUDE.md §13).

Status legend for criteria: `[ ]` open · `[x]` verified.

---

> 2026-11-27: phases 0–4 implemented in one session (roles played
> sequentially). Criteria marked `[x]` were verified by running the
> gates; tasks stay at `REVIEW` until an independent CODE_REVIEWER pass
> (T-111, T-503). Spec deviations: DEC-016..DEC-021 (PROPOSED).

## Phase 0 — Project Scaffolding

### T-001 Create project skeleton and tooling
- Owner: ARCHITECT · Size: S · Status: REVIEW · Deps: —
- Files: `pyproject.toml`, `README.md`, `src/netcore/__init__.py`,
  `src/netcore/__main__.py`, `tests/conftest.py`, `.gitignore`
- Acceptance:
  - [x] `pyproject.toml` matches ARCHITECTURE.md §6 (textual; dev: pytest, pytest-asyncio, ruff, ty).
  - [x] Directory tree from ARCHITECTURE.md §2 exists with `__init__.py` files.
  - [x] `python -m netcore --version` prints version.
  - [x] All four quality gates run (pytest may report "no tests").
- Skill: `.ai/skills/quality-gates.md`

### T-002 Architecture import-rule tests
- Owner: QA_ENGINEER · Size: S · Status: REVIEW · Deps: T-001
- Files: `tests/architecture/test_layer_imports.py`
- Acceptance:
  - [x] Test fails if `netcore.domain` imports textual/sqlite3/application/infrastructure/tui.
  - [x] Test fails if `netcore.tui` imports sqlite3/infrastructure.
  - [x] Test fails if `src/` imports `socket`, `subprocess`, or calls `os.system`.
- Skill: `.ai/skills/architecture-guard.md`

---

## Phase 1 — Core Network Engine (domain only)

### T-101 Domain enums and error hierarchy
- Owner: NETWORK_ENGINEER · Size: S · Status: REVIEW · Deps: T-001
- Files: `domain/enums.py`, `domain/errors.py`
- Acceptance:
  - [x] All enums from UML.md §4 exist.
  - [x] Error classes and codes from NETWORK_SPEC §12 / UML §5 exist; each carries `code` and `message`.

### T-102 Addressing value objects and validators
- Owner: NETWORK_ENGINEER · Size: M · Status: REVIEW · Deps: T-101
- Files: `domain/addressing.py`, `tests/unit/domain/test_addressing.py`
- Acceptance:
  - [x] IPv4 parsing rules of NETWORK_SPEC §2.1 incl. leading-zero rejection.
  - [x] `MacAddress` normalisation (`:`, `-`, `.`), rejects broadcast/multicast.
  - [x] Deterministic MAC generator (seeded, `02:` prefix).
  - [x] AT-02 test passes.

### T-103 LoggerMixin, NetworkInterface, Subnet, Link
- Owner: NETWORK_ENGINEER · Size: M · Status: REVIEW · Deps: T-102
- Files: `domain/logging_mixin.py`, `domain/interface.py`, `domain/subnet.py`, `domain/link.py`
- Acceptance:
  - [x] Signatures match UML §2.
  - [x] Subnet reserved-address rules incl. /31, /32.
  - [x] Link rejects same-device endpoints.

### T-104 NetworkDevice, Router, Switch, Server
- Owner: NETWORK_ENGINEER · Size: L→split if needed · Status: REVIEW · Deps: T-103
- Files: `domain/devices/*.py`
- Acceptance:
  - [x] Abstract `NetworkDevice` with `receive()` abstract.
  - [x] Interface count limits (NETWORK_SPEC §3).
  - [x] Switch ports 1..N, `InvalidPortError` (AT-10).
  - [x] Private attributes not exposed; read-only properties used.

### T-105 RoutingTable with longest prefix match
- Owner: NETWORK_ENGINEER · Size: M · Status: REVIEW · Deps: T-104
- Files: `domain/devices/router.py`, `tests/unit/domain/test_routing_table.py`
- Acceptance:
  - [x] Example table in NETWORK_SPEC §6.2 returns all 5 expected matches (AT-06).
  - [x] Connected routes sync with interface addresses.
  - [x] `InvalidNextHopError`, `DuplicateRouteError`.

### T-106 MacTable and ArpTable
- Owner: NETWORK_ENGINEER · Size: M · Status: REVIEW · Deps: T-104
- Files: `domain/devices/switch.py`, `domain/arp.py`
- Acceptance:
  - [x] Expiry uses injected `now`.
  - [x] Static ARP entries never expire.

### T-107 NetworkTopology aggregate
- Owner: NETWORK_ENGINEER · Size: L · Status: REVIEW · Deps: T-105, T-106
- Files: `domain/topology.py`, `tests/unit/domain/test_topology.py`
- Acceptance:
  - [x] Duplicate hostname/IP/MAC rejected (AT-03, AT-04).
  - [x] Overlapping subnets rejected.
  - [x] `connect` enforces one link per interface.
  - [x] `is_operational` per NETWORK_SPEC §3.1.
  - [x] `l2_segment` stops at routers.
  - [x] `remove_device` returns RemovalReport and cleans links/routes.

### T-108 Packet, Frame, NetworkEvent, TrafficEvent
- Owner: NETWORK_ENGINEER · Size: S · Status: REVIEW · Deps: T-101
- Files: `domain/packet.py`, `domain/events.py`
- Acceptance:
  - [x] Frozen dataclasses; `Packet.with_ttl` returns new instance.
  - [x] TTL range 1..255, size 64..9000 validated.

### T-109 ForwardingEngine (single packet + traceroute)
- Owner: NETWORK_ENGINEER · Size: L · Status: REVIEW · Deps: T-107, T-108
- Files: `domain/simulation/*.py`, `tests/fixtures/two_router_lab.py`,
  `tests/unit/domain/test_forwarding_engine.py`
- Acceptance:
  - [x] AT-01 delivered, TTL 64→62, path `srv-a, sw-a, r1, r2, sw-b, srv-b`.
  - [x] AT-05 NO_ROUTE, AT-07 TTL_EXPIRED, AT-08 DEVICE_OFFLINE, AT-09 LINK_DOWN.
  - [x] Switch never reads dst IP (assert via test double).
  - [x] ARP hops visible, do not decrement TTL.
  - [x] Hop limit guard; deterministic with seed.
  - [x] Single packet ≤ 50 hops < 50 ms (NFR-01).
- Skill: `.ai/skills/network-scenario-test.md`

### T-110 TrafficGenerator and utilization
- Owner: NETWORK_ENGINEER · Size: M · Status: REVIEW · Deps: T-109
- Files: `domain/simulation/traffic.py`
- Acceptance:
  - [x] Formula NETWORK_SPEC §10.2; capacity never mutated.
  - [x] CONGESTION drops when load > capacity.

### T-111 Phase 1 review
- Owner: CODE_REVIEWER · Size: M · Status: TODO · Deps: T-101..T-110
- Acceptance:
  - [ ] Review report per `.ai/agents/code-reviewer.md`, no blocking findings open.
  - [x] Domain coverage ≥ 90 %.

---

## Phase 2 — Persistence

### T-201 Schema migration 0001 and Migrator
- Owner: DATABASE_ENGINEER · Size: M · Status: REVIEW · Deps: T-107
- Files: `infrastructure/persistence/migrations/0001_initial.sql`, `migrator.py`, `connection.py`
- Acceptance:
  - [x] Tables per UML §10 with FK, UNIQUE, CHECK constraints.
  - [x] Pragmas: foreign_keys, WAL, busy_timeout.
  - [x] Migrator idempotent; records `schema_migrations`.

### T-202 Ports and SqliteUnitOfWork
- Owner: DATABASE_ENGINEER (ports reviewed by ARCHITECT) · Size: M · Status: REVIEW · Deps: T-201
- Files: `application/ports.py`, `infrastructure/persistence/unit_of_work.py`
- Acceptance:
  - [x] Commit on success, rollback + re-raise on exception.

### T-203 Topology, Event, Simulation, Settings repositories + mappers
- Owner: DATABASE_ENGINEER · Size: L · Status: REVIEW · Deps: T-202
- Acceptance:
  - [x] Round-trip test: build reference lab → save → load → equal (AT-11).
  - [x] Parameterised SQL only.
  - [x] Event pruning keeps N most recent.

### T-204 Seed labs (two-router, spine-leaf)
- Owner: DATABASE_ENGINEER + NETWORK_ENGINEER · Size: M · Status: REVIEW · Deps: T-203
- Acceptance:
  - [x] Spine-leaf: 2 spines, 4 leaves, 8 servers, valid addressing; packet between any two servers is DELIVERED.

---

## Phase 3 — Application Services

### T-301 DTOs, ApplicationError, EventBus
- Owner: ARCHITECT · Size: M · Status: REVIEW · Deps: T-202
### T-302 Device, IPAM, Routing, Switch, Topology services
- Owner: NETWORK_ENGINEER · Size: L · Status: REVIEW · Deps: T-301, T-203
### T-303 Simulation, Monitoring, EventLog, Settings services
- Owner: NETWORK_ENGINEER · Size: L · Status: REVIEW · Deps: T-302
### T-304 bootstrap composition root + CLI args
- Owner: ARCHITECT · Size: S · Status: REVIEW · Deps: T-303

Acceptance for T-302/T-303:
  - [x] Each service method has a unit test with fake UoW and one integration test with in-memory SQLite.
  - [x] No `textual` or `sqlite3` import in `application/`.
  - [x] Domain errors mapped to ApplicationError with same code.

---

## Phase 4 — TUI

### T-401 App shell, theme, sidebar, global bindings, too-small screen
- Owner: TUI_ENGINEER · Size: M · Status: REVIEW · Deps: T-304
### T-402 Reusable widgets (UI_SPEC §6)
- Owner: TUI_ENGINEER · Size: L · Status: REVIEW · Deps: T-401
### T-403 Dashboard, Devices, IPAM screens
- Owner: TUI_ENGINEER · Size: L · Status: REVIEW · Deps: T-402
### T-404 Routing, Switch Ports, Topology screens
- Owner: TUI_ENGINEER · Size: L · Status: REVIEW · Deps: T-402
### T-405 Packet Lab, Traffic, Event Logs, Settings screens
- Owner: TUI_ENGINEER · Size: L · Status: REVIEW · Deps: T-402
### T-406 TUI Pilot tests incl. AT-12
- Owner: QA_ENGINEER · Size: M · Status: REVIEW · Deps: T-403..T-405

Acceptance for Phase 4:
  - [x] All screens reachable via `1`–`0`; AT-12 passes.
  - [x] Long operations in workers; no UI freeze.
  - [x] All UI_SPEC §9 error/empty states implemented.

---

## Phase 5 — Hardening & Documentation

### T-501 Coverage & performance verification (NFR-01, NFR-02, NFR-06)
- Owner: QA_ENGINEER · Status: REVIEW
- Notes: domain 95 %, overall 91 %; NFR-01/02 covered by timed tests.
### T-502 User guide in README (install, run, keymap, sample lab walkthrough)
- Owner: TUI_ENGINEER · Status: REVIEW
### T-503 Final review and release checklist
- Owner: CODE_REVIEWER · Status: TODO

---

## Parallelisation Map

```
T-001 ─┬─ T-002
       └─ T-101 ─┬─ T-102 ─ T-103 ─ T-104 ─┬─ T-105 ─┐
                 └─ T-108                  └─ T-106 ─┴─ T-107 ─ T-109 ─ T-110 ─ T-111
T-107 ─ T-201 ─ T-202 ─┬─ T-203 ─ T-204
                       └─ T-301 ─ T-302 ─ T-303 ─ T-304 ─ T-401 ─ T-402 ─┬─ T-403 ┐
                                                                         ├─ T-404 ┼─ T-406
                                                                         └─ T-405 ┘
```

Safe parallel pairs (no shared files): T-002 ‖ T-101; T-105 ‖ T-106;
T-108 ‖ T-102..T-104; T-203 ‖ T-301; T-403 ‖ T-404 ‖ T-405.
