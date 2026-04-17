import os
from contextlib import nullcontext as no_error
from pathlib import Path

import pytest
from dulwich import porcelain
from dulwich.objects import Commit

from tests.conftest import DEFAULT_VERSION_FLOW_CONFIG, DepTool, build_fake_project
from version_flow.clairity_repo import ClairityRepo
from version_flow.git import get_filenames_from_commit
from version_flow.project_config import ProjectConfig as Config
from version_flow.project_version import ProjectVersion
from version_flow.types import BumpPriority, CommitType, FunctionalBranch


def test_fixtures(repo, most_recent_version_tag, most_recent_version_ref, create_git_history):
    # Just some quick tests to make sure the fixtures are working as I expect them to

    message_ids = create_git_history(
        pre=[CommitType.test],
        post=[CommitType.feat],
    )
    tagged_message_id = message_ids[1]

    walker = repo.get_walker()
    repo_messages = []
    for entry in walker:
        message = entry.commit.message.decode()
        repo_messages.append(message)

    assert len(repo_messages) == 3
    assert repo_messages[0].startswith("feat:")
    assert repo_messages[1].startswith("ci:")
    assert repo_messages[2].startswith("test:")
    assert tagged_message_id is not None
    assert repo[most_recent_version_ref].id is not None


def test_fake_project_root_dir(repo, fake_project_root_dir):

    # Check that the commit message is as expected
    head_commit = repo[b"HEAD"]
    assert isinstance(head_commit, Commit)
    assert "project infrastructure" in head_commit.message.decode()

    # Walk the Head commit's tree, make sure the expected files exist
    paths_seen = get_filenames_from_commit(repo, repo[b"HEAD"])
    assert {p.as_posix() for p in paths_seen} == {"pyproject.toml", "workbench/__init__.py"}


GIT_HISTORY_PARAMETERS = [
    ([], []),
    ([CommitType.test], []),
    ([], [CommitType.feat]),
    ([CommitType.test], [CommitType.feat]),
    ([t for t in CommitType], [t for t in CommitType]),
]


@pytest.mark.parametrize("pre, post", GIT_HISTORY_PARAMETERS)
def test_get_most_recent_version_tag(pre, post, create_git_history, fake_project_builder, most_recent_version_tag):

    project_dir = fake_project_builder(DepTool.uv)
    create_git_history(pre, post)
    clairity_repo = ClairityRepo(project_dir)
    assert clairity_repo.get_most_recent_version_tag() == most_recent_version_tag


@pytest.mark.parametrize("pre, post", GIT_HISTORY_PARAMETERS)
def test_get_commit_messages(pre, post, create_git_history, fake_project_builder, most_recent_version_tag):

    project_dir = fake_project_builder(DepTool.uv)
    create_git_history(pre, post)
    clairity_repo = ClairityRepo(project_dir)
    messages = clairity_repo.get_commit_messages(since_tag=most_recent_version_tag)

    assert len(messages) == len(post)
    for message, message_type in zip(messages, reversed(post)):
        assert message.startswith(message_type.name)


@pytest.mark.parametrize("pre, post", GIT_HISTORY_PARAMETERS)
def test_do_version_bump_commit(pre, post, repo, create_git_history, fake_project_root_dir):
    create_git_history(pre, post)

    # Determine a new version, edit the version files, and do the version commit
    config = Config(fake_project_root_dir)
    old_version = ProjectVersion.from_string(config.version_string, config.version_spec)

    new_version = old_version.bump(BumpPriority.rc)
    config.set_new_version(new_version)

    clairity_repo = ClairityRepo(config)
    new_commit_id = clairity_repo.do_version_bump_commit(new_version, dry_run=True)

    # Ensure the changes were committed
    status_report = porcelain.status(repo)
    assert len(status_report.staged["add"]) == 0
    assert len(status_report.staged["modify"]) == 0
    assert len(status_report.staged["delete"]) == 0
    assert len(status_report.unstaged) == 0
    assert len(status_report.untracked) == 0

    # Ensure the commit and tag are correct
    assert new_commit_id == repo[b"HEAD"].id
    assert clairity_repo.get_most_recent_version_tag() == new_version.to_string()
    assert new_version.to_string() in repo[b"HEAD"].message.decode()


