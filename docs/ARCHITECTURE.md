# NetCore TUI — Architecture

| Field          | Value                                      |
| -------------- | ------------------------------------------ |
| Owner          | ARCHITECT                                  |
| Status         | Approved baseline v1.0                     |
| Last updated   | 2026-11-27                                 |
| Related        | PRD.md, NETWORK_SPEC.md, UML.md, DECISIONS.md |

---

## 1. Architectural Style

NetCore TUI is a **Layered Modular Monolith**: one Python package
(`netcore`), one process, separated into strict layers and, inside each
layer, cohesive feature modules.

```
┌──────────────────────────────────────────────────────────────┐
│  Presentation (TUI)          netcore.tui                      │
│  Textual App, Screens, Widgets, Bindings, CSS                 │
└───────────────▲──────────────────────────────────────────────┘
                │ calls (DTOs in, DTOs out)
┌───────────────┴──────────────────────────────────────────────┐
│  Application Services        netcore.application              │
│  Use cases, DTOs, EventBus, UnitOfWork protocol, ports        │
└───────────────▲──────────────────────────────────────────────┘
                │ uses
┌───────────────┴──────────────────────────────────────────────┐
│  Domain                      netcore.domain                   │
│  Entities, value objects, simulation engine, domain errors    │
└──────────────────────────────────────────────────────────────┘
                ▲ implements ports defined above
┌───────────────┴──────────────────────────────────────────────┐
│  Infrastructure              netcore.infrastructure           │
│  SQLite repositories, migrations, UoW, clock, config, logging │
└──────────────────────────────────────────────────────────────┘
```

### 1.1 Dependency Rule

```
tui  ──►  application  ──►  domain
infrastructure  ──►  application (ports)  &  domain
bootstrap (composition root)  ──►  everything
```

- `domain` imports **only** the Python standard library.
- `application` imports `domain` and the standard library.
- `infrastructure` imports `application` (protocols) and `domain`.
- `tui` imports `application` (services + DTOs) only. It may import
  domain **enums/value types re-exported by application DTOs**, never
  entities or the simulation engine.
- `bootstrap.py` is the single composition root that wires concrete
  infrastructure into services and hands services to the TUI.

Forbidden (enforced by tests in `tests/architecture/`):

| From             | Must not import                          |
| ---------------- | ---------------------------------------- |
| `netcore.domain` | `textual`, `sqlite3`, `netcore.application`, `netcore.infrastructure`, `netcore.tui` |
| `netcore.application` | `textual`, `sqlite3`, `netcore.infrastructure`, `netcore.tui` |
| `netcore.tui`    | `sqlite3`, `netcore.infrastructure`, `netcore.domain.simulation` |
| any module       | circular imports                          |

## 2. Repository Layout

