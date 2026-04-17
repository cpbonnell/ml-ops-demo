from contextlib import nullcontext as DoesNotRaise
from pathlib import Path
from unittest.mock import patch

import pytest
from dulwich import porcelain

from tests.conftest import DEFAULT_VERSION_FLOW_CONFIG, DepTool, build_fake_project
from version_flow.fda_flows import check_triggering_event, InvalidTriggerException, fda_git_flow
from version_flow.project_config import ProjectConfig
from version_flow.types import BranchFunctionalRole as Role, BumpPriority
from version_flow.types import GitBranchStrategy as Strategy
from version_flow.types import VersionSpec
from version_flow.version import Version, DEFAULT_MINIMUM_VERSION

RAISES_BAD_MERGE = pytest.raises(
    InvalidTriggerException, match="Merges of a branch role .* Version flow will not proceed"
)


@pytest.mark.parametrize(
    "strategy, branch_a, branch_b, context",
    [
        (Strategy.fda_git_flow, Role.trunk, Role.release, RAISES_BAD_MERGE),
        (Strategy.fda_git_flow, Role.release_candidate, Role.trunk, RAISES_BAD_MERGE),
        (Strategy.fda_git_flow, Role.release_candidate, Role.release, RAISES_BAD_MERGE),
        (Strategy.fda_git_flow, Role.release, Role.trunk, RAISES_BAD_MERGE),
        (Strategy.fda_git_flow, Role.trunk, None, DoesNotRaise()),
        (Strategy.fda_git_flow, Role.release_candidate, Role.feature, DoesNotRaise()),
        (Strategy.fda_git_flow, Role.release, Role.release_candidate, DoesNotRaise()),
        (Strategy.fda_trunk_flow, Role.trunk, Role.release, RAISES_BAD_MERGE),
        (Strategy.fda_trunk_flow, Role.trunk, None, DoesNotRaise()),
        (Strategy.fda_trunk_flow, Role.release, Role.trunk, DoesNotRaise()),
        (Strategy.fda_trunk_flow, Role.release, Role.feature, DoesNotRaise()),
    ],
)
def test_check_triggering_event(strategy: Strategy, branch_a: Role, branch_b: Role, context):
    with context:
        check_triggering_event(strategy, branch_a, branch_b)


def test_fda_flow(
    gh, repo, fake_project_root_dir, most_recent_version_tag, fake_gh_repo_full_name, fake_gh_token_env, caplog
):

    config = ProjectConfig(fake_project_root_dir.as_posix())
    if config.git_branch_strategy != Strategy.fda_git_flow:
        pytest.skip("Legacy FDA Flow does not need to test this.")

    starting_version = Version.from_string(most_recent_version_tag, default_output_spec=VersionSpec.semver)
    ending_version = starting_version.bump(BumpPriority.minor, "dev")
    assert config.version_string == starting_version.to_string()

    with caplog.at_level("DEBUG"):
        fda_git_flow(config)

    assert f"from version {starting_version.to_string()}" in caplog.text
    assert f"to version {ending_version.to_string()}" in caplog.text
    assert config.version_string == ending_version.to_string()


@pytest.fixture()
def fake_fda_monorepo(repo_root_dir, repo, create_commit_at_path, most_recent_version_tag) -> Path:
    fda_base = {
        **DEFAULT_VERSION_FLOW_CONFIG,
        "git_branch_strategy": "fda_git_flow",
        "trunk_branch": "main",
    }
    config_a = {**fda_base, "project_name_in_tag": "svc-a", "owned_paths": ["svc-a"]}
    config_b = {**fda_base, "project_name_in_tag": "svc-b", "owned_paths": ["svc-b"]}

    build_fake_project(repo_root_dir / "svc-a", DepTool.poetry_2x, config_a)
    build_fake_project(repo_root_dir / "svc-b", DepTool.uv, config_b)
    porcelain.add(repo)
    porcelain.commit(repo, message=b"Initial commit with project infrastructure.")

    # Add a breaking-change commit *before* the version tags. If get_commit_messages
    # fails to stop at the tag (the bug this test guards against), this commit leaks
    # into the message list and escalates the bump from minor to major.
    create_commit_at_path("svc-a/legacy.py", "feat!: pre-tag breaking change")
    head = repo.head()

    for prefix in ("svc-a", "svc-b"):
        porcelain.tag_create(
            repo,
            annotated=True,
            tag=f"{prefix}/{most_recent_version_tag}".encode(),
            message=f"release: {prefix}/{most_recent_version_tag}".encode(),
            objectish=head,
        )

    create_commit_at_path("svc-a/new_feature.py", "feat: add feature to svc-a")
    create_commit_at_path("svc-b/bugfix.py", "fix: patch svc-b")

    return repo_root_dir


@patch("version_flow.project_config.ProjectConfig.get_remote_repo")
def test_monorepo_fda_flow(mock_remote, fake_fda_monorepo, repo, most_recent_version_tag, caplog):
    """FDA flow for one sub-project only considers its own tags and commits."""
    starting_version = Version.from_string(most_recent_version_tag, default_output_spec=VersionSpec.semver)
    ending_version = starting_version.bump(BumpPriority.minor, "dev")

    config_a = ProjectConfig(fake_fda_monorepo / "svc-a")

    with caplog.at_level("DEBUG"):
        fda_git_flow(config_a)

    assert config_a.version_string == ending_version.to_string()

    tags = repo.refs.as_dict(b"refs/tags/")
    assert f"svc-a/{ending_version.to_string()}".encode() in tags

    config_b = ProjectConfig(fake_fda_monorepo / "svc-b")
    assert config_b.version_string == most_recent_version_tag
