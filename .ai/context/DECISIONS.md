# NETCORE — ARCHITECTURE DECISION LOG

Lightweight ADR log. Each decision is immutable once `ACCEPTED`; to
change it, add a new decision that `SUPERSEDES` the old one.

Status values: `PROPOSED` → `ACCEPTED` | `REJECTED`; later `SUPERSEDED`.
Only a human may move a decision to `ACCEPTED` when it touches a gate in
`CLAUDE.md §15`. Agents may record `PROPOSED` entries.

Template:

```
## DEC-NNN: <title>
- Status: PROPOSED | ACCEPTED | REJECTED | SUPERSEDED by DEC-XXX
- Date: YYYY-MM-DD
- Deciders: <human / agent roles>
- Context: why a decision is needed
- Decision: what was chosen
- Alternatives: options considered and why rejected
- Consequences: positive / negative / follow-up tasks
```

---

## DEC-001: Use Python 3.12+ and Textual

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: The product is a terminal application for education; it must
  be cross-platform and easy to install.
- Decision: Python ≥ 3.12; Textual for the presentation layer.
- Alternatives: curses (too low-level), urwid (smaller ecosystem),
  prompt_toolkit (not screen-oriented), Rich only (no interactivity).
- Consequences: Async-aware UI, CSS-like styling, built-in Pilot test
  harness. Textual must stay confined to `netcore.tui`.

## DEC-002: Use SQLite for local persistence

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: Labs, configuration and event history must survive restarts
  with zero setup.
- Decision: Single SQLite file accessed via stdlib `sqlite3`.
- Alternatives: JSON files (no transactions/queries), PostgreSQL (needs
  a server).
- Consequences: Transactions and foreign keys available; one writer at
  a time — workers use separate connections.

## DEC-003: Preserve the original OOP foundation

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: Project originates from a UTS (mid-term) OOP assignment with
  classes `NetworkDevice`, `Router`, `Switch`, `Server`, `Packet`,
  `Link`, `NetworkTopology`, `LoggerMixin`.
- Decision: Keep these class names, the inheritance
  `NetworkDevice → Router/Switch/Server`, and `LoggerMixin` as a mixin.
  Fix protocol defects inside them rather than replacing them.
- Alternatives: Rewrite with a pure functional engine (loses
  educational OOP value).
- Consequences: New models (`RoutingEntry`, `SwitchPort`,
  `NetworkInterface`, `Subnet`, `TrafficEvent`, `SimulationResult`,
  `NetworkEvent`) are added around the original classes.

## DEC-004: Default to simulation-only mode

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: Safety and scope.
- Decision: No sockets, raw packets, subprocess or host network access
  in `src/`. Enforced by an architecture test.
- Consequences: Any real integration needs a new spec and human
  approval (CLAUDE.md §12, §15).

## DEC-005: Layered Modular Monolith with ports

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human, ARCHITECT
- Context: Several agents work in parallel; boundaries must be explicit.
- Decision: Layers `tui → application → domain`; `infrastructure`
  implements `typing.Protocol` ports declared in `application.ports`.
  Composition root in `netcore/bootstrap.py`. `src/` layout.
- Alternatives: Flat package (coupling), microservices (overkill),
  full hexagonal with separate packages (too heavy).
- Consequences: Import rules tested in `tests/architecture/`.

## DEC-006: No ORM — repositories with hand-written SQL

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: ARCHITECT, DATABASE_ENGINEER
- Context: Schema is small; dependency count should stay low;
  learners benefit from readable SQL.
- Decision: stdlib `sqlite3`, parameterised queries only, mappers in
  `infrastructure/persistence/mappers.py`, forward-only `.sql`
  migrations.
- Alternatives: SQLAlchemy (heavy dependency), Peewee.
- Consequences: Mapper code must be unit-tested; no string-formatted SQL.

## DEC-007: Use `ty` for static type checking (replaces mypy)

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human (project description explicitly specifies ty)
- Context: The earlier `CLAUDE.md` listed `python -m mypy src/netcore`,
  while the human project description specifies **ty** for static
  type checking, Ruff for lint/format and pytest for tests. Explicit
  human requirements take priority (CLAUDE.md §03).