```
pbo_dcnm/
├── CLAUDE.md                      # AI orchestration entry point
├── pyproject.toml                 # deps, ruff, ty, pytest config
├── README.md
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── NETWORK_SPEC.md
│   ├── UI_SPEC.md
│   └── UML.md
├── .ai/
│   ├── agents/                    # role instructions
│   ├── context/                   # PROJECT_STATE, TASKS, DECISIONS
│   └── skills/                    # reusable execution recipes
├── src/netcore/
│   ├── __init__.py
│   ├── __main__.py                # `python -m netcore`
│   ├── bootstrap.py               # composition root
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── errors.py              # domain exception hierarchy
│   │   ├── enums.py               # DeviceType, DeviceStatus, Protocol, DropReason...
│   │   ├── logging_mixin.py       # LoggerMixin
│   │   ├── addressing.py          # IPv4Address/MacAddress value objects, validators
│   │   ├── devices/
│   │   │   ├── base.py            # NetworkDevice (abstract)
│   │   │   ├── router.py          # Router, RoutingTable, RoutingEntry
│   │   │   ├── switch.py          # Switch, SwitchPort, MacTable
│   │   │   └── server.py          # Server
│   │   ├── interface.py           # NetworkInterface
│   │   ├── link.py                # Link
│   │   ├── subnet.py              # Subnet
│   │   ├── packet.py              # Packet, Frame
│   │   ├── arp.py                 # ArpTable, ArpResolver
│   │   ├── topology.py            # NetworkTopology (aggregate root)
│   │   ├── events.py              # NetworkEvent, TrafficEvent
│   │   └── simulation/
│   │       ├── engine.py          # ForwardingEngine
│   │       ├── result.py          # SimulationResult, HopRecord
│   │       └── traffic.py         # TrafficGenerator, utilization calc
│   ├── application/
│   │   ├── __init__.py
│   │   ├── dto.py                 # frozen dataclasses for TUI
│   │   ├── ports.py               # Repository & UnitOfWork Protocols, Clock
│   │   ├── event_bus.py           # in-process pub/sub
│   │   ├── errors.py              # ApplicationError wrapping domain errors
│   │   └── services/
│   │       ├── device_service.py
│   │       ├── ipam_service.py
│   │       ├── routing_service.py
│   │       ├── switch_service.py
│   │       ├── topology_service.py
│   │       ├── simulation_service.py
│   │       ├── monitoring_service.py
│   │       ├── event_log_service.py
│   │       └── settings_service.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── config.py              # paths, env vars, CLI args
│   │   ├── clock.py               # SystemClock, FixedClock
│   │   ├── logging_setup.py
│   │   └── persistence/
│   │       ├── connection.py      # sqlite3 connection factory (WAL, FK on)
│   │       ├── migrations/        # 0001_initial.sql, 0002_....sql
│   │       ├── migrator.py
│   │       ├── unit_of_work.py    # SqliteUnitOfWork
│   │       ├── mappers.py         # row <-> domain
│   │       └── repositories/      # one per aggregate/table group
│   └── tui/
│       ├── __init__.py
│       ├── app.py                 # NetCoreApp(App)
│       ├── theme.tcss             # dark theme
│       ├── bindings.py            # global key map
│       ├── screens/               # one module per screen (10)
│       ├── widgets/               # reusable widgets
│       └── modals/                # forms, confirm dialogs
└── tests/
    ├── conftest.py
    ├── unit/domain/
    ├── unit/application/
    ├── integration/persistence/
    ├── tui/                       # Textual Pilot tests
    ├── architecture/              # import-rule tests
    └── fixtures/                  # sample labs
```

## 3. Layer Responsibilities

### 3.1 Domain (`netcore.domain`)

- Holds all network business rules: addressing, validation, routing
  lookup, MAC learning, ARP, TTL, forwarding, utilization math.
- Pure, synchronous, deterministic. Time and randomness are injected
  (`now: datetime` parameters, `random.Random` seeded instance).
- `NetworkTopology` is the **aggregate root**: all mutations that must
  preserve cross-device invariants (unique IP, unique MAC, unique
  hostname, interface has ≤ 1 link) go through it.
- Raises typed exceptions from `domain/errors.py`. Never returns
  error codes for invariant violations.
- `LoggerMixin` provides `self.logger` bound to `netcore.<class>`; it
  uses stdlib `logging` only.

### 3.2 Application (`netcore.application`)

- One service per use-case area. Services are thin orchestrators:
  load aggregate via UoW → call domain → commit → publish events →
  return DTOs.
- Defines **ports** (typing `Protocol`) that infrastructure implements:
  `TopologyRepository`, `EventRepository`, `SettingsRepository`,
  `SimulationRepository`, `UnitOfWork`, `Clock`.
- Converts domain exceptions into `ApplicationError` subclasses with a
  user-safe message and an error code (UI shows the message).
- Owns the `EventBus`: synchronous in-process publish/subscribe used by
  monitoring and the TUI (TUI subscribes via a thin adapter that posts
  Textual messages to the app thread).
- Returns immutable DTOs (`@dataclass(frozen=True, slots=True)`); never
  returns domain entities to the TUI.

### 3.3 Infrastructure (`netcore.infrastructure`)

- SQLite via stdlib `sqlite3`. No ORM (decision DEC-006).
- `SqliteUnitOfWork` is a context manager: `BEGIN` on enter, `COMMIT`
  on clean exit, `ROLLBACK` on exception (exception re-raised).
- Connection pragmas: `foreign_keys=ON`, `journal_mode=WAL`,
  `busy_timeout=5000`.
- Migrations: ordered `NNNN_name.sql` files, tracked in
  `schema_migrations(version, applied_at)`.
- Mappers convert rows to domain objects and back; repositories never
  leak `sqlite3.Row` upward.

### 3.4 Presentation (`netcore.tui`)

