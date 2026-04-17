# Ticket 7: Release PR scoping per sub-project

**Size: S-M**
**Depends on:** Ticket 1

## Summary

When `project_name_in_tag` is set, scope release PR creation so that each
sub-project gets its own release PR with clear naming, and PRs don't collide
across sub-projects.

## Implementation

### `clairity_repo.py` — `create_next_release_pr()` (line ~276+)

1. **PR title**: Include the project name when configured.
    - With prefix: `"Release: my-data-pipeline v1.2.0"`
    - Without prefix: same as today (backward compatible)

2. **PR body**: Include the project name for clarity so reviewers know which
   sub-project is being released.

3. **Duplicate detection**: When checking for existing release PRs (to avoid
   creating duplicates), filter by project prefix in the title. Without this,
   sub-project A's release PR would prevent sub-project B from creating its own.

### Trunk flow integration

`trunk_flow.py:77` calls `clairity_repo.create_next_release_pr(dry_run)`. The
`ClairityRepo` already has access to the config, so it can read
`project_name_in_tag` internally. No changes needed in `trunk_flow.py`.

### FDA flow

There's currently a TODO at `fda_flows.py:102-103` about release PR creation in
FDA flow. This ticket should at minimum ensure the infrastructure supports it
when that TODO is addressed. If the TODO is in scope, implement it with project
scoping included.

## Testing

- Release PR created with project name in title when prefix is configured
- Release PR created without project name when prefix is absent (regression)
- Duplicate detection: existing PR for project A does not block PR creation for
  project B
- Duplicate detection: existing PR for project A does block a second PR for
  project A

## Key files

- `version_flow/clairity_repo.py` — `create_next_release_pr()`
- Tests for release PR creation
