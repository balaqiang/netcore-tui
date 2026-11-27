# NETCORE TUI — AI ORCHESTRATION

Entry point for every AI coding agent working on this repository.
Read this file completely before doing anything else.

This is the canonical instruction file. [AGENTS.md](AGENTS.md) is a
short, tool-agnostic index that links back here; when this file
changes, keep AGENTS.md in sync.

## 01. Project Identity

- Name: NetCore TUI
- Full name: Data Center Network Management & Traffic Simulator
- Type: Educational network management and packet simulator
- Language: Python 3.12+
- Framework: Textual (presentation layer only)
- Architecture: Layered Modular Monolith (`src/netcore`)
- Paradigm: Object-Oriented Programming
- Database: SQLite (stdlib `sqlite3`, no ORM)
- Operation mode: Local network **simulation only**
- Development method: Spec-Driven Development,
  Hierarchical Multi-Agent Orchestration, Skill-Based Execution
- Quality tooling: pytest (tests), Ruff (lint + format), ty (types)

### Description

NetCore TUI is a terminal application in which the user acts as a
Network Administrator in a virtual data center. The user manages
routers, switches and servers, performs IP address management (IPAM),
configures routing tables, connects devices, visualizes the topology
and simulates packet delivery hop by hop. The system also provides
device status monitoring, simulated traffic statistics, an event log
and failure injection for troubleshooting practice.

Everything runs virtually so learners can study routing, switching,
subnetting, packet forwarding, TTL, ARP and network management without
physical infrastructure, while experiencing part of a professional data
center administrator's workflow.

## 02. Primary Objective

Develop a professional terminal-based network management and packet
simulation application that supports:

- Network device management (router, switch, server)
- IP address management (IPAM)
- Router configuration (connected, static, default routes)
- Switch port management and MAC address tables
- Network topology visualization
- Packet forwarding simulation and traceroute
- Simulated traffic monitoring
- Event logging
- Network failure simulation (device, link, port)

The application must operate without access to physical network
infrastructure and without touching the host network configuration.

## 03. Source of Truth

Read, in this order, before implementation:

| # | Document                       | Owner             | Contains |
| - | ------------------------------ | ----------------- | -------- |
| 1 | `docs/PRD.md`                  | ORCHESTRATOR / Human | Goals, user stories, FR/NFR, acceptance tests AT-01..AT-12, phases |
| 2 | `docs/ARCHITECTURE.md`         | ARCHITECT         | Layers, folder layout, flows, quality gate config |
| 3 | `docs/NETWORK_SPEC.md`         | NETWORK_ENGINEER  | Normative network rules: addressing, routing, switching, ARP, TTL, drops, traffic |
| 4 | `docs/UI_SPEC.md`              | TUI_ENGINEER      | Screens, keymap, theme, widgets, async rules |
| 5 | `docs/UML.md`                  | ARCHITECT         | Class, sequence, state and ER diagrams (public contract) |
| 6 | `.ai/context/PROJECT_STATE.md` | ORCHESTRATOR      | Current phase, verified status, next task |
| 7 | `.ai/context/TASKS.md`         | ORCHESTRATOR      | Task board with owners, deps, acceptance criteria |
| 8 | `.ai/context/DECISIONS.md`     | ARCHITECT / Human | Architecture decision records DEC-001..DEC-015 |

Supporting material:

- `.ai/agents/*.md` — role instructions (§04)
- `.ai/skills/*.md` — reusable execution recipes (§05.4)

Precedence when sources disagree:

1. Explicit human instruction in the current conversation
2. Accepted decisions in `DECISIONS.md`
3. `docs/NETWORK_SPEC.md` (network behaviour) / `docs/UI_SPEC.md` (UI)
4. `docs/ARCHITECTURE.md` and `docs/UML.md`
5. `docs/PRD.md`
6. Existing code

If specifications conflict, **report the conflict before changing
architectural decisions** (use `.ai/skills/spec-change.md`).
Never silently modify established requirements.

## 04. Agent Registry

