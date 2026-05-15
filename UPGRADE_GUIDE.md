# Upgrade Guide

## Upgrading from 0.9.x to 1.0

This upgrade path is expected to be low-friction for current local installs.

## Before You Upgrade

1. Back up local state folders if you care about recovery snapshots:
   - `Runtime/`
   - `Projects/`
2. Record your current version/tag:
   - `cat VERSION`
   - `git describe --tags --always`
3. Confirm your local model inventory (`ollama list`) has enough disk headroom.

## Upgrade Steps

1. Pull the target release/tag.
2. Re-run platform installer:
   - Linux: `./install_oathweaver_linux.sh`
   - Windows: `install_oathweaver.ps1`
3. Start Oathweaver and run one research turn + one make turn.
4. Verify Web GUI/API/CLI/TUI surfaces you use most.

## Known Surface Changes from Early 0.9.x

These changes already landed in `0.9.x` release-candidate work and remain in 1.0:
- Personal/life memory capture surfaces removed
- Image-generation lanes removed
- Legacy planner/home artifacts retired from active runtime surfaces

## Environment and Config Notes

- No mandatory environment-variable rename is required for `0.9.x -> 1.0` at this time.
- Keep using your current model-routing and hardware-profile config unless release notes call out a migration.
- If you exposed services beyond loopback manually, re-validate your security posture after upgrade.

## Rollback

1. Stop Oathweaver services/processes.
2. Checkout your previous tag.
3. Restore backed-up `Runtime/` and `Projects/` as needed.
4. Restart with the previous scripts.
