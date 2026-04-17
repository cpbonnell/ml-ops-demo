from contextlib import nullcontext as DoesNotRaise
from pathlib import Path

import pytest
from dulwich import porcelain

from tests.conftest import DEFAULT_VERSION_FLOW_CONFIG, DepTool, build_fake_project
from version_flow.clairity_repo import FunctionalBranch, ClairityRepo
from version_flow.project_config import ProjectConfig
from version_flow.project_version import ProjectVersion
from version_flow.trunk_flow import check_current_version_state
from version_flow.trunk_flow import trunk_flow
from version_flow.types import VersionSpec, GitBranchStrategy, BumpPriority


@pytest.mark.parametrize(
    "functional_branch",
    [
        FunctionalBranch.trunk,
        pytest.param(
            FunctionalBranch.release,
            marks=pytest.mark.xfail(reason="Fixtures for release branch not yet implemented."),
        ),
    ],
)
def test_trunk_flow(fake_project_root_dir, functional_branch, most_recent_version_tag, caplog):

    config_file_location = fake_project_root_dir.as_posix()
    config = ProjectConfig(config_file_location)
    clairity_repo = ClairityRepo(config)
    if config.git_branch_strategy != GitBranchStrategy.trunk_flow:
        pytest.skip("Legacy Trunk Flow does not need to test this.")

    starting_version = ProjectVersion.from_string(most_recent_version_tag, VersionSpec.semver)
    ending_version = starting_version.bump(BumpPriority.rc)
    assert config.version_string == starting_version.to_string()

    with caplog.at_level("DEBUG"):
        trunk_flow(config, clairity_repo, functional_branch)

    assert f"from version {starting_version.to_string()}" in caplog.text
    assert f"to version {ending_version.to_string()}" in caplog.text
    assert config.version_string == ending_version.to_string()


@pytest.mark.parametrize("version_spec", [VersionSpec.semver, VersionSpec.pyver])
@pytest.mark.parametrize(
    "config_version_string, tagged_version_string, functional_branch, exception_context",
    [
        ("v0.1.0", "v0.1.0", FunctionalBranch.release, DoesNotRaise()),
        ("v0.1.0", "v0.1.0", FunctionalBranch.trunk, DoesNotRaise()),
        ("v0.1.0", "v0.1.0-rc2", FunctionalBranch.release, DoesNotRaise()),
        (
            "v0.1.0",
            "v0.1.0-rc2",
            FunctionalBranch.trunk,
            pytest.raises(ValueError, match="does not match the most recent tagged"),
        ),
        ("v3.11.12rc0", "v2.4.1", FunctionalBranch.release, DoesNotRaise()),
    ],
)
def test_check_current_version_state(
    version_spec, config_version_string, tagged_version_string, functional_branch, exception_context
):

    with exception_context:
        check_current_version_state(
            version_spec=version_spec,
            config_version_string=config_version_string,
            tagged_version_string=tagged_version_string,
            functional_branch=functional_branch,
        )


@pytest.fixture()
def fake_monorepo(repo_root_dir, repo, create_commit_at_path) -> Path:
    config_a = {
        **DEFAULT_VERSION_FLOW_CONFIG,
        "project_name_in_tag": "svc-a",
        "owned_paths": ["svc-a"],
    }
    config_b = {
        **DEFAULT_VERSION_FLOW_CONFIG,
        "project_name_in_tag": "svc-b",
        "owned_paths": ["svc-b"],
    }
    build_fake_project(repo_root_dir / "svc-a", DepTool.poetry_2x, config_a)
    build_fake_project(repo_root_dir / "svc-b", DepTool.uv, config_b)
    porcelain.add(repo)
    head = porcelain.commit(repo, message=b"Initial commit with project infrastructure.")

    version_tag = "v1.2.3-rc.4"
    for prefix in ("svc-a", "svc-b"):
        porcelain.tag_create(
            repo,
            annotated=True,
            tag=f"{prefix}/{version_tag}".encode(),
            message=f"release: {prefix}/{version_tag}".encode(),
            objectish=head,
        )

    create_commit_at_path("svc-a/new_feature.py", "feat: add feature to svc-a")
    create_commit_at_path("svc-b/bugfix.py", "fix: patch svc-b")

    return repo_root_dir


def test_monorepo_trunk_flow(fake_monorepo, repo, caplog):
    """Trunk flow for one sub-project only considers its own tags and commits."""
    version_tag = "v1.2.3-rc.4"
    starting_version = ProjectVersion.from_string(version_tag, VersionSpec.semver)

    config_a = ProjectConfig(fake_monorepo / "svc-a")
    clairity_repo_a = ClairityRepo(config_a)

    with caplog.at_level("DEBUG"):
        trunk_flow(config_a, clairity_repo_a, FunctionalBranch.trunk)

    # svc-a should have bumped
    assert config_a.version_string != starting_version.to_string()
    new_version_a = config_a.version_string

    # Verify that svc-a's tag was created with prefix
    tags = repo.refs.as_dict(b"refs/tags/")
    assert f"svc-a/{new_version_a}".encode() in tags

    # svc-b should be untouched
    config_b = ProjectConfig(fake_monorepo / "svc-b")
    assert config_b.version_string == version_tag

    # Only the svc-a feat commit should have been parsed (not the svc-b fix commit)
    assert "1 commit messages" in caplog.text
