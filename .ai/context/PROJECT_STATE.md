# NETCORE PROJECT STATE

Single source of truth for "where are we now". Updated by the
ORCHESTRATOR **only after verification** (tests actually run, review
passed). Never record a result that was not observed.

Last updated: 2026-11-27 — by ORCHESTRATOR

## Current Phase

Phases 0–4 implemented and gate-verified; awaiting independent
CODE_REVIEWER pass (T-111, T-503) and human review of DEC-016..DEC-021.
Phase 5 partially done (README guide, NFR-01/02/06 measured).

## Current Architecture

Layered Modular Monolith — `tui → application → domain`,
infrastructure implements application ports (see docs/ARCHITECTURE.md,
DEC-005).

## Specification Status

| Document                     | Status   | Version |
| ---------------------------- | -------- | ------- |
| docs/PRD.md                  | Baseline | 1.0     |
| docs/ARCHITECTURE.md         | Baseline | 1.0     |
| docs/NETWORK_SPEC.md         | Baseline | 1.0     |
| docs/UI_SPEC.md              | Baseline | 1.0     |
| docs/UML.md                  | Baseline | 1.0     |
| .ai/agents/*.md (7 roles)    | Baseline | 1.0     |
| .ai/skills/*.md (7 skills)   | Baseline | 1.0     |

## Completed (implemented + quality gates green; review pending)

- Phase 0: `pyproject.toml`, src layout, `.gitignore`, `python -m netcore
  --version`, architecture import-rule tests (T-001, T-002).
- Phase 1: domain enums/errors, addressing, interface/subnet/link,
  Router/Switch/Server, RoutingTable (integer LPM), MacTable/ArpTable,
  NetworkTopology aggregate, Packet/Frame/events, ForwardingEngine
  (single + traceroute, explicit ARP, flood-branch following, hop guard),
  TrafficGenerator (T-101..T-110). All 5 UTS defects covered by tests.
- Phase 2: migration 0001, Migrator, connection factory (WAL/FK/busy),
  SqliteUnitOfWork, topology/event/simulation/traffic/settings
  repositories, two-router + spine-leaf seed labs (T-201..T-204).
- Phase 3: DTOs, ApplicationError, EventBus, 9 services, bootstrap +
  CLI (`--db`, `--seed`, `--version`) (T-301..T-304).
- Phase 4: app shell, dark theme, sidebar, header, too-small guard,
  10 screens, widgets (StatCard, EventFeed, UtilizationPanel, FilterBar,
  FormField, PortGrid, TopologyCanvas, HopTraceTable), 11 modals,
  EventBus→TUI bridge, Pilot tests incl. AT-12 (T-401..T-406).
- Phase 5 (partial): README user guide (T-502); coverage and
  performance measured (T-501).

## In Progress

- None. Independent review not yet performed (the implementing session
  must not self-review — CLAUDE.md §04).

## Planned (by phase)

1. Core Network Engine — NetworkDevice abstraction, Router, Switch,
   Server, Packet, Link, NetworkTopology, ARP, ForwardingEngine,
   traffic model.
2. Persistence — SQLite schema, migrations, repositories, UoW, seed labs.
3. Application services — use cases, DTOs, EventBus.
4. TUI — 10 screens, widgets, dark theme.
5. Hardening — coverage, performance, user guide.

See `.ai/context/TASKS.md` for task-level detail.

## Known Issues in Original UTS Code

These defects must be fixed by the new implementation; each has a
covering spec rule and acceptance test.

| # | Defect | Fix spec | Test |
| - | ------ | -------- | ---- |
| 1 | Routing uses string prefix matching. | NETWORK_SPEC §6.2, DEC-009 | AT-06 |
| 2 | TTL expiration is not handled correctly. | NETWORK_SPEC §6.3 step 3 | AT-07 |
| 3 | Switch forwarding matches destination IP. | NETWORK_SPEC §8.3 | T-109 |
| 4 | Link connectivity is not enforced. | NETWORK_SPEC §3.1, §4 | AT-09 |
| 5 | Bandwidth utilization is not implemented. | NETWORK_SPEC §10, DEC-011 | T-110 |

Note: the original UTS source is not in this repository (open question
OQ-01 in PRD). Class names and responsibilities are preserved per DEC-003.

## Active Decisions

- DEC-001: Use Python and Textual.
- DEC-002: Use SQLite for local persistence.
- DEC-003: Preserve the original OOP foundation.
- DEC-004: Default to simulation-only mode.
- DEC-005: Layered Modular Monolith with ports.
- DEC-006: No ORM — repositories with hand-written SQL.
- DEC-007: Use ty for static type checking (replaces mypy).
- DEC-008: NetworkTopology is the aggregate root.
- DEC-009: Integer longest prefix match.
- DEC-010: Explicit simulated ARP.
- DEC-011: Capacity vs utilization are separate fields.
- DEC-012: Deterministic simulation (injected clock/RNG).
- DEC-013: Synchronous in-process EventBus.
- DEC-014: Testing stack (pytest, pytest-asyncio, Pilot).
- DEC-015: Hierarchical multi-agent orchestration with skills.

## Open Questions (need human input)

- OQ-01: Import original UTS source into `legacy/` for reference?
- OQ-02: VLAN support in a later phase?
- OQ-03: Lecturer export format (CSV / JSON / both)?

## Blockers

- None.

## Next Task

T-111 / T-503 — independent CODE_REVIEWER review of phases 1–4, then
human decision on DEC-016..DEC-021 and doc updates that follow.

## Verification Status (2026-11-27, Python 3.14.10, Textual 8.2.8)

| Check                         | Status        |
| ----------------------------- | ------------- |
| Implementation                | Phases 0–4 complete |
| `python -m pytest`            | exit 0 — 197 passed (~35 s); one transient TUI failure seen once, not reproduced in later runs (see Known Issues) |
| `python -m ruff check .`      | exit 0 — All checks passed |
| `python -m ruff format --check .` | exit 0 — 142 files already formatted |
| `ty check src/netcore`        | exit 0 — All checks passed |
| Acceptance tests AT-01..AT-12 | 12 / 12 automated and passing |
| Coverage (NFR-06)             | domain 95 %, overall 91 % (coverage.py) |
| NFR-01 single packet ≤ 50 hops | < 50 ms (test) |
| NFR-02 200 devices / 400 links load | < 1 s (test) |

## Known Issues

- `tests/tui/test_tui.py::test_device_add_flow_end_to_end` failed once
  with `textual.app.ScreenStackError` during a full-suite run; it passed
  in every subsequent isolated and full run. Treat as possibly flaky
  until reviewed.
- `coverage` was installed into the local venv for measurement only; it
  is not declared in `pyproject.toml`.

## Change History

| Date       | Agent        | Change |
| ---------- | ------------ | ------ |
| 2026-11-27 | ORCHESTRATOR | Initial specs, agent instructions, skills, decisions DEC-005..DEC-015. |
| 2026-11-27 | ORCHESTRATOR (all roles, sequential) | Implemented phases 0–4; gates green; DEC-016..DEC-021 proposed. |
