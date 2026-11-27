# AGENTS.md — NetCore TUI

Tool-agnostic entry point for AI coding agents (Codex, Cursor, Gemini,
Copilot, Claude, etc.).

> **Canonical instructions live in [CLAUDE.md](CLAUDE.md).**
> This file is a short index. If anything here disagrees with
> `CLAUDE.md`, `CLAUDE.md` wins. Update `CLAUDE.md` first, then this
> file.

## Project in One Paragraph

NetCore TUI is a Python 3.12+ terminal application (Textual) that
simulates data center network management: devices (router, switch,
server), IPAM, routing tables, switch ports, topology, packet forwarding
with TTL/ARP, simulated traffic monitoring, event logs and failure
injection. Architecture: Layered Modular Monolith with OOP, SQLite
persistence. **Simulation only** — no real network access.
Full description: [CLAUDE.md §01–§02](CLAUDE.md#01-project-identity).

## Read Before Working

1. [CLAUDE.md](CLAUDE.md) — rules, protocol, ownership, approval gates
2. [.ai/context/PROJECT_STATE.md](.ai/context/PROJECT_STATE.md) — current phase and next task
3. [.ai/context/TASKS.md](.ai/context/TASKS.md) — task board
4. [.ai/context/DECISIONS.md](.ai/context/DECISIONS.md) — accepted decisions
5. Specs referenced by your task:
   [PRD](docs/PRD.md) ·
   [ARCHITECTURE](docs/ARCHITECTURE.md) ·
   [NETWORK_SPEC](docs/NETWORK_SPEC.md) ·
   [UI_SPEC](docs/UI_SPEC.md) ·
   [UML](docs/UML.md)

## Agent Roles

Pick the role that matches your task and follow its file
(details: [CLAUDE.md §04](CLAUDE.md#04-agent-registry)).

| Role              | Instructions |
| ----------------- | ------------ |
| ORCHESTRATOR      | [.ai/agents/orchestrator.md](.ai/agents/orchestrator.md) |
| ARCHITECT         | [.ai/agents/architect.md](.ai/agents/architect.md) |
| NETWORK_ENGINEER  | [.ai/agents/network-engineer.md](.ai/agents/network-engineer.md) |
| TUI_ENGINEER      | [.ai/agents/tui-engineer.md](.ai/agents/tui-engineer.md) |
| DATABASE_ENGINEER | [.ai/agents/database-engineer.md](.ai/agents/database-engineer.md) |
| QA_ENGINEER       | [.ai/agents/qa-engineer.md](.ai/agents/qa-engineer.md) |
| CODE_REVIEWER     | [.ai/agents/code-reviewer.md](.ai/agents/code-reviewer.md) |

Reusable procedures: [.ai/skills/README.md](.ai/skills/README.md).

## Commands

```bash
pip install -e ".[dev]"          # install (once pyproject.toml exists, T-001)
python -m netcore                # run the app
python -m pytest                 # tests
python -m ruff check .           # lint
python -m ruff format --check .  # format check
ty check src/netcore             # type check (ty, not mypy — DEC-007)
```

Never claim a check passed without running it; otherwise report it as
unverified.

## Hard Rules (summary)

Full list: [CLAUDE.md §05–§15](CLAUDE.md#05-orchestration-protocol).

- Follow DISCOVER → PLAN → DESIGN → IMPLEMENT → TEST → REVIEW → INTEGRATE → DOCUMENT.
- Dependency direction `tui → application → domain`; infrastructure implements ports.
- Domain: no Textual, no SQLite, no I/O. TUI: no network business logic.
- SQL only in repositories, parameterised.
- Longest prefix match, TTL decrement per router hop, switch forwards by destination MAC, explicit ARP.
- No sockets, subprocess or host network changes.
- Work only in files your role owns ([CLAUDE.md §05.3](CLAUDE.md#053-file-ownership)).
- Report spec conflicts; never silently change requirements.
- Human approval needed for the gates in [CLAUDE.md §15](CLAUDE.md#15-human-approval-gates).
- Report with the output contract in [CLAUDE.md §14](CLAUDE.md#14-agent-output-contract).
