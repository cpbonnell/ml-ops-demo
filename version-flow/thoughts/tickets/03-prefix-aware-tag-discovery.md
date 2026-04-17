# Ticket 3: Prefix-aware tag discovery

**Size: M**
**Depends on:** Ticket 2

## Summary

Refactor tag discovery so that when a project prefix is configured, version-flow
only sees tags belonging to that sub-project. This prevents sub-projects from
interfering with each other's version history.

## Problem

`commit_id_to_version_map()` (`git.py:204-210`) scans all tags in the repo
matching the version regex. In a monorepo with multiple sub-projects,
sub-project A would see sub-project B's tags, leading to incorrect "effective
version" calculations.

The function is also `@cache`'d with only `repo` as the key, so it cannot
currently distinguish between different project contexts.

## Implementation

### `commit_id_to_version_map()` (`git.py:204-210`)

1. Add an optional `project_prefix: str | None` parameter.
2. When prefix is set:
    - Only match tags starting with `{prefix}/`
    - Strip the prefix before parsing the version string
    - The returned dict values (tag names as bytes) should be the version
      portion only (without prefix), since they're fed into
      `Version.from_string()`
3. When prefix is `None`:
    - Match tags as today (bare version strings)
    - Exclude any tags that contain a `/` before the version to avoid
      accidentally picking up another project's prefixed tags
4. Replace `@cache` with `@lru_cache` using `(repo, project_prefix)` as the
   composite key, or restructure caching to accommodate the new parameter.

### `find_effective_version()` (`git.py:213-235`)

1. Add `project_prefix: str | None` parameter.
2. Pass it through to `commit_id_to_version_map()`.
3. No other logic changes needed — the filtering happens in the map.

### All callers of these functions

Update call sites to pass the prefix through. Current callers:

- `fda_flows.py:87` — `find_effective_version(repo, repo.head())`
- `clairity_repo.py` — via `get_most_recent_version_tag()`

These callers will be fully wired up in Tickets 5 and 6, but the function
signatures must accept the parameter here.

## Testing

Create a synthetic repo (or mock) with mixed tags:

- `v1.0.0`, `v1.1.0` (unprefixed)
- `project-a/v2.0.0`, `project-a/v2.1.0`
- `project-b/v3.0.0`

Verify:

- `commit_id_to_version_map(repo, None)` returns only `v1.0.0`, `v1.1.0`
- `commit_id_to_version_map(repo, "project-a")` returns only `v2.0.0`, `v2.1.0`
- `commit_id_to_version_map(repo, "project-b")` returns only `v3.0.0`
- `find_effective_version` with each prefix returns correct version walking back
  through history

## Key files

- `version_flow/git.py` — `commit_id_to_version_map()`,
  `find_effective_version()`
- Tests for git operations
