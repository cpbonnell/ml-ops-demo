# Ticket 5: Wire monorepo support into trunk flow

**Size: M**
**Depends on:** Tickets 3, 4

## Summary

Connect the prefix-aware tag discovery (Ticket 3) and path-scoped commit
filtering (Ticket 4) into the trunk flow path, so that monorepo sub-projects
using trunk flow are versioned correctly.

## Implementation

### `clairity_repo.py`

The `ClairityRepo` class wraps git operations for the trunk flow. Update the
following methods to pass monorepo config through:

- **`get_most_recent_version_tag()`** (line ~90-106): Currently walks commit
  history looking for any version tag. Must pass `project_name_in_tag` to the
  tag lookup so it only finds tags belonging to this sub-project.
- **`get_commit_messages()`**: Pass `owned_paths` and `repo_root` through to
  `git.get_commit_messages()` for path filtering.
- **`do_version_bump_commit()`**: Pass `project_name_in_tag` through to
  `git.do_version_bump_commit()` for prefixed tag creation.

The `ClairityRepo` already receives a `ProjectConfig` (or should — verify), so
it can read `config.project_name_in_tag` and `config.owned_paths` directly.

### `trunk_flow.py`

The trunk flow function (`trunk_flow()` at line 11) orchestrates the version
bump. Changes needed:

- **`check_current_version_state()`** (line 80-129): The `tagged_version_string`
  it receives will now come from the prefix-filtered tag lookup, so the
  comparison logic should work as-is. Verify this.
- No other changes expected in `trunk_flow.py` itself if `clairity_repo` handles
  the plumbing.

### Verification checklist

With a monorepo trunk flow config:

1. `get_most_recent_version_tag()` returns only the sub-project's latest tag
2. `check_current_version_state()` compares against the correct (
   sub-project-specific) tag
3. Commit messages are filtered to only those touching owned paths
4. The bump commit creates a prefixed tag
5. The tag push uses the correct prefixed ref

Without `project_name_in_tag` / `owned_paths`:

1. All behavior is identical to today (regression tests pass)

## Testing

Integration-style test: mock or build a repo simulating a monorepo trunk flow
scenario with two sub-projects. Run trunk flow for one sub-project and verify:

- Correct tag is found as baseline
- Only relevant commits are considered
- Correct prefixed tag is created
- Other sub-project's tags are not disturbed

Regression: run existing trunk flow tests unchanged to confirm backward
compatibility.

## Key files

- `version_flow/trunk_flow.py`
- `version_flow/clairity_repo.py`
- `tests/test_trunk_flow.py`
