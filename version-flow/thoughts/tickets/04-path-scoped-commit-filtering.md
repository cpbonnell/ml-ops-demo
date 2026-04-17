# Ticket 4: Path-scoped commit message filtering

**Size: L**
**Depends on:** Ticket 1

## Summary

When `owned_paths` is configured, filter commit messages to only include commits
that touched files under those paths. This prevents unrelated commits in the
monorepo from influencing a sub-project's version bump priority.

## Problem

In a monorepo, all sub-projects share commit history. If sub-project B gets a
`feat!: breaking change` commit, sub-project A would see it and get an unearned
major bump. We need to filter commits by which files they touched.

## Implementation

### Core filtering logic (new function in `git.py`)

Add a function that, given a commit and a list of owned paths, determines
whether the commit touched any file under those paths:

```python
def commit_touches_paths(repo: Repo, commit_id: bytes, owned_paths: list[Path],
                         repo_root: Path) -> bool
```

Use dulwich `diff_tree.tree_changes()` (already used at `git.py:314`) to diff
each commit against its parent and check if any changed file path starts with
one of the owned paths.

### Edge cases

- **Merge commits** (multiple parents): Diff against the first parent. This
  matches the standard git convention for merge commit diffs and avoids
  double-counting.
- **Initial commit** (no parent): Always include it — it's the repo bootstrap.
- **Commits touching multiple sub-projects**: Include them. Better to over-bump
  than under-bump. The commit message is presumably relevant if it touched your
  files.
- **Empty `owned_paths`**: No filtering occurs — all commits returned (backward
  compatible).

### Integration points

Modify `get_commit_messages()` in `git.py` (line 385+):

- Add optional `owned_paths: list[Path]` and `repo_root: Path` parameters.
- After collecting commits, filter them through `commit_touches_paths` if
  `owned_paths` is non-empty.

Modify `get_commit_messages()` in `clairity_repo.py`:

- Pass `owned_paths` from config through to the `git.get_commit_messages()`
  call.

Callers will be fully wired up in Tickets 5 and 6, but signatures must accept
the parameter here.

## Testing

Build a synthetic dulwich repo with the following commits:

1. Commit touching `services/pipeline-a/main.py` with message
   `feat: new pipeline feature`
2. Commit touching `services/pipeline-b/main.py` with message
   `feat!: breaking change to B`
3. Commit touching both `services/pipeline-a/util.py` and `shared/lib.py` with
   message `fix: shared fix`
4. Merge commit touching `services/pipeline-b/config.py`

Verify with `owned_paths = ["services/pipeline-a"]`:

- Commits 1 and 3 are included
- Commits 2 and 4 are excluded
- Resulting bump priority is `minor` (from commit 1), not `major`

Verify with empty `owned_paths`:

- All 4 commits are included (backward compat)

## Key files

- `version_flow/git.py` — `get_commit_messages()`, new `commit_touches_paths()`
- `version_flow/clairity_repo.py` — `get_commit_messages()`
- Tests