| Role              | Responsibility                                  | Instructions |
| ----------------- | ----------------------------------------------- | ------------ |
| ORCHESTRATOR      | Planning, delegation, integration, project state | `.ai/agents/orchestrator.md` |
| ARCHITECT         | Architecture, interfaces, ports, DTOs, UML, ADRs | `.ai/agents/architect.md` |
| NETWORK_ENGINEER  | Network simulation, routing logic, domain, services | `.ai/agents/network-engineer.md` |
| TUI_ENGINEER      | Textual screens, widgets and user interaction    | `.ai/agents/tui-engineer.md` |
| DATABASE_ENGINEER | Persistence, migrations and repositories         | `.ai/agents/database-engineer.md` |
| QA_ENGINEER       | Unit, integration, acceptance and interface tests | `.ai/agents/qa-engineer.md` |
| CODE_REVIEWER     | Independent implementation review                | `.ai/agents/code-reviewer.md` |

Hierarchy:

```
Human (product owner, approval gates)
  └── ORCHESTRATOR
        ├── ARCHITECT
        ├── NETWORK_ENGINEER
        ├── TUI_ENGINEER
        ├── DATABASE_ENGINEER
        ├── QA_ENGINEER
        └── CODE_REVIEWER (independent)
```

A single AI session may play several roles sequentially, but must
announce the active role and follow that role's instructions and file
ownership while acting in it. The reviewer role must not review its own
implementation in the same pass without saying so.

## 05. Orchestration Protocol

### 05.1 Lifecycle

Every development task follows:

```
DISCOVER → PLAN → DESIGN → IMPLEMENT → TEST → REVIEW → INTEGRATE → DOCUMENT
```

| Step      | Purpose | Exit artefact |
| --------- | ------- | ------------- |
| DISCOVER  | Read context and specs; inspect code; list unknowns. | Discovery notes |
| PLAN      | Define tasks, owners, deps, acceptance criteria. | Entries in `TASKS.md` |
| DESIGN    | Define/adjust interfaces and UML when contracts change. | UML/ARCH update, DEC entry |
| IMPLEMENT | Write code + unit tests within owned files. | Code |
| TEST      | Run quality gates and scenario tests. | Gate output |
| REVIEW    | Independent review against checklist. | Review report |
| INTEGRATE | Compose pieces; full suite green. | Green full suite |
| DOCUMENT  | Docs match behaviour; state updated. | `PROJECT_STATE.md` |

A step may be skipped only with a written reason in the task notes.

### 05.2 Orchestrator Duties

- Analyze the requested feature and map it to PRD ids.
- Identify affected modules and layers.
- Determine dependencies and order.
- Assign exactly one owning agent per task and per file.
- Define acceptance criteria.
- Prevent overlapping file ownership.
- Validate implementation results (re-run gates).
- Request human approval for breaking changes (§15).
- Update project state only after verification.

### 05.3 File Ownership

| Path                                              | Owner |
| ------------------------------------------------- | ----- |
| `CLAUDE.md`, `AGENTS.md`, `.ai/context/PROJECT_STATE.md`, `.ai/context/TASKS.md` | ORCHESTRATOR |
| `docs/PRD.md`                                     | ORCHESTRATOR (human approves) |
| `docs/ARCHITECTURE.md`, `docs/UML.md`, `.ai/context/DECISIONS.md` | ARCHITECT |
| `pyproject.toml`, `src/netcore/bootstrap.py`, `src/netcore/__main__.py` | ARCHITECT |
| `src/netcore/application/{ports,dto,errors,event_bus}.py` | ARCHITECT |
| `src/netcore/infrastructure/{config,clock,logging_setup}.py` | ARCHITECT |
| `docs/NETWORK_SPEC.md`, `src/netcore/domain/**`, `src/netcore/application/services/**` | NETWORK_ENGINEER |
| `docs/UI_SPEC.md`, `src/netcore/tui/**`           | TUI_ENGINEER |
| `src/netcore/infrastructure/persistence/**`       | DATABASE_ENGINEER |
| `tests/conftest.py`, `tests/fixtures/**`, `tests/acceptance/**`, `tests/architecture/**`, `tests/tui/**` | QA_ENGINEER |
| `tests/unit/**`, `tests/integration/**`           | Owner of the code under test |
| `.ai/agents/**`, `.ai/skills/**`                  | ORCHESTRATOR (role owners may propose) |

