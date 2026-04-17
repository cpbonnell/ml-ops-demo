import pytest
from dulwich import porcelain
from dulwich.objects import Commit

from version_flow import git
from version_flow.project_config import ProjectConfig
from version_flow.project_version import ProjectVersion, VersionSpec
from version_flow.types import CommitType, BumpPriority, BranchFunctionalRole


@pytest.fixture(autouse=True)
def clear_version_map_cache():
    """Clear the cache to get rid of stale values.

    This helps avoid memory bloat from computed dictionaries that are no longer needed.
    """
    yield
    git.commit_id_to_version_map.cache_clear()


def test_create_merge_commit(
    repo,
    fake_project_root_dir,
    create_git_history,
    default_fake_user_name,
    default_fake_user_email,
    default_fake_feature_branch_name,
):
    original_branch = porcelain.active_branch(repo)
    history = create_git_history(
        pre=[CommitType.feat, CommitType.fix, CommitType.chore, CommitType.docs, CommitType.test],
        post=[],
        feature=[CommitType.feat, CommitType.fix],
        merge_feature=False,
    )

    result = git.create_merge_commit(
        repo=repo,
        feature_branch_name=default_fake_feature_branch_name,
        commit_user=f"{default_fake_user_name} <{default_fake_user_email}>",
    )

    assert porcelain.active_branch(repo) == original_branch

    # Ensure the head is at the correct commit
    master_commit = repo[repo.refs[b"refs/heads/main"]]
    assert result == master_commit.id

    # Ensure all expected commits appear in the history of the branch
    not_seen = set(history)
    seen = set()
    unexpected = set()
    initial_commit_seen = False
    merge_commit_seen = False

    for entry in repo.get_walker(include=[repo.refs[b"refs/heads/main"]]):
        match entry.commit:
            case Commit(message=m) if "initial" in m.decode().lower():
                initial_commit_seen = True
            case Commit(id=i) if i == master_commit.id:
                merge_commit_seen = True
            case Commit(id=i) if i in not_seen:
                not_seen.remove(i)
                seen.add(i)
            case Commit(id=i):
                unexpected.add(i)
            case _:
                pass

    assert merge_commit_seen  # Check for the merge commit
    assert initial_commit_seen  # Check for the initial commit
    assert len(not_seen) == 0  # No expected commits have been missed
    assert len(seen) == len(history)  # All expected commits should have been observed
    assert len(unexpected) == 0


def test_dereference_tag(repo, fake_project_root_dir):

    # Test a correct case. There is only the initial commit, so the object pointed by the
    # HEAD (a Commit), the main branch (a Commit), and the initial tag (a Tag) should all
    # ultimately give us the same commit object.
    id_a = repo.refs[b"HEAD"]
    id_b = repo.refs[b"refs/heads/main"]
    id_c = repo.refs[b"refs/tags/initial"]

    pointed_a = git.dereference_tag(repo, id_a)
    pointed_b = git.dereference_tag(repo, id_b)
    pointed_c = git.dereference_tag(repo, id_c)

    assert pointed_a == pointed_b
    assert pointed_b == pointed_c

    # Test that we raise the desired error
    with pytest.raises(KeyError, match="Cannot dereference"):
        git.dereference_tag(repo, b"a" * 40)


@pytest.mark.parametrize(
    "pre, post, feature, merge_feature, include_version_tag, diverging_commit_on_main",
    [
        pytest.param([CommitType.feat], [], [], False, False, None, id="no_version_tag"),
        pytest.param([CommitType.feat], [], [], False, True, None, id="linear history, default version tag"),
        pytest.param(
            [CommitType.feat], [CommitType.feat], [], False, True, BumpPriority.minor, id="linear history, alt version"
        ),
        pytest.param(
            [], [CommitType.feat], [CommitType.feat], False, True, BumpPriority.minor, id="feat branch, not merged"
        ),
        pytest.param(
            [], [CommitType.feat], [CommitType.feat], True, True, BumpPriority.minor, id="feat branch, merge commit"
        ),
    ],
)
def test_find_effective_version(
    repo,
    create_commit,
    create_git_history,
    most_recent_version_tag,
    pre,
    post,
    feature,
    merge_feature,
    include_version_tag,
    diverging_commit_on_main: BumpPriority | None,
):
    history = create_git_history(
        pre=pre,
        post=post,
        feature=feature,
        merge_feature=merge_feature,
        include_version_tag=include_version_tag,
    )

    if include_version_tag:
        current_version = ProjectVersion.from_string(most_recent_version_tag, VersionSpec.semver)
    else:
        current_version = ProjectVersion.from_string(ProjectVersion.DEFAULT_MINIMUM_VERSION, VersionSpec.semver)

    if diverging_commit_on_main:
        new_version = current_version.bump(diverging_commit_on_main)
        history.append(create_commit(diverging_commit_on_main, new_version.to_string()))
    else:
        new_version = current_version

    effective_version = git.find_effective_version(repo, repo.head())
    assert effective_version.decode() == new_version.to_string()


def test_get_active_and_auxiliary_branch_names(
    repo, gh, fake_gh_repo_id, fake_gh_pull_request_base_ref, fake_gh_pull_request_head_ref
):
    gh_repo = gh.get_repo(fake_gh_repo_id)

    active, auxiliary = git.get_active_and_auxiliary_branch_names(repo, gh_repo, repo.head())
    assert active == fake_gh_pull_request_base_ref
    assert auxiliary == fake_gh_pull_request_head_ref