- Decision: Quality gate is `ty check src/netcore`. mypy is not used.
- Alternatives: mypy (slower, conflicting configuration), pyright.
- Consequences: `pyproject.toml` contains `[tool.ty]`; ty is still
  evolving, so a rule that misbehaves may be suppressed with a targeted
  `# ty: ignore[<rule>]` plus a justification comment — never blanket
  ignores.

## DEC-008: NetworkTopology is the aggregate root

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: ARCHITECT, NETWORK_ENGINEER
- Context: Uniqueness of IP/MAC/hostname and link exclusivity span
  multiple devices.
- Decision: All cross-device mutations go through `NetworkTopology`
  methods. Repositories load/save the whole topology (labs are small:
  target ≤ 200 devices).
- Alternatives: Per-device repositories with DB constraints only
  (invariants leak into infrastructure).
- Consequences: DB UNIQUE constraints still exist as a second safety
  net. Revisit if labs exceed NFR-02 size.

## DEC-009: Integer longest prefix match

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: NETWORK_ENGINEER
- Context: Original UTS code used string prefix matching (defect).
- Decision: Use `ipaddress` membership and `prefixlen`; tie-break by AD,
  metric, insertion order (NETWORK_SPEC §6.2). Linear scan is
  acceptable for tables ≤ 1 000 entries.
- Consequences: Radix trie may be introduced later behind the same
  `RoutingTable.longest_prefix_match` interface.

## DEC-010: Explicit simulated ARP

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: NETWORK_ENGINEER, Human (CLAUDE.md §08 requires explicit ARP)
- Context: Switches forward on MAC, so L3→L2 resolution must exist.
- Decision: Per-device `ArpTable`, broadcast request flooded within the
  L2 segment, reply from owner, cache with simulation-time expiry,
  visible as `ARP` hop records that do not consume TTL (NETWORK_SPEC §7).
- Alternatives: Global IP→MAC oracle (hides learning, rejected).
- Consequences: Traces are longer but educational.

## DEC-011: Capacity vs utilization are separate fields

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: NETWORK_ENGINEER
- Context: Original code had no utilization and risked mixing
  bandwidth with usage.
- Decision: `Link.capacity_mbps` is configuration; utilization is
  computed from active simulated flows (NETWORK_SPEC §10) and never
  persisted as configuration. UI labels all traffic numbers "simulated".
- Consequences: No real measurements are ever fabricated.

## DEC-012: Deterministic simulation with injected clock and RNG

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: ARCHITECT, QA_ENGINEER
- Decision: Domain receives `now: datetime` and `random.Random(seed)`;
  application provides them via a `Clock` port and settings seed.
- Consequences: Reproducible tests and replays.

## DEC-013: Synchronous in-process EventBus

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: ARCHITECT
- Context: Dashboard, traffic monitor and event log need live updates.
- Decision: Simple synchronous pub/sub in `application/event_bus.py`.
  Events are persisted first, then published after commit. TUI bridge
  marshals to the Textual thread.
- Alternatives: asyncio queues in the domain (couples domain to
  asyncio), polling only (laggy).
- Consequences: Handlers must be fast and must not raise; handler
  errors are logged and do not break the publisher.

## DEC-014: Testing stack

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: QA_ENGINEER, Human
- Decision: pytest + pytest-asyncio (`asyncio_mode = "auto"`) and
  Textual `run_test()`/Pilot for TUI. In-memory SQLite
  (`:memory:`) for integration tests. No snapshot-testing dependency
  without approval.
- Consequences: TUI tests run headless in CI.

## DEC-015: Hierarchical multi-agent orchestration with skills

- Status: ACCEPTED
- Date: 2026-11-27
- Deciders: Human
- Context: Development uses Spec-Driven Development, Hierarchical
  Multi-Agent Orchestration and Skill-Based Execution.
- Decision: ORCHESTRATOR plans and delegates to six specialist roles
  (`.ai/agents/*.md`); reusable procedures live in `.ai/skills/*.md`;
  shared state lives in `.ai/context/`. File ownership per role is
  defined in `CLAUDE.md §05`.
- Consequences: Every task must pass DISCOVER → … → DOCUMENT and the
  agent output contract.

---

## Pending / Proposed

Recorded during the initial implementation (2026-11-27). None touches a
CLAUDE.md §15 gate (no breaking public interface, no new runtime
dependency, no destructive migration), but each deviates from or extends
the baseline docs, so they await human confirmation.

## DEC-016: Topology assigns positive ids (no temporary negative ids)

