# Skill: quality-gates

## Trigger
Before an agent reports a task as `REVIEW` or `DONE`.

## Steps
1. From the repository root, run in order:

   ```bash
   python -m ruff format --check .
   python -m ruff check .
   ty check src/netcore
   python -m pytest
   ```

2. If formatting fails, run `python -m ruff format .` on **your owned
   files only**, then re-run the check.
3. Fix lint and type errors properly (for ty errors apply
   `add-or-fix-type-checking/SKILL.md`). Suppressions (`# noqa: <rule>`,
   `# ty: ignore[<rule>]`) need a specific rule code and a one-line
   justification.
4. For fast iteration, scope pytest (`python -m pytest tests/unit/domain -q`),
   but the final run must be the full suite.

## Checks
- Every command's exit code is 0.
- No new warnings introduced in pytest output (`-ra` summary).

## Output (paste into report)

```
Tests executed:
  ruff format --check .   → exit 0
  ruff check .            → exit 0 (All checks passed!)
  ty check src/netcore    → exit 0
  pytest                  → exit 0 (57 passed in 2.1s)
```

If a tool is missing or cannot be executed, write
`UNVERIFIED — <reason>`. Never write "passed" for a command not run.
