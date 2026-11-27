# NetCore Skills Index

Skills are short, repeatable execution recipes. An agent applies a skill
when its task brief names it or when the trigger matches. Skills never
override `CLAUDE.md` or the specs; they describe *how* to do a recurring
job consistently.

| Skill | Trigger | Primary user |
| ----- | ------- | ------------ |
| [quality-gates.md](quality-gates.md) | Before reporting any task | All engineers, QA |
| [architecture-guard.md](architecture-guard.md) | Adding modules/imports; writing import-rule tests | ARCHITECT, QA, REVIEWER |
| [network-scenario-test.md](network-scenario-test.md) | Testing any forwarding/validation rule | NETWORK_ENGINEER, QA |
| [textual-screen.md](textual-screen.md) | Creating or changing a screen/widget | TUI_ENGINEER |
| [sqlite-migration.md](sqlite-migration.md) | Any schema change or new repository | DATABASE_ENGINEER |
| [spec-change.md](spec-change.md) | Behaviour or interface differs from docs | Any agent → ORCHESTRATOR |
| [add-or-fix-type-checking/SKILL.md](add-or-fix-type-checking/SKILL.md) | `ty check` reports errors | All engineers |
| [tui-ux-pro-max/SKILL.md](tui-ux-pro-max/SKILL.md) | Designing, building or reviewing TUI look, layout, keys, feedback | TUI_ENGINEER, CODE_REVIEWER |

Note for `add-or-fix-type-checking`: this project has no Makefile —
read `make typing` as `ty check src/netcore` (DEC-007).

Skill file format:

```
# Skill: <name>
Trigger / Inputs / Steps / Checks / Output
```
