# Skill: architecture-guard

## Trigger
Adding a module, adding an import across packages, or writing
`tests/architecture/` tests.

## Rules to enforce (ARCHITECTURE.md §1.1)

| Package               | Forbidden imports |
| --------------------- | ----------------- |
| `netcore.domain`      | `textual`, `sqlite3`, `netcore.application`, `netcore.infrastructure`, `netcore.tui` |
| `netcore.application` | `textual`, `sqlite3`, `netcore.infrastructure`, `netcore.tui` |
| `netcore.tui`         | `sqlite3`, `netcore.infrastructure`, `netcore.domain.simulation` |
| `src/netcore/**`      | `socket`, `subprocess`, `ctypes`, `scapy`; calls to `os.system`, `eval`, `exec` |

## Steps
1. Before adding an import, check the table. If it is forbidden, the
   design is wrong — route through a port/DTO instead, or ask ARCHITECT.
2. Implement the guard test with `ast`:
   - walk `src/netcore/<pkg>/**/*.py`,
   - collect `Import` / `ImportFrom` module names (resolve relative
     imports against the file's package),
   - assert none start with a forbidden prefix,
   - assert no `Call` node targets `os.system`, `eval`, `exec`.
3. Circular import check: import every module under `netcore` in a
   fresh interpreter (`importlib.import_module`) — any `ImportError`
   from partial initialisation fails the test.

## Checks
- Guard test fails when a deliberately bad import is added (verify once
  locally, then remove the bad import).

## Output
List of rules covered and the test file path.
