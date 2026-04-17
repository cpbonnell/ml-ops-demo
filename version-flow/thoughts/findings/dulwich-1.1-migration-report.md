# Dulwich 0.24 to 1.1 Migration Report

**Date:** 2026-03-16
**Branch:** `ps-4413-update-deps-to-dulwich-1.0`
**Test Results:** 17 failed, 216 errors, 94 passed, 6 xfailed (3.01s)

---

## Summary

Updating dulwich from 0.24.x to 1.1.0 introduces two breaking changes that surface immediately in the test suite. Both originate in the shared test fixtures in `conftest.py`, which means they cascade to block virtually all parameterized tests. Once those fixture issues are fixed, there are additional locations in both application and test code that may need attention due to API changes in dulwich 1.x (particularly around `Repo.path` type changes).

---

## Confirmed Breaking Changes (Surfaced by Tests)

### 1. `Repo.stage()` has been removed

- **Error:** `AttributeError: 'Repo' object has no attribute 'stage'`
- **Tests affected:** 17 FAILED
- **Root location:** `tests/conftest.py:159`

```python
# Current (broken):
repo.stage(new_file_name)

# Fix: use porcelain.add() instead
porcelain.add(repo, [new_file_name])
```

The `Repo.stage()` convenience method was removed in dulwich 1.x. The equivalent functionality is available through `porcelain.add()`.

**Affected test names (all from the `create_commit` fixture):**
- `test_fixtures`
- `test_get_most_recent_version_tag` (5 parameterizations)
- `test_get_commit_messages` (5 parameterizations)
- `test_cherry_pick_to_branch`
- `test_find_effective_version` (5 parameterizations)


### 2. `porcelain.status().untracked` now returns `bytes` instead of `str`

- **Error:** `TypeError: unsupported operand type(s) for /: 'PosixPath' and 'bytes'`
- **Tests affected:** 216 ERRORS (all as fixture setup failures)
- **Root location:** `tests/conftest.py:111`

```python
# Current (broken):
porcelain.add(repo, [(repo_root_dir / f).as_posix() for f in status_report.untracked])

# Fix: decode bytes to str before path operations
porcelain.add(repo, [(repo_root_dir / f.decode()).as_posix() for f in status_report.untracked])
```

In dulwich 1.x, `porcelain.status()` returns file paths as `bytes` objects in its `untracked` list, whereas 0.24.x returned `str`. The `/` operator on `PosixPath` does not accept `bytes` operands.

**This single fixture failure cascades to block ALL of the following test modules:**
- `tests/test_clairity_repo.py` (all parameterized tests)
- `tests/test_cli.py` (all parameterized tests)
- `tests/test_fda_flows.py` (all parameterized tests)
- `tests/test_git_utilities.py` (all parameterized tests)
- `tests/test_github_api.py` (all parameterized tests)
- `tests/test_project_config.py` (all parameterized tests)
- `tests/test_trunk_flow.py` (all parameterized tests)

---

## Potential Additional Issues (Not Yet Surfaced)

The following locations use dulwich APIs that may have changed behavior in 1.x, but they haven't been reached yet because the fixture failures above block the tests from progressing. These should be verified after the confirmed issues are fixed.

### 3. `Repo.path` return type change

In dulwich 1.x, `Repo.path` returns a `str` instead of `bytes`. This could affect code that previously called `.decode()` on it, or compared it against bytes values.

**Locations to check:**

| File | Line | Code | Concern |
|------|------|------|---------|
| `tests/conftest.py` | 251 | `porcelain.branch_create(repo.path, feature_name)` | `repo.path` type may change what `branch_create` receives |
| `tests/test_project_config.py` | 35 | `gotten_local_repo.path == fake_project_root_dir.as_posix()` | Equality comparison depends on `Repo.path` now being `str` (may now pass, or may include trailing slash / `.git` path) |
| `version_flow/clairity_repo.py` | 159 | `Path(self._repo.path) / relative_path` | If `Repo.path` was previously bytes, wrapping in `Path()` would have failed; if now str, this may now work correctly |
| `version_flow/git.py` | 192 | `repo.path` in error message f-string | Cosmetic; if previously bytes, the error message would have included `b'...'` prefix |

### 4. `porcelain.active_branch()` return type

In `version_flow/clairity_repo.py:80` and `version_flow/fda_flows.py:78`, the code calls:
```python
porcelain.active_branch(self._repo).decode()
```

If `active_branch()` now returns `str` in dulwich 1.x (consistent with the bytes-to-str migration), calling `.decode()` on a `str` will raise `AttributeError`. This needs verification.

### 5. `porcelain.tag_create()` parameter types

The `tag` and `message` parameters are passed as `bytes` in several locations:
- `tests/conftest.py:114-118` (fixture setup)
- `tests/conftest.py:165-170` (create_commit fixture)
- `version_flow/git.py:359-364` (do_version_bump_commit)

If dulwich 1.x now expects `str` for these parameters, these calls will need updating.

### 6. `porcelain.commit()` message parameter

Similarly, `porcelain.commit()` is called with `bytes` messages in:
- `tests/conftest.py:112`
- `tests/conftest.py:161`

And with `str` messages in:
- `version_flow/git.py:328-329`

If the API now uniformly expects `str`, the bytes-based calls will need updating.

### 7. `repo.refs` dictionary key/value types

Multiple locations iterate over `repo.refs.as_dict()`:
- `version_flow/git.py:208` — `commit_id_to_version_map()`
- `version_flow/git.py:401` — `get_commit_messages()`
- `version_flow/clairity_repo.py:96` — `get_most_recent_version_tag()`

If the ref keys/values changed from `bytes` to `str`, the `.decode()` calls on them would fail, and bytes comparisons would break.

---

## Recommended Fix Order

1. **Fix `conftest.py:111`** (decode `status.untracked` items) -- unblocks 216 tests
2. **Fix `conftest.py:159`** (replace `repo.stage()` with `porcelain.add()`) -- unblocks 17 tests
3. **Re-run tests** to discover which of the "potential" issues in sections 3-7 actually surface
4. **Fix any newly surfaced issues** and iterate until green

This incremental approach is recommended because the dulwich 0.24-to-1.x migration involved a broad shift from bytes to str across many APIs, and it's difficult to predict every breakage without running the code. Fixing the two known blockers and iterating is the most efficient path.