### 05.4 Skill-Based Execution

Recurring procedures are encoded as skills in `.ai/skills/`:

| Skill                     | Use when |
| ------------------------- | -------- |
| `quality-gates.md`        | Before reporting any task |
| `architecture-guard.md`   | Adding imports/modules, writing layer tests |
| `network-scenario-test.md`| Testing network rules |
| `textual-screen.md`       | Building screens/widgets |
| `sqlite-migration.md`     | Schema or repository changes |
| `spec-change.md`          | Spec conflict or gap |
| `add-or-fix-type-checking/SKILL.md` | Fixing `ty` errors (`make typing` ⇒ `ty check src/netcore`) |
| `tui-ux-pro-max/SKILL.md` | TUI design, layout, keyboard UX, theme, UI review |

### 05.5 Parallel Execution

Permitted only when tasks have no shared files, no unfinished interface
dependency between them, and separate test files. See the
parallelisation map in `TASKS.md`. When in doubt, run sequentially.

## 06. Architectural Constraints

Dependency direction:

```
TUI → Application Services → Domain
Infrastructure → implements Application ports, uses Domain
bootstrap.py → wires everything (single composition root)
```

Rules:

- Domain must not import Textual.
- Domain must not depend directly on SQLite.
- Domain is pure: no I/O, no `datetime.now()`, no global RNG
  (clock and seeded RNG are injected).
- TUI must not contain network business logic.
- TUI must not import infrastructure or domain entities; it uses
  services and DTOs.
- Database queries must use repositories (parameterised SQL only).
- Services coordinate application use cases inside a Unit of Work.
- Dependencies must be explicit (constructor injection).
- Circular imports are prohibited.
- Rules are enforced by tests in `tests/architecture/`.

Package layout and responsibilities: `docs/ARCHITECTURE.md §2–§3`.

## 07. Core Domain Models

Preserve the original OOP foundation (DEC-003):

- `NetworkDevice` (abstract) → `Router`, `Switch`, `Server`
- `Packet`
- `Link`
- `NetworkTopology` (aggregate root, DEC-008)
- `LoggerMixin`

Existing responsibilities must be preserved unless an approved
specification requires changes.

Additional models:

- `NetworkInterface`, `SwitchPort`
- `RoutingEntry`, `RoutingTable`
- `MacTable`, `ArpTable`
- `Subnet`
- `Frame`
- `NetworkEvent`, `TrafficEvent`
- `SimulationResult`, `HopRecord`
- `ForwardingEngine`, `TrafficGenerator`

Exact signatures: `docs/UML.md §2–§5`.

## 08. Network Simulation Rules

Full normative rules: `docs/NETWORK_SPEC.md`. Summary:

- Validate IPv4 addresses and CIDR subnets (`ipaddress`, strict).
- Reject duplicate IP, MAC and hostname addresses lab-wide.
- Use longest prefix match for routing (network semantics, never strings).
- Tie-break routes by admin distance, metric, insertion order.
- Decrement TTL at every router hop.
- Drop packets when TTL expires (`TTL_EXPIRED`).
- Validate next-hop connectivity when adding static routes.
- Prevent forwarding through offline devices, down links, down ports.
- Switch forwarding must use destination MAC only; learn source MAC.
- Simulated ARP is explicit: per-device tables, broadcast request,
  reply, expiry; ARP does not consume TTL.
- Record every forwarding, delivery and drop as hop records and events.
- Distinguish bandwidth capacity from simulated utilization.
- Never fabricate real network measurements; label simulated values.
- Simulation is deterministic for a given topology, input and seed.

## 09. TUI Design Rules

Use Textual for the presentation layer. Full spec: `docs/UI_SPEC.md`.

Required screens (number key → screen id):

