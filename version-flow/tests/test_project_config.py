from pathlib import Path

import pytest
from dulwich.repo import Repo
from github.Repository import Repository as GHRepo

from conftest import DepTool, DEFAULT_VERSION_FLOW_CONFIG
from version_flow.project_config import ProjectConfig
from version_flow.project_version import ProjectVersion
from version_flow.types import VersionSpec, BumpPriority, GitBranchStrategy


def test_project_config(
    gh, repo, fake_project_root_dir, most_recent_version_tag, fake_gh_repo_full_name, fake_gh_token_env
):

    # Test the getter methods
    conf = ProjectConfig(fake_project_root_dir)
    assert (
        conf.git_branch_strategy == GitBranchStrategy.fda_git_flow
        if "fda" in fake_project_root_dir.as_posix()
        else GitBranchStrategy.trunk_flow
    )
    assert conf.version_spec == VersionSpec.semver
    assert conf.version_string == most_recent_version_tag
    assert conf.trunk_branch == "x_main"
    assert conf.release_branch == "x_release"
    assert conf.repository_root == fake_project_root_dir
    assert conf.release_candidates == {"rc": "x_rc/.*"}
    assert conf.named_releases == {"prod": "x_prod"}
    assert conf.project_name_in_tag is None
    assert conf.owned_paths == []
    assert conf.remote_repository_name == fake_gh_repo_full_name
    assert conf.github_token == fake_gh_token_env

    # Test the local repo object
    gotten_local_repo = conf.get_repo()
    assert isinstance(gotten_local_repo, Repo)
    assert gotten_local_repo.path == fake_project_root_dir.as_posix()

    # Test the remote repo object
    gotten_remote_repo = conf.get_remote_repo()
    assert isinstance(gotten_remote_repo, GHRepo)
    assert gotten_remote_repo.full_name == fake_gh_repo_full_name

    # Test the setter methods
    new_version = ProjectVersion.from_string(most_recent_version_tag, conf.version_spec).bump(BumpPriority.patch)
    changed_files = conf.set_new_version(new_version)
    assert conf.project_config_path.as_posix() in changed_files
    assert conf.version_string == new_version.to_string()
    assert len(conf.files_to_update) == 1
    for file in conf.files_to_update:
        assert new_version.to_string() in file.read_text()
        assert file.as_posix() in changed_files


@pytest.fixture
def alternate_config_file_path(fake_project_root_dir) -> Path:
    # Move the config file into a subdirectory
    config_file = fake_project_root_dir / "pyproject.toml"
    (fake_project_root_dir / "sub").mkdir(parents=True, exist_ok=True)
    config_file = config_file.rename(fake_project_root_dir / "sub" / "pyproject.toml")

    return config_file


def test_project_config_not_in_repo_root(fake_project_root_dir, alternate_config_file_path):
    config = ProjectConfig(alternate_config_file_path)
    assert config.repository_root != config.project_root
    assert config.repository_root == fake_project_root_dir
    assert config.project_config_path == alternate_config_file_path

class TestMonorepoConfig:
    """Tests for monorepo config options: project_name_in_tag and owned_paths."""

    @pytest.mark.parametrize("config_value, expected_value", [
        ("my-lib", "my-lib"),
        ("", None),
    ])
    def test_project_name_in_tag_present(self, fake_project_builder, config_value, expected_value):
        project_dir = fake_project_builder(
            DepTool.poetry_2x,
            version_flow_config={**DEFAULT_VERSION_FLOW_CONFIG, "project_name_in_tag": config_value},
        )
        conf = ProjectConfig(project_dir)
        assert conf.project_name_in_tag == expected_value


    def test_owned_paths_present(self, fake_project_builder):
        project_dir = fake_project_builder(
            DepTool.uv,
            version_flow_config={**DEFAULT_VERSION_FLOW_CONFIG, "owned_paths": ["services/api", "libs/common"]},
        )
        conf = ProjectConfig(project_dir)
        assert conf.owned_paths == [project_dir / "services/api", project_dir / "libs/common"]


