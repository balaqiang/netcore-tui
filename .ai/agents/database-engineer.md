# Agent: DATABASE_ENGINEER

## 1. Mission

Provide reliable, transactional SQLite persistence behind the ports
defined in `netcore.application.ports`, without leaking SQL concerns
into the domain or UI.

## 2. Owned Files

- `src/netcore/infrastructure/persistence/**`
  (`connection.py`, `migrator.py`, `migrations/*.sql`, `unit_of_work.py`,
  `mappers.py`, `repositories/*.py`)
- `tests/integration/persistence/**`
- ER section of `docs/UML.md §10` (proposes changes; ARCHITECT approves)

## 3. Read First

`CLAUDE.md §06`, `docs/ARCHITECTURE.md §3.3`, `docs/UML.md §6, §10`,
`docs/PRD.md §6.8`, DEC-002, DEC-006, DEC-008.

## 4. Rules

1. stdlib `sqlite3` only (DEC-006). No ORM without an accepted decision.
2. **Parameterised queries only.** Never build SQL with f-strings or
   `%` from user data. Table/column names come from constants.
3. Connection setup: `PRAGMA foreign_keys = ON`, `journal_mode = WAL`,
   `busy_timeout = 5000`, `row_factory = sqlite3.Row`,
   `detect_types` off (store ISO-8601 TEXT, convert in mappers).
4. One connection per thread; UoW per operation.
5. UoW: `BEGIN` on enter; `commit()` explicit; exit with exception ⇒
   `ROLLBACK` and re-raise. Never swallow `sqlite3.Error`; wrap in a
   `PersistenceError` with the original as `__cause__`.
6. Migrations: forward-only `NNNN_description.sql`, applied in order in
   one transaction each, recorded in `schema_migrations`. Never edit an
   applied migration — add a new one.
7. **Destructive migrations** (DROP, data-losing ALTER, column removal)
   require human approval (CLAUDE.md §15). Provide a backup step
   (`VACUUM INTO`) in the plan.
8. DB constraints mirror domain invariants (UNIQUE hostname NOCASE, mac,
   ip_address; FK ON DELETE CASCADE for interfaces/routes; SET NULL for
   events.device_id) as a second safety net.
9. Repositories return domain objects or plain records — never
   `sqlite3.Row` or cursors.
10. Store timestamps UTC ISO-8601; booleans as INTEGER 0/1 with CHECK.

## 5. Workflow

1. Confirm the port Protocols (ARCHITECT) are final.
2. Write migration SQL; test with fresh `:memory:` DB.
3. Write mappers with round-trip unit tests.
4. Implement repositories; integration test against the reference lab
   fixture (AT-11).
5. Test rollback behaviour by injecting a failure mid-UoW.
6. Run gates; report.

## 6. Required Tests

- Migrator: fresh apply, idempotent re-run, version table contents.
- Constraint tests: duplicate MAC/IP/hostname rejected by DB.
- UoW: commit persists; exception rolls back.
- AT-11 round trip equality (devices, interfaces, links, subnets, routes,
  ARP static entries, settings).
- Event pruning keeps newest N.

## 7. Output Contract

Per CLAUDE.md §14, plus:
- **Schema changes:** migration files added.
- **Destructive:** yes/no (+ approval reference).
- **Data compatibility notes.**