def test_do_version_bump_commit_with_prefix(repo, fake_project_builder, create_git_history):
    config_dict = {**DEFAULT_VERSION_FLOW_CONFIG, "project_name_in_tag": "my-lib"}
    project_dir = fake_project_builder(DepTool.uv, version_flow_config=config_dict)

    create_git_history(pre=[], post=[])

    config = Config(project_dir)
    old_version = ProjectVersion.from_string(config.version_string, config.version_spec)
    new_version = old_version.bump(BumpPriority.rc)
    config.set_new_version(new_version)

    clairity_repo = ClairityRepo(config)
    new_commit_id = clairity_repo.do_version_bump_commit(new_version, dry_run=True)

    # Verify the tag was created with the prefix
    tags = repo.refs.as_dict(b"refs/tags/")
    expected_tag = f"my-lib/{new_version.to_string()}"
    assert bytes(expected_tag, encoding="utf-8") in tags

    # Verify the commit is correct
    assert new_commit_id == repo[b"HEAD"].id
    assert new_version.to_string() in repo[b"HEAD"].message.decode()


@pytest.mark.parametrize(
    "branch_name, expected_functional_branch, context_manager",
    [
        ("x_main", FunctionalBranch.trunk, no_error()),
        ("staging", FunctionalBranch.staging, pytest.raises(NotImplementedError)),
        ("x_release", FunctionalBranch.release, no_error()),
        ("ps-9999-solve-world-hunger", FunctionalBranch.other, no_error()),
    ],
)
def test_get_functional_versions(branch_name, expected_functional_branch, context_manager, repo, fake_project_root_dir):
    if branch_name not in [branch.decode() for branch in porcelain.branch_list(repo)]:
        porcelain.branch_create(repo, branch_name)

    porcelain.checkout(repo, branch_name)
    clairity_repo = ClairityRepo(fake_project_root_dir)

    with context_manager:
        assert clairity_repo.get_functional_branch() == expected_functional_branch


def test_cherry_pick_to_branch(repo, repo_root_dir, create_commit, create_git_history):
    clairity_repo = ClairityRepo(repo_root_dir)

    # Create a Git history for branch main, and then create a new branch release
    main_history = [CommitType.feat, CommitType.fix]
    create_git_history(main_history, [])
    porcelain.branch_create(repo, "release")

    # Create a new commit on branch release, and snapshot the state of both branches before the cherry-pick
    porcelain.checkout(repo, "release")
    target_commit_id = create_commit(CommitType.test)
    release_files_pre_cp = os.listdir(repo_root_dir)
    porcelain.checkout(repo, "main")
    main_files_pre_cp = os.listdir(repo_root_dir)

    # Make sure we start on the release branch, then do the cherry-pick
    porcelain.checkout(repo, "release")
    clairity_repo.change_branch_and_cherry_pick("main", target_commit_id)

    # Ensure that cherry-pick checked out the new branch
    assert porcelain.active_branch(repo) == b"main"
    main_files_post_cp = os.listdir(repo_root_dir)

    # Make sure the file got cherry-picked correctly, and the messages align
    main_head_commit: Commit = repo[b"refs/heads/main"]
    release_head_commit: Commit = repo[b"refs/heads/release"]
    assert main_head_commit.message == release_head_commit.message
    assert set(main_files_pre_cp) != set(release_files_pre_cp)
    assert set(main_files_post_cp) == set(release_files_pre_cp)


