# Constraints

Last reviewed: 2026-11-14

## Floor (always enforced)

- No new suppression comments that hide type or lint errors
- No unimplemented stubs (`raise NotImplementedError`, empty `except: pass`)
- No skipped or deleted tests without a reason in the commit message
- No secrets in source
- This file does not get weakened to make a change pass
- No direct writes to World state outside GameMaster-approved paths
- All new models remain frozen, strict, extra="forbid"
- Determinism: same initial World + same structured action → identical resulting World

## Enforced with numbers

| Dimension | Rule | Checked by | Runs at |
|-----------|------|-----------|---------|
| Imports | All engine modules import cleanly | `python test_imports.py` | every edit |
| Models | frozen, strict, extra="forbid" | code review + existing tests | every edit |
| Determinism | same state + same action = same result | kernel tests (clock, tick, deny) | task end |

## Measured, not yet enforced

| Metric | Today | Direction |
|--------|-------|-----------|
| Import kernel | passes | must not fall |
| Project coverage | not measured | measure before enforcing |

## Exceptions

| ID | Rule | Path | Reason | Owner | Expires |
|----|------|------|--------|-------|---------|
| (none) | | | | | |