- Textual `App` with 10 screens (see UI_SPEC.md).
- Screens call services; long-running calls (simulation, traffic
  generation, lab load) run in `@work(thread=True)` workers and report
  results through Textual messages.
- No validation logic beyond input-shape checks (e.g., field not empty).
  All semantic validation comes back as `ApplicationError`.
- Widgets are reusable and data-driven (accept DTOs).

## 4. Key Runtime Flows

### 4.1 Startup

```
python -m netcore [--db PATH] [--seed spine-leaf]
  └─ bootstrap.build_container(config)
       ├─ open sqlite connection, run Migrator
       ├─ construct repositories, UnitOfWork factory, EventBus, Clock
       ├─ construct services
       └─ NetCoreApp(services).run()
            └─ DashboardScreen mounts → DashboardService.summary()
```

### 4.2 Command (e.g., assign IP)

```
IpamScreen (form submit)
  → IpamService.assign_address(device_id, if_name, "10.0.1.10/24")
      with uow:
        topo = uow.topology.load()
        topo.assign_address(...)      # domain validates, may raise
        uow.topology.save(topo)
        uow.events.add(event)
        uow.commit()
      event_bus.publish(event)
  ← InterfaceDTO
IpamScreen refreshes table; notification "Address assigned"
```

### 4.3 Packet Simulation

```
SimulationLabScreen → worker thread
  → SimulationService.send_packet(SendPacketRequest)
      topo = load (read-only snapshot)
      result = ForwardingEngine(topo, settings, rng).simulate(packet)
      persist result + traffic events; publish events
  ← SimulationResultDTO (hops, status, drop reason)
UI thread renders hop trace and highlights path
```

## 5. Cross-Cutting Concerns

| Concern        | Approach |
| -------------- | -------- |
| Errors         | Domain errors → ApplicationError (code, message) → TUI notification. Never swallow; unexpected exceptions are logged with traceback and shown as "Unexpected error (see logs)". |
| Logging        | stdlib `logging`, file handler at `$XDG_STATE_HOME/netcore/netcore.log`. Logging is diagnostic; **NetworkEvent** is the user-visible audit trail. |
| Configuration  | `infrastructure/config.py` resolves CLI flag > env var > settings table > default. |
| Time           | `Clock` port; tests use `FixedClock`. All timestamps UTC ISO-8601. |
| Randomness     | Seeded `random.Random` injected (MAC generation, traffic jitter). |
| Concurrency    | One SQLite connection per thread; workers get their own UoW. Domain objects are not shared across threads — services load fresh snapshots. |
| Identifiers    | Integer surrogate keys from SQLite; domain uses `DeviceId = NewType("DeviceId", int)` etc. New unsaved entities use temporary negative ids assigned by the topology. |
| Security       | No sockets, no `subprocess`, no `os.system` in `src/`. Enforced by an architecture test scanning imports. |

## 6. Quality Gates

Run from the repository root:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
ty check src/netcore
```

`pyproject.toml` (target configuration):

```toml
[project]
name = "netcore-tui"
requires-python = ">=3.12"
dependencies = ["textual>=0.80"]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "ruff>=0.6", "ty"]

[project.scripts]
netcore = "netcore.__main__:main"

[tool.ruff]
line-length = 88
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "RUF", "ANN", "PL", "PT"]
ignore = ["ANN401"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["ANN", "PLR2004"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra --strict-markers"

[tool.ty.environment]
python-version = "3.12"
```

## 7. Extension Points

| Extension                   | Where to add                         | Touches domain? |
| --------------------------- | ------------------------------------ | --------------- |
| New screen                  | `tui/screens/`, service method       | No |
| New device type (e.g., Firewall) | `domain/devices/`, mapper, migration | Yes — needs ARCHITECT design + human approval |
| New drop reason             | `domain/enums.py`, engine, tests     | Yes |
| New persistence backend     | implement ports in `infrastructure/` | No |
| Export format               | `application/services/event_log_service.py` + infra writer | No |

## 8. Architecture Change Process

1. ARCHITECT writes a proposal in `.ai/context/DECISIONS.md` with status
   `PROPOSED`.
2. ORCHESTRATOR checks impact on PRD/specs and open tasks.
3. Human approves (status → `ACCEPTED`) if it matches any gate in
   `CLAUDE.md §15`.
4. Docs updated **before** implementation begins.
