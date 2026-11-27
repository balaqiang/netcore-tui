# Skill: spec-change

## Trigger
An agent finds that the requested behaviour, the code, or another
document disagrees with a spec, or the spec is silent on needed
behaviour.

## Steps
1. **Stop** implementing the affected part. Do not silently pick a side
   (CLAUDE.md §03).
2. Write a conflict note:

   ```
   Conflict ID: CF-<date>-<n>
   Found by: <ROLE> during T-xxx
   Sources: <doc §ref> vs <doc §ref | human request | code path>
   Description: <what disagrees>
   Options:
     A) ... (recommended because ...)
     B) ...
   Impact: <files, tests, interfaces affected>
   Approval gate hit: <CLAUDE.md §15 item or "none">
   ```

3. Send it to ORCHESTRATOR; mark the task `BLOCKED`.
4. After resolution, ORCHESTRATOR (or delegated owner) updates the spec
   **first**, adds a `DEC-NNN` entry if architectural, then unblocks the
   task.

## Checks
- The spec text and the implementation agree after the change.
- PROJECT_STATE.md "Change History" records the resolution.
