# Ticket 8: Documentation

**Size: M**
**Depends on:** All previous tickets

## Summary

Update the README with a comprehensive monorepo setup guide covering all new
features.

## Sections to add/update

### New section: Monorepo Support

#### Overview

Explain that version-flow supports monorepos where each sub-project has its own
`pyproject.toml` and can be versioned independently.

#### Configuration guide

Walk through a complete example `pyproject.toml` for a monorepo sub-project:

```toml
[project]
version = "1.0.0-rc.3"

[tool.version-flow]
version_specification = "semver"
git_branch_strategy = "fda_git_flow"
project_name_in_tag = "my-data-pipeline"
owned_paths = ["services/my-data-pipeline", "shared/common-lib"]
files_to_update = ["services/my-data-pipeline/src/__init__.py"]

[tool.version-flow.managed-branches]
trunk = "main"
release = "release"
```

Explain each monorepo-specific option:

- `project_name_in_tag`: What it does, how it affects tag format (
  `my-data-pipeline/v1.0.0-rc.3`), when to use it
- `owned_paths`: What it does, how it filters commits, how to choose what paths
  to include (your code + shared code you depend on)

#### CI setup guidance

Document that tag-triggered CI pipelines need their tag filter regex updated to
match the prefixed format. Provide example for CircleCI:

```yaml
tags:
  only: /^my-data-pipeline\/v(\d+\.){2}\d+(|-?\w+\.?\d+)$/
```

#### Running version-flow for a sub-project

```bash
version-flow ./services/my-data-pipeline
```

#### Gotchas / FAQ

- Version string replacement (`files_to_update`) does a naive string replace —
  keep listed files scoped to your sub-project
- If `owned_paths` is not configured, all commits in the repo influence bump
  priority
- Each sub-project should have a unique `project_name_in_tag` value
- Tag format uses `/` as separator, which is compatible with standard git
  tooling

### Existing sections

Review existing README sections to ensure they don't contradict or need caveats
for monorepo usage.

## Key files

- `README.md`
