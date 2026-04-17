# Ticket 2: Prefixed tag creation

**Size: S**
**Depends on:** Ticket 1

## Summary

When `project_name_in_tag` is configured, modify tag creation so the git tag
becomes `{prefix}/v1.2.3-rc.0` instead of `v1.2.3-rc.0`. The `Version` class
remains untouched — prefixing is strictly a git-layer concern.

## Implementation

Modify `do_version_bump_commit()` in `version_flow/git.py` (lines 358-378):

1. Accept the project prefix (passed from config) as an optional parameter.
2. When prefix is set, construct the tag string as
   `f"{prefix}/{new_version.to_string()}"` instead of `new_version.to_string()`.
3. The tag annotation message should also include the prefix for clarity (e.g.,
   `f"release: {prefix}/{new_version.to_string()}"`).
4. The tag ref string (`refs/tags/...`) must use the prefixed form.
5. When prefix is `None`, behavior is identical to today.

The `Version` class (`version_flow/version.py`) is NOT modified. The prefix is
applied only at the point of tag creation and tag ref construction.

## Testing

- Tag created with prefix: verify tag name is `my-project/v1.2.3-rc.0`
- Tag created without prefix (regression): verify tag name is `v1.2.3-rc.0`
- Tag ref string is correct in both cases
- Tag annotation message includes prefix when set

## Key files

- `version_flow/git.py` — `do_version_bump_commit()` (lines 319-382)
- Tests for git operations