# indirect_equals for "indirect parameterization"
@pytest.mark.parametrize(
    "github_branches, expected_result",
    [
        ([], False),
        ([""], False),
        (["main"], False),
        (["x_release", "main"], True),
        (["x_release", "main", "ps-9999-solve-world-hunger"], True),
    ],
    indirect=["github_branches"],
)
def test_release_branch_exists(repo, repo_root_dir, fake_project_root_dir, github_branches, expected_result):
    clairity_repo = ClairityRepo(repo_root_dir)

    assert clairity_repo.release_branch_exists(github_branches) == expected_result


@pytest.mark.parametrize(
    "github_pull_requests, expected_result",
    [
        # Tuples are (head, base) or (head, base, title)
        ([], False),
        ([("x_main", "x_release", "Next Release")], True),
        ([("x_main", "x_release", "Next Release"), ("x_main", "x_release", "Next Release")], True),
        ([("x_main", "x_release", "Next Release"), ("ps-101-solve-world-hunger", "x_release")], True),
        ([("x_main", "x_release", "Next Release"), ("ps-101-solve-world-hunger", "x_main")], True),
        ([("ps-101-solve-world-hunger", "x_main"), ("ps-102-cure-cancer", "x_main")], False),
        # Branch match but wrong title — not a match for this project
        ([("x_main", "x_release", "Release: other-project")], False),
    ],
    indirect=["github_pull_requests"],
)
def test_next_release_pr_exists(repo, repo_root_dir, fake_project_root_dir, github_pull_requests, expected_result):
    clairity_repo = ClairityRepo(repo_root_dir)

    assert clairity_repo.next_release_pr_exists(github_pull_requests) == expected_result


class TestReleasePrScopingPerSubProject:

    @pytest.fixture()
    def monorepo(self, repo_root_dir, repo) -> Path:
        config_a = {**DEFAULT_VERSION_FLOW_CONFIG, "project_name_in_tag": "svc-a", "owned_paths": ["svc-a"]}
        config_b = {**DEFAULT_VERSION_FLOW_CONFIG, "project_name_in_tag": "svc-b", "owned_paths": ["svc-b"]}

        build_fake_project(repo_root_dir / "svc-a", DepTool.poetry_2x, config_a)
        build_fake_project(repo_root_dir / "svc-b", DepTool.uv, config_b)

        porcelain.add(repo)
        porcelain.commit(repo, message=b"Initial commit with project infrastructure.")
        return repo_root_dir

    def test_release_pr_title_includes_project_name(self, monorepo):
        clairity_repo = ClairityRepo(monorepo / "svc-a")
        assert clairity_repo._release_pr_title() == "Release: svc-a"

    def test_existing_pr_for_project_a_does_not_block_project_b(self, monorepo, gh_pull_request_factory):
        pr_for_a = gh_pull_request_factory("x_main", "x_release", title="Release: svc-a")

        repo_b = ClairityRepo(monorepo / "svc-b")
        assert repo_b.next_release_pr_exists([pr_for_a]) is False

    def test_existing_pr_for_project_a_blocks_duplicate_for_project_a(self, monorepo, gh_pull_request_factory):
        pr_for_a = gh_pull_request_factory("x_main", "x_release", title="Release: svc-a")

        repo_a = ClairityRepo(monorepo / "svc-a")
        assert repo_a.next_release_pr_exists([pr_for_a]) is True

    def test_both_projects_can_have_release_prs(self, monorepo, gh_pull_request_factory):
        pr_for_a = gh_pull_request_factory("x_main", "x_release", title="Release: svc-a")
        pr_for_b = gh_pull_request_factory("x_main", "x_release", title="Release: svc-b")

        repo_a = ClairityRepo(monorepo / "svc-a")
        repo_b = ClairityRepo(monorepo / "svc-b")

        assert repo_a.next_release_pr_exists([pr_for_a, pr_for_b]) is True
        assert repo_b.next_release_pr_exists([pr_for_a, pr_for_b]) is True