| Key | Screen                  | id             |
| --- | ----------------------- | -------------- |
| 1   | Dashboard               | `dashboard`    |
| 2   | Device Management       | `devices`      |
| 3   | IP Address Management   | `ipam`         |
| 4   | Routing Table           | `routing`      |
| 5   | Switch Port Management  | `switch-ports` |
| 6   | Network Topology        | `topology`     |
| 7   | Packet Simulation Lab   | `packet-lab`   |
| 8   | Traffic Monitor         | `traffic`      |
| 9   | Event Logs              | `events`       |
| 0   | Settings                | `settings`     |

Design requirements:

- Keyboard-first navigation; every action has a binding.
- Responsive terminal layout (min 100×30; breakpoints in UI_SPEC §7).
- Clear focus indicators.
- Consistent visual hierarchy.
- Dark terminal theme (`tui/theme.tcss`).
- Non-blocking UI: long operations in Textual workers.
- Readable errors and status messages; status never by color alone.
- Reusable components and widgets driven by DTOs.

## 10. Coding Standards

- Follow PEP 8 (enforced by Ruff, line length 88).
- Use type hints on all functions and public attributes.
- Use descriptive identifiers.
- Prefer composition where appropriate.
- Preserve encapsulation (`_private` state, read-only properties).
- Follow SOLID principles pragmatically.
- Avoid unnecessary abstractions.
- Avoid hardcoded application state; constants live in dedicated modules.
- Do not swallow exceptions; raise typed errors with codes.
- Do not expose private attributes to the TUI.
- Do not introduce dependencies without justification
  (runtime deps need human approval).
- Value objects are frozen dataclasses.
- Docstrings on public classes and functions.

## 11. Testing Protocol

Required checks (run from repository root):

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
ty check src/netcore
```

Note: type checking uses **ty** (DEC-007), replacing the earlier mypy
command, per the human project description.

Mandatory test scenarios (PRD §8):

| AT    | Scenario |
| ----- | -------- |
| AT-01 | Successful packet delivery |
| AT-02 | Invalid IPv4 address |
| AT-03 | Duplicate IP address |
| AT-04 | Duplicate MAC address |
| AT-05 | Missing routing entry |
| AT-06 | Longest prefix match |
| AT-07 | TTL expiration |
| AT-08 | Offline network device |
| AT-09 | Disconnected network link |
| AT-10 | Invalid switch port |
| AT-11 | Database persistence |
| AT-12 | TUI keyboard navigation |

Never claim a test passed without running it.
If execution is unavailable, report the test as **unverified**.

## 12. Security and Scope

Default operation is simulation-only (DEC-004).

Prohibited by default:

- Connecting to physical routers or switches
- Modifying host network configuration
- Executing arbitrary shell commands from the TUI
- Importing `socket`, `subprocess` or similar in `src/`
- Storing credentials in source code
- Sending or capturing raw network packets

Real network integration requires separate human approval and a
dedicated specification.

## 13. Definition of Done

A task is complete only when:

- Acceptance criteria in `TASKS.md` are satisfied.
- Implementation follows architecture and specs.
- Relevant tests have been executed (output recorded).
- No unresolved BLOCKER or MAJOR review findings remain.
- Documentation reflects actual behavior.
- Project state has been updated by the ORCHESTRATOR.
- Changes have passed the review stage.

## 14. Agent Output Contract

Each agent must report:

```
Task ID:
Agent role:
Status:            DONE | REVIEW | BLOCKED | FAILED
Summary:
Files changed:
Tests executed:    exact commands
Test results:      exit codes + summary lines, or UNVERIFIED (reason)
Architectural decisions:  DEC ids added/used, or none
Known limitations:
Recommended next task:
```

Role files may add extra fields.

## 15. Human Approval Gates

Require human approval before:

- Breaking public interfaces
- Changing core architectural patterns
- Removing existing features
- Introducing destructive migrations
- Adding real network access
- Changing the approved project scope
- Adding a new runtime dependency

## 16. Quick Start for an Agent

1. Read this file, then `PROJECT_STATE.md` → "Next Task".
2. Open that task in `TASKS.md`; read the referenced spec sections.
3. Load your role file from `.ai/agents/` and any named skills.
4. Work only in your owned files.
5. Run `.ai/skills/quality-gates.md`.
6. Report with the §14 contract.
