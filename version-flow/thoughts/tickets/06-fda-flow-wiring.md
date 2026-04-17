# Ticket 6: Wire monorepo support into FDA flow

**Size: S-M**
**Depends on:** Tickets 3, 4

## Summary

Connect the prefix-aware tag discovery (Ticket 3) and path-scoped commit
filtering (Ticket 4) into the FDA git flow path.

## Implementation

### `fda_flows.py`

The FDA flow calls git functions directly (not through `ClairityRepo`), so the
wiring is more straightforward.

Update `fda_git_flow()` (line 68+):

1. **Line 87** — `git.find_effective_version(repo, repo.head())`:
   Pass `config.project_name_in_tag` so it uses prefix-aware tag discovery.

2. **Line 91** — `git.get_commit_messages(repo, current_version_tag)`:
   Pass `config.owned_paths` and `config.repository_root` for path-scoped
   filtering.

3. **Line 100** —
   `git.do_version_bump_commit(config, repo, new_version, dry_run)`:
   The `config` is already passed, so `do_version_bump_commit` can read
   `config.project_name_in_tag` directly (or it may need to be passed explicitly
   depending on Ticket 2's interface — check).

### Verification checklist

With a monorepo FDA flow config:

1. `find_effective_version()` returns only the sub-project's version
2. Commit messages are filtered to only those touching owned paths
3. Bump priority is correct for the sub-project's changes only
4. The bump commit creates a prefixed tag

Without `project_name_in_tag` / `owned_paths`:

1. All behavior is identical to today

## Testing

Integration-style test: simulate FDA flow in a monorepo scenario. Verify:

- Correct effective version is found with prefix
- Only relevant commits influence bump priority
- Prefixed tag is created
- Branch label logic (trunk/rc/release) still works correctly with prefixed tags

Regression: run existing FDA flow tests to confirm backward compatibility.

## Key files

- `version_flow/fda_flows.py`
- `tests/test_fda_flows.py`