@pytest.mark.parametrize(
    "branch_name, expected_label, expected_role",
    [
        ("x_main", "dev", BranchFunctionalRole.trunk),
        ("x_release", None, BranchFunctionalRole.release),
        ("x_rc/1.2.3", "rc", BranchFunctionalRole.release_candidate),
        ("x_rc/foo", "rc", BranchFunctionalRole.release_candidate),
        ("x_prod", "prod", BranchFunctionalRole.release),
    ],
)
def test_get_branch_label_and_role(fake_project_root_dir, branch_name, expected_label, expected_role):
    conf = ProjectConfig(fake_project_root_dir)

    label, roll = git.get_branch_label_and_role(conf, branch_name)
    assert label == expected_label
    assert roll == expected_role


def test_commit_id_to_version_map_with_prefix(repo, fake_project_root_dir, create_commit):
    commit_bare_1 = create_commit(CommitType.feat, "v1.0.0")
    commit_bare_2 = create_commit(CommitType.feat, "v1.1.0")
    commit_a_1 = create_commit(CommitType.feat, "project-a/v2.0.0")
    commit_a_2 = create_commit(CommitType.feat, "project-a/v2.1.0")
    commit_b_1 = create_commit(CommitType.feat, "project-b/v3.0.0")

    bare_map = git.commit_id_to_version_map(repo, None)
    assert len(bare_map) == 2
    assert bare_map[commit_bare_1] == b"v1.0.0"
    assert bare_map[commit_bare_2] == b"v1.1.0"

    a_map = git.commit_id_to_version_map(repo, "project-a")
    assert len(a_map) == 2
    assert a_map[commit_a_1] == b"v2.0.0"
    assert a_map[commit_a_2] == b"v2.1.0"

    b_map = git.commit_id_to_version_map(repo, "project-b")
    assert len(b_map) == 1
    assert b_map[commit_b_1] == b"v3.0.0"


def test_find_effective_version_with_prefix(repo, fake_project_root_dir, create_commit):
    create_commit(CommitType.feat, "v1.0.0")
    create_commit(CommitType.feat, "project-a/v2.0.0")
    create_commit(CommitType.feat)

    assert git.find_effective_version(repo, repo.head(), None) == b"v1.0.0"
    assert git.find_effective_version(repo, repo.head(), "project-a") == b"v2.0.0"
    assert git.find_effective_version(repo, repo.head(), "project-c") == ProjectVersion.DEFAULT_MINIMUM_VERSION.encode()


# ========== Path-scoped commit filtering ==========


class TestCommitTouchesPaths:

    @pytest.mark.parametrize(
        "committed_path, owned_dir, expected",
        [
            pytest.param("svc-a/main.py", "svc-a", True, id="matching_path"),
            pytest.param("svc-b/main.py", "svc-a", False, id="non_matching_path"),
        ],
    )
    def test_path_matching(self, repo_root_dir, repo, create_commit_at_path, committed_path, owned_dir, expected):
        create_commit_at_path("svc-a/init.py", "initial")
        commit_id = create_commit_at_path(committed_path, "feat: a feature")

        assert git.commit_touches_paths(
            repo, commit_id, [repo_root_dir / owned_dir], repo_root_dir
        ) is expected

    def test_initial_commit_always_included(self, repo_root_dir, repo, create_commit_at_path):
        commit_id = create_commit_at_path("svc-b/main.py", "initial")

        assert git.commit_touches_paths(
            repo, commit_id, [repo_root_dir / "svc-a"], repo_root_dir
        )

    def test_merge_commit_diffs_first_parent(
        self, repo_root_dir, repo, create_commit_at_path, default_fake_user_name, default_fake_user_email
    ):
        create_commit_at_path("svc-a/init.py", "initial")

        main_branch = porcelain.active_branch(repo)
        feature_branch = b"feature/test-merge"
        porcelain.branch_create(str(repo_root_dir), feature_branch)
        porcelain.update_head(repo, feature_branch)

        create_commit_at_path("svc-b/feature.py", "feat: b on branch")

        porcelain.update_head(repo, main_branch)
        merge_id = git.create_merge_commit(
            repo=repo,
            feature_branch_name=feature_branch.decode(),
            commit_user=f"{default_fake_user_name} <{default_fake_user_email}>",
        )

        assert not git.commit_touches_paths(
            repo, merge_id, [repo_root_dir / "svc-a"], repo_root_dir
        )


class TestGetCommitMessagesWithOwnedPaths:

    def test_filters_by_owned_paths(self, repo_root_dir, repo, create_commit_at_path):
        create_commit_at_path("svc-a/init.py", "initial")
        porcelain.tag_create(
            repo, annotated=True, tag=b"v1.0.0",
            message=b"release: v1.0.0",
        )

        create_commit_at_path("svc-a/main.py", "feat: pipeline a feature")
        create_commit_at_path("svc-b/main.py", "feat!: breaking change to b")
        create_commit_at_path("svc-a/util.py", "fix: shared fix")

        messages = git.get_commit_messages(
            repo, "v1.0.0",
            owned_paths=[repo_root_dir / "svc-a"],
            repo_root=repo_root_dir,
        )

        assert len(messages) == 2
        assert any("pipeline a feature" in m for m in messages)
        assert any("shared fix" in m for m in messages)
        assert not any("breaking change to b" in m for m in messages)

    def test_no_filtering_when_owned_paths_empty(self, repo_root_dir, repo, create_commit_at_path):
        create_commit_at_path("svc-a/init.py", "initial")
        porcelain.tag_create(
            repo, annotated=True, tag=b"v1.0.0",
            message=b"release: v1.0.0",
        )

        create_commit_at_path("svc-a/main.py", "feat: a feature")
        create_commit_at_path("svc-b/main.py", "feat: b feature")

        messages_empty = git.get_commit_messages(
            repo, "v1.0.0", owned_paths=[], repo_root=repo_root_dir,
        )
        messages_none = git.get_commit_messages(repo, "v1.0.0")

        assert len(messages_empty) == 2
        assert len(messages_none) == 2

