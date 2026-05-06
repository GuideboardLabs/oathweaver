# Workspace Tools

Oathweaver now includes a small, local-first code workspace layer aimed at safe repository assistance rather than fully autonomous coding loops.

## Included capabilities

- Read-only workspace tools
  - `/workspace-tree [path] [depth]`
  - `/workspace-read <path>`
  - `/workspace-search <query> [ | <glob>]`
- Patch proposal flow
  - `/workspace-patch <relative_path> | <instruction>`
  - `/workspace-patches [n]`
  - `/workspace-apply <proposal_id>`
  - `/workspace-reject <proposal_id>`

## Safety model

- Workspace access is scoped to `Projects/<active_project>/...`.
- Patch application uses approval proposals rather than direct AI writes.
- Applying a patch checks a stored SHA-256 hash to make sure the file has not changed since proposal generation.
- Patch reads and proposals are logged in the `workspace_actions` SQLite table.

## Typical flow

1. Select a project with `/project <slug>`.
2. Inspect files with `/workspace-tree`, `/workspace-read`, and `/workspace-search`.
3. Ask for a patch proposal with `/workspace-patch path/to/file.py | add validation for empty usernames`.
4. Review pending patch proposals with `/workspace-patches`.
5. Apply the proposal with `/workspace-apply <id>`.

## Notes

- Patch generation uses the configured local Ollama model. If Ollama is offline, read-only tools still work.
- The patch engine proposes a full-file replacement internally, but presents it as a unified diff for review.
- This is intentionally narrower than a full autonomous coding agent loop.


## Multi-file patch batching

Use `/workspace-patch-batch <path1, path2, ...> | <instruction>` to propose one approval-gated batch across up to 8 files in the active project workspace.

Pending patch proposals now show a compact diff/file preview in the Postbag overlay, where they can be approved or rejected.
