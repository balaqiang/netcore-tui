# Skill: sqlite-migration

## Trigger
Any change to the database schema, or a new repository.

## Steps
1. Update the ER diagram in `docs/UML.md §10` first (propose to ARCHITECT).
2. Classify the change:
   - **Additive** (new table, nullable column, new index) → proceed.
   - **Destructive** (DROP, rename, NOT NULL without default, data
     rewrite) → stop, request human approval via ORCHESTRATOR with a
     backup plan (`VACUUM INTO 'backup-<ts>.db'`).
3. Create `src/netcore/infrastructure/persistence/migrations/NNNN_<name>.sql`
   with the next number. Never edit an applied migration.
4. Include constraints: `PRIMARY KEY`, `FOREIGN KEY ... ON DELETE`,
   `UNIQUE`, `CHECK (admin_up IN (0,1))`, `CHECK (device_type IN (...))`.
5. Update mappers (row ↔ domain) and repositories. SQL uses `?`
   placeholders only.
6. Tests:
   - migrator applies on fresh `:memory:` DB,
   - re-running migrator is a no-op,
   - repository round trip,
   - constraint violation raises `PersistenceError`.

## Checks
- `SELECT version FROM schema_migrations` lists the new number.
- No f-string/`%` SQL built from data (`grep -n 'execute(f' src/` is empty).
