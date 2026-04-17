# version-flow

A tool for automated semantic versioning based on commit messages. Supports
projects managed by Poetry 1.x, Poetry 2.x, and UV. Monorepo support (
independent versioning per sub-project) is in active development.

## Running tests

```bash
poetry run pytest          # run locally
```

## Writing tests: the fake project builder

Tests that need a project on disk should use `fake_project_builder` or
`build_fake_project` from `tests/conftest.py`. **Do not** create new template
directories under `tests/data/`.

- `tests/data/fake_projects/` contains 3 base templates (poetry1.x, poetry2.x,
  uv) with only dependency-tool metadata — no `[tool.version-flow]` section.
- The builder copies a template and injects whatever version-flow config you
  pass.

### Single-project tests

Use the `fake_project_builder` fixture. It builds the project, commits, and tags
in one call:

```python
def test_something(fake_project_builder):
    project_dir = fake_project_builder(
        DepTool.uv)  # uses DEFAULT_VERSION_FLOW_CONFIG

    # Or with custom config:
    config = {**DEFAULT_VERSION_FLOW_CONFIG, "project_name_in_tag": "my-lib"}
    project_dir = fake_project_builder(DepTool.poetry_2x,
                                       version_flow_config=config)
```

### Monorepo tests (multiple sub-projects in one repo)

Use `build_fake_project()` directly in a fixture so you control the commit
timing:

```python
@pytest.fixture()
def fake_monorepo(repo_root_dir, repo) -> Path:
    config_a = {**DEFAULT_VERSION_FLOW_CONFIG, "project_name_in_tag": "svc-a",
                "owned_paths": ["svc-a"]}
    config_b = {**DEFAULT_VERSION_FLOW_CONFIG, "project_name_in_tag": "svc-b",
                "owned_paths": ["svc-b"]}

    build_fake_project(repo_root_dir / "svc-a", DepTool.poetry_2x, config_a)
    build_fake_project(repo_root_dir / "svc-b", DepTool.uv, config_b)

    porcelain.add(repo)
    porcelain.commit(
      repo,
      message=b"Initial commit with project infrastructure."
    )
    return repo_root_dir


def test_monorepo_versioning(fake_monorepo):
    conf_a = ProjectConfig(fake_monorepo / "svc-a")
    conf_b = ProjectConfig(fake_monorepo / "svc-b")
    assert conf_a.project_name_in_tag == "svc-a"
    assert conf_b.repository_root == fake_monorepo
```

### Existing parametrized tests

`fake_project_root_dir` runs every test against all 6 combinations (3 dep tools
x 2 strategies). Use it when a test should validate behavior across all project
types.