- Status: PROPOSED
- Date: 2026-11-27
- Deciders: ARCHITECT, DATABASE_ENGINEER
- Context: ARCHITECTURE.md §5 says new entities get temporary negative
  ids. Services return the created DTO (with its id) inside the same
  unit of work, so a negative id would leak to the TUI.
- Decision: `NetworkTopology.next_device_id/next_link_id/next_subnet_id`
  return `max(existing) + 1`; repositories persist those ids verbatim
  (upsert + prune). Routing entries keep their own per-router ids;
  connected routes use derived negative ids and are never persisted.
- Consequences: ids are stable across save/load; ARCHITECTURE.md §5
  "Identifiers" row should be updated if accepted.

## DEC-017: Additional error codes NET016–NET022 and APP0xx

- Status: PROPOSED
- Date: 2026-11-27
- Deciders: NETWORK_ENGINEER
- Context: UML §5 names `InterfaceNotFoundError`/`LinkNotFoundError`
  without codes; NETWORK_SPEC §2.3 names `DuplicateInterfaceError`;
  subnet/route not-found, subnet-in-use and generic range errors are
  needed.
- Decision: NET016 InterfaceNotFound, NET017 LinkNotFound, NET018
  SubnetNotFound, NET019 RouteNotFound, NET020 SubnetInUse, NET021
  DuplicateInterface, NET022 InvalidValue. Application-only errors use
  `APP001`–`APP012` (e.g. unknown lab, export file exists).
- Consequences: NETWORK_SPEC §12 catalogue should list them.

## DEC-018: Schema 0001 additions beyond UML §10

- Status: PROPOSED
- Date: 2026-11-27
- Deciders: DATABASE_ENGINEER
- Decision: additive columns needed for lossless round-trips:
  `interfaces.position`, `routes.route_no/insertion_index`,
  `arp_entries.learned_at`, `mac_entries.learned_at`,
  `simulation_runs.path_json`, `hop_records.device_name/device_type`,
  `traffic_counters.drop_reasons_json`. Only static/default routes are
  stored; connected routes are re-derived on load.
- Consequences: UML §10 ER diagram should be updated if accepted.

## DEC-019: Port additions — TrafficRepository, TopologyRepository.clear, EventExporter

- Status: PROPOSED
- Date: 2026-11-27
- Deciders: ARCHITECT
- Decision: `UnitOfWork.traffic` (simulated counters),
  `TopologyRepository.clear()` (lab reset / sample-lab load) and an
  `EventExporter` port (CSV/JSON file writing stays in infrastructure).
  Repository members on the `UnitOfWork` protocol are read-only
  properties (required for structural typing under ty).
- Consequences: UML §6 should show these members.

## DEC-020: DEVICE_OFFLINE detected at the previous hop's egress

- Status: PROPOSED
- Date: 2026-11-27
- Deciders: NETWORK_ENGINEER
- Context: NETWORK_SPEC §3.1 makes `peer_device.status == ONLINE` part of
  the egress operational check (step 6), while AT-08 expects
  `DEVICE_OFFLINE` (not `LINK_DOWN`) when a middle router is offline.
- Decision: the egress check reports `DEVICE_OFFLINE` when the peer
  device is offline/maintenance (`LINK_DOWN` for link/peer-interface
  problems, `INTERFACE_DOWN`/`PORT_DOWN` for local admin-down). ARP
  resolution reports the first such failure on the static L2 path to the
  owner instead of a bare `ARP_FAILED`. The drop hop is recorded at the
  device that could not transmit and its reason names the offline device.

## DEC-021: Topology canvas = layered node rows + link list

- Status: PROPOSED
- Date: 2026-11-27
- Deciders: TUI_ENGINEER
- Context: UI_SPEC §5.6 asks for links drawn with box-drawing characters
  between layered nodes; free-form edge routing in a character grid is
  costly and hard to read for > 10 links.
- Decision: routers / switches / servers render as rows of node cells;
  links render as a list underneath (`━━━━` up, `┄┄┄┄` down in `$error`,
  last path in `$accent`), plus a link table for selection. `t` switches
  to an adjacency list (automatic above 40 devices).
- Also: `ctrl+enter` is not delivered by many terminals, so Packet Lab
  also sends on `enter` and `ctrl+t`; Settings lab actions use
  `ctrl+l` / `ctrl+r`.
