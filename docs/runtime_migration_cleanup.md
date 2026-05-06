# Runtime migration cleanup map

This file records which runtime files are still actively used, which ones remain only as compatibility/import leftovers, and which ones are now dead and safe to remove once you no longer need backward compatibility.

## Still active

These are still part of the live system and should remain in place unless their owning subsystem is migrated again.

- `Runtime/cloud/settings.json` — active cloud provider/settings config.
- `Runtime/config/email_config.json` — active email notifier config.
- `Runtime/web/settings.json` — active web/UI config.
- `Runtime/topics/topics.json` — active topic registry.
- `Runtime/project_catalog.json` — active UI/project catalog summary.
- `Runtime/project_pipeline.json` — active pipeline/project orchestration state.
- `Runtime/routines/routines.json` — active routines store.
- `Runtime/watchtower/watches.json` — active watch list state.
- `Runtime/watchtower/briefing_state.json` — active watchtower checkpoint state.
- `Runtime/web/pending_requests.json` — active web-research approval queue.
- `Runtime/web/sources.jsonl` — active append-only web research/source log.
- `Runtime/activity/events.jsonl` — active append-only activity log.
- `Runtime/conversations/` and `Runtime/users/*/conversations/` — active conversation storage.

## Import-only / compatibility leftovers

These are no longer the source of truth. They remain only to support one-time import, fallback resets, or smoother transitions from older copies of the project.

- `Runtime/family/accounts.json` — legacy account bootstrap source. Real users now live in SQLite `users`.
- `Runtime/learning/lessons.json` — legacy lessons file. Real lessons now live in SQLite `lessons`.
- `Runtime/learning/reflections.json` — legacy reflection/lesson fallback. Learning now stages in SQLite.
- `Runtime/memory/project_context.json` — legacy project memory source. Real project memory now lives in SQLite `project_facts`.
- `Runtime/legacy planning/state.json` — legacy legacy planning import source. Real legacy planning state now lives in SQLite legacy planning tables.
- `Runtime/cloud/pending_requests.json` — legacy cloud queue. Real cloud approval/audit state now lives in SQLite `cloud_requests`.
- `Runtime/cloud/runs.jsonl` — legacy cloud run history. Real cloud run history now lives in SQLite `cloud_requests`.

## Dead and removable

These were part of the pre-SQLite filesystem queue design and are no longer the source of truth.

- `Runtime/approvals/pending/` — replaced by SQLite `approvals`.
- `Runtime/approvals/decided/` — replaced by SQLite `approvals`.

## Practical recommendation

Once you are comfortable that you do not need backward-compatibility imports anymore, the next cleanup step can be:

1. remove the import-only files/directories from the runtime template,
2. remove any code paths that write fallback JSON copies for them,
3. simplify reset so it only reports them as historical artifacts rather than resetting them.

For a live snapshot of this same information plus current row counts, run:

```bash
python tools/reset_environment.py --report
```

To preview what a reset would remove without changing anything, run:

```bash
python tools/reset_environment.py --full-reset --dry-run
python tools/reset_environment.py --only-learning-origin reflection --dry-run
```
