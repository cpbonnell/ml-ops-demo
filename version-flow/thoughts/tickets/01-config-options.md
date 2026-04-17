# Ticket 1: New config options (`project_name_in_tag`, `owned_paths`)

**Size: S**
**Depends on:** None

## Summary

Add two new optional config properties to `ProjectConfig` that will be used by
later tickets to enable monorepo support. This ticket adds only the config
parsing — no behavioral changes.

## Config keys

Both live under `[tool.version-flow]` in `pyproject.toml`:

```toml
[tool.version-flow]
project_name_in_tag = "my-data-pipeline"
owned_paths = ["services/my-data-pipeline", "shared/common-lib"]
```

## Implementation

Add two new properties to `ProjectConfig` (`version_flow/project_config.py`):

- `project_name_in_tag -> str | None`: Returns the string value if present,
  `None` if absent. This will later be used as a prefix on git tags (e.g.,
  `my-data-pipeline/v1.2.3-rc.0`).
- `owned_paths -> list[Path]`: Returns paths resolved relative to
  `project_root` (same pattern as `files_to_update` on line 128-130). Returns
  empty list if absent.

Both must be fully backward compatible — absent config means no change in
behavior.

## Testing

Unit tests in `test_project_config.py`:

- Parse `project_name_in_tag` when present, verify string value
- Parse `project_name_in_tag` when absent, verify `None`
- Parse `owned_paths` when present, verify paths resolved relative to project
  root
- Parse `owned_paths` when absent, verify empty list
- Edge case: `project_name_in_tag` is empty string — decide behavior (probably
  treat as `None`)

## Key files

- `version_flow/project_config.py`
- `tests/test_project_config.py`
