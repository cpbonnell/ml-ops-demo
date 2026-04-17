import itertools
import secrets
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from secrets import token_hex
from tempfile import TemporaryDirectory
from typing import Iterable
from typing import Optional, Callable

from github import Github

from version_flow.git import to_bytes
import responses
import tomlkit

import lorem
import pytest
from dulwich import porcelain
from dulwich.repo import Repo

from version_flow.git import create_merge_commit
from version_flow.types import CommitType
from version_flow.project_config import ProjectConfig


# ========== Fake Project Builder ==========


FAKE_PROJECTS_DIR = Path("tests/data/fake_projects")


class DepTool(Enum):
    """The dependency management tool used by a fake project template."""
    poetry_1x = "poetry1.x-project"
    poetry_2x = "poetry2.x-project"
    uv = "uv-project"


# The default version-flow config that matches the old static templates.
DEFAULT_VERSION_FLOW_CONFIG = {
    "git_branch_strategy": "trunk_flow",
    "version_specification": "semver",
    "files_to_update": ["workbench/__init__.py"],
    "trunk_branch": "x_main",
    "release_branch": "x_release",
    "managed-branches": {
        "release-candidate": {"rc": "x_rc/.*"},
        "named-release": {"prod": "x_prod"},
    },
}


def build_fake_project(
    target_dir: Path,
    dep_tool: DepTool,
    version_flow_config: dict | None = None,
) -> Path:
    """Copy a dep-tool template into target_dir and inject the version-flow config.

    Parameters
    ----------
    target_dir:
        The directory to populate (typically repo_root_dir from the fixture).
    dep_tool:
        Which dependency management template to use.
    version_flow_config:
        The full [tool.version-flow] config dict. If None, DEFAULT_VERSION_FLOW_CONFIG is used.

    Returns
    -------
    target_dir, for convenience.
    """
    source = FAKE_PROJECTS_DIR / dep_tool.value
    shutil.copytree(source, target_dir, dirs_exist_ok=True)

    config = version_flow_config or DEFAULT_VERSION_FLOW_CONFIG

    pyproject_path = target_dir / "pyproject.toml"
    with open(pyproject_path, "r") as f:
        doc = tomlkit.load(f)

    # Ensure [tool] table exists
    if "tool" not in doc:
        doc["tool"] = tomlkit.table()

    doc["tool"]["version-flow"] = config

    with open(pyproject_path, "w") as f:
        tomlkit.dump(doc, f)

    return target_dir


@pytest.fixture()
def most_recent_version_tag() -> str:
    """Tag of the most recent version, as expected by most code."""
    return "v1.2.3-rc.4"


@pytest.fixture()
def most_recent_version_ref(most_recent_version_tag) -> bytes:
    """The ref to the most recent version tag, as expected by dulwich code."""
    return bytes(f"refs/tags/{most_recent_version_tag}", encoding="utf-8")


@pytest.fixture()
def repo_root_dir() -> Path:
    with TemporaryDirectory() as tempdir:
        yield Path(tempdir).resolve()


@pytest.fixture()
def default_fake_user_name() -> str:
    return "Test Testerson"


@pytest.fixture()
def default_fake_user_email() -> str:
    return "test.testerson@clairity.com"


@pytest.fixture()
def default_fake_feature_branch_name() -> str:
    return "feature/ps-111-cure-cancer"


@pytest.fixture()
def repo(repo_root_dir, default_fake_user_name, default_fake_user_email) -> Repo:
    temp_repo = Repo.init(str(repo_root_dir), default_branch=b"main")
    config = temp_repo.get_config()
    config.set("user", "name", default_fake_user_name)
    config.set("user", "email", default_fake_user_email)
    config.write_to_path(config.path)
    return temp_repo


@pytest.fixture()
def fake_project_builder(repo_root_dir, repo) -> Callable[..., Path]:
    """Factory fixture that builds a fake project in the test's git repo.

    Usage in tests::

        def test_something(fake_project_builder):
            project_dir = fake_project_builder(DepTool.poetry_2x)

        # With custom version-flow config:
        def test_monorepo(fake_project_builder):
            config = {**DEFAULT_VERSION_FLOW_CONFIG, "project_name_in_tag": "my-lib"}
            project_dir = fake_project_builder(DepTool.uv, version_flow_config=config)
    """

    def _build(dep_tool: DepTool, version_flow_config: dict | None = None) -> Path:
        build_fake_project(repo_root_dir, dep_tool, version_flow_config)
        porcelain.add(repo)
        initial_commit_id = porcelain.commit(repo, message=b"Initial commit with project infrastructure.")
        porcelain.tag_create(
            repo,
            annotated=True,
            tag=b"initial",
            message=b"Initial Commit Tag.",
            objectish=initial_commit_id,
        )
        return repo_root_dir

    return _build


def _fda_config() -> dict:
    """Return a version-flow config dict with fda_git_flow strategy."""
    return {**DEFAULT_VERSION_FLOW_CONFIG, "git_branch_strategy": "fda_git_flow"}


# Parametrized fixture that runs each test against all 6 dep-tool × strategy combos.
# This is the backward-compatible replacement for the old static-template approach.
@pytest.fixture(
    params=[
        pytest.param((DepTool.poetry_1x, None), id="poetry_1x_trunk"),
        pytest.param((DepTool.poetry_2x, None), id="poetry_2x_trunk"),
        pytest.param((DepTool.uv, None), id="uv_trunk"),
        pytest.param((DepTool.poetry_1x, _fda_config()), id="poetry_1x_fda"),
        pytest.param((DepTool.poetry_2x, _fda_config()), id="poetry_2x_fda"),
        pytest.param((DepTool.uv, _fda_config()), id="uv_fda"),
    ]
)
def fake_project_root_dir(request, fake_project_builder) -> Path:
    dep_tool, version_flow_config = request.param
    yield fake_project_builder(dep_tool, version_flow_config)


@pytest.fixture()
def random_file_factory(repo_root_dir) -> Callable[[], str]:

    def _random_file_factory() -> str:
        new_file_name = f"{token_hex(4)}.txt"
        with open(repo_root_dir / new_file_name, "w") as f:
            f.write(token_hex(16))

        return new_file_name

    return _random_file_factory


@pytest.fixture()
def create_commit_at_path(repo_root_dir, repo) -> Callable[[str, str], bytes]:

    def _create_commit_at_path(relative_path: str, message: str) -> bytes:
        full_path = repo_root_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(token_hex(16))
        porcelain.add(repo, [str(full_path)])
        return porcelain.commit(repo, message=message.encode())

    return _create_commit_at_path


# ========== Fixtures for fabricating a Git history ==========
@pytest.fixture()
def create_commit(repo_root_dir, repo, random_file_factory) -> Callable[[CommitType, Optional[str], bool], bytes]:

    def _create_commit(commit_type: CommitType, tag: Optional[str] = None, unstaged_change: bool = False) -> bytes:
        """Add a commit to the repo, and optionally tag it.

        Parameters
        ----------
        commit_type: CommitType
            The name of the commit type will be used for the <type> of the commit message.
        tag: str
            If provided, the commit will be tagged with this string.
        unstaged_change: bool
            If true, then after the original file is committed, a change will be made to the file but not staged.

        Returns
        -------
        id:
            The ID of the commit added to the repo. (Note this is different than the ID of the tag).

        """
        new_file_name = random_file_factory()
        porcelain.add(repo, [new_file_name])
        commit_message = bytes(f"{commit_type.name}: write file {new_file_name}", encoding="utf-8")
        commit_id = porcelain.commit(repo, message=commit_message)

        if tag:
            tag_message = bytes(f"release: {tag}", encoding="utf-8")
            porcelain.tag_create(
                repo,
                annotated=True,
                tag=bytes(tag, encoding="utf-8"),
                message=tag_message,
                objectish=commit_id,
            )

        if unstaged_change:
            with open(repo_root_dir / new_file_name, "a") as f:
                f.writelines(["\n", token_hex(16)])

        return commit_id

    return _create_commit


@pytest.fixture()
def create_git_history(
    repo,
    create_commit,
    most_recent_version_tag,
    default_fake_feature_branch_name,
    default_fake_user_name,
    default_fake_user_email,
) -> Callable[[list[CommitType], list[CommitType], list[CommitType], str | bytes | None, bool, bool, int], list[bytes]]:

    def _create_git_history(
        pre: list[CommitType],
        post: list[CommitType],
        feature: list[CommitType] = list(),
        feature_name: str | bytes | None = None,
        merge_feature: bool = True,
        include_version_tag: bool = True,
        pull_request_number: int = 1,
    ) -> list[bytes]:
        """Create a full Git history including a commit tagged with the most recent version.

        One commit will be created for each type in pre, followed by a commit tagged with the most recent
        version, and then another commit for each type in post. Returns a list of the commit IDs
        in the order of most recent to most ancient.

        If the feature list is nonempty, then a feature branch will be created, forked from the main branch
        after the commit pointed to by most_recent_version_tag. If merge_feature is True, then the feature
        branch will be merged back into the main branch, and the merge commit will be the last commit in the
        commit history. If the feature list is empty, then no branch will be created, even if a name is supplied.

        If a clean history with no version tags is desired, then set include_version_tag to False,
        and the full history will be created, branched, and merged as described above, but without the
        "most recent version tag" commit.

        Parameters
        ----------
        pre: list[CommitType]
            Commit types to be created before the most recent version tag.
        post: list[CommitType]
            Commit types to be created after the most recent version tag.
        feature: list[CommitType]
            Commit types to be created as a feature branch.
        feature_name: str | bytes | None
            Name of the feature branch.
        merge_feature: bool
            Whether the feature branch should be merged into the main branch. Default True.


        Returns
        -------
        commit_ids: list[bytes]
        """

        commit_ids = list()

        for commit_type in pre:
            commit_ids.append(create_commit(commit_type))

        if include_version_tag:
            commit_ids.append(
                create_commit(CommitType.ci, most_recent_version_tag),
            )

        for commit_type in post:
            commit_ids.append(create_commit(commit_type))

        if len(feature) > 0:
            previous_branch_name = porcelain.active_branch(repo)
            feature_name = to_bytes(feature_name, default_fake_feature_branch_name)
            porcelain.branch_create(repo.path, feature_name)
            porcelain.checkout(repo, feature_name)

            for commit_type in feature:
                commit_ids.append(create_commit(commit_type))

            if merge_feature:
                commit_ids.append(
                    create_merge_commit(
                        repo,
                        feature_branch_name=feature_name,
                        commit_user=f"{default_fake_user_name} <{default_fake_user_email}>",
                        pull_request_number=pull_request_number,
                    )
                )

            porcelain.checkout(repo, previous_branch_name)

        commit_ids.reverse()
        return commit_ids

    return _create_git_history


# ========== Fixtures for creating Git Messages ==========


@pytest.fixture()
def conventional_commit_message() -> Callable[[CommitType, bool, bool, bool], str]:

    def _message_creator(
        type: CommitType, scope: bool = False, breaking: bool = False, alt_breaking: bool = True
    ) -> str:
        """Return a one-line conventional commit message of the given type.

        The message will have a nonsense description section. If scope is True, then the first word of the description
        will be used as the scope. If breaking is True, then a "!" will be added just before the ":".
        """
        description_segment = lorem.sentence()
        scope_segment = f"({description_segment[0]})" if scope else ""
        breaking_segment = "!" if breaking else ""
        alt_breaking_segment = "!" if alt_breaking else ""

        return f"{type.name}{alt_breaking_segment}{scope_segment}{breaking_segment}: {description_segment}"

    return _message_creator


@pytest.fixture()
def squashed_commit_message() -> Callable[[list[str]], str]:

    def _message_creator(messages: list[str]) -> str:
        """Create a squashed commit message from a list of commit messages."""
        result = ""
        for message in messages:
            result += f"* {message}\n\n"
        return result.strip()

    return _message_creator


# ========== Fixtures for creating GitHub Entities ==========
from github.Branch import Branch
from github.NamedUser import NamedUser
from github.PullRequestPart import PullRequestPart
from github.PullRequest import PullRequest
from github.Requester import Requester


@pytest.fixture()
def gh_named_user_json() -> dict:
    return {
        "login": "clairity-test-user",
        "id": 123456789,
    }


@pytest.fixture()
def gh_requester():
    return Requester(
        auth=None,
        base_url="https://api.github.com",
        timeout=1,
        user_agent="clairity-inc",
        per_page=1,
        verify=False,
        retry=1,
        pool_size=1,
    )


@pytest.fixture()
def gh_named_user(gh_named_user_json, gh_requester) -> NamedUser:
    return NamedUser(
        attributes=gh_named_user_json,
        requester=gh_requester,
        headers=None,
    )


@pytest.fixture()
def gh_pr_part_factory(gh_named_user_json, gh_requester) -> Callable[[str], PullRequestPart]:

    def _github_pr_part(ref: str) -> PullRequestPart:
        return PullRequestPart(
            attributes={
                "ref": ref,
                "label": f"{gh_named_user_json['login']}:{ref}",
                "sha": secrets.token_hex(20),
                "user": gh_named_user_json,
            },
            requester=gh_requester,
            headers=None,
        )

    return _github_pr_part


@pytest.fixture()
def gh_pull_request_factory(gh_named_user_json, gh_pr_part_factory, gh_requester) -> Callable[[str, str], PullRequest]:

    pr_number = itertools.count()

    def _gh_pull_request_factory(
        head_name: str,
        base_name: str,
        this_pr_number: int | None = None,
        title: str | None = None,
        body: str | None = None,
        is_closed: bool = False,
    ) -> PullRequest:

        if not this_pr_number:
            this_pr_number = next(pr_number)

        if not title:
            title = f"Test PR {this_pr_number}"

        if not body:
            body = f"This is the body text for test PR {this_pr_number}."

        return PullRequest(
            attributes={
                "number": this_pr_number,
                "title": title,
                "body": body,
                "state": "closed" if is_closed else "open",
                "user": gh_named_user_json,
                "head": gh_pr_part_factory(head_name).raw_data,
                "base": gh_pr_part_factory(base_name).raw_data,
            },
            requester=gh_requester,
            headers=None,
        )

    return _gh_pull_request_factory


@pytest.fixture()
def github_branches(request, gh_requester) -> list[Branch]:
    if request and hasattr(request, "param"):
        names: Iterable[str] = request.param
    else:
        names = []

    return [Branch(attributes={"name": name}, requester=gh_requester, headers=None) for name in names]


@pytest.fixture()
def github_pull_requests(request, gh_pull_request_factory) -> list[PullRequest]:
    if request and hasattr(request, "param"):
        prs: Iterable[tuple[str, ...]] = request.param
    else:
        prs = []

    return [
        gh_pull_request_factory(pr[0], pr[1], title=pr[2] if len(pr) > 2 else None)
        for pr in prs
    ]


# ========== Fixtures for Mocking the GitHub API ==========

GITHUB_API = "https://api.github.com:443"


# ===== Owner =====
@pytest.fixture()
def fake_gh_owner_login():
    return "clairity-inc"


@pytest.fixture()
def fake_gh_owner_json(fake_gh_owner_login):
    return {
        "login": fake_gh_owner_login,
    }


@pytest.fixture()
def fake_gh_token_env(monkeypatch):
    token = "1234abcd"
    monkeypatch.setenv("GH_TOKEN", token)
    return token


# ===== Repository =====


@pytest.fixture()
def fake_gh_repo_id():
    return 123456789


@pytest.fixture()
def fake_gh_repo_name():
    return "fix-all-problems-in-the-world"


@pytest.fixture()
def fake_gh_repo_full_name(fake_gh_owner_login, fake_gh_repo_name):
    return f"{fake_gh_owner_login}/{ fake_gh_repo_name}"


@pytest.fixture()
def fake_gh_remote_origin_url(fake_gh_repo_full_name) -> str:
    return f"git@github.com:{fake_gh_repo_full_name}.git"


@pytest.fixture()
def fake_gh_repo_json(fake_gh_repo_id, fake_gh_repo_name, fake_gh_repo_full_name, fake_gh_owner_json):
    return {
        "id": fake_gh_repo_id,
        "name": fake_gh_repo_name,
        "owner": fake_gh_owner_json,
        "full_name": fake_gh_repo_full_name,
    }


# ===== Pull Request =====
@pytest.fixture()
def fake_gh_pull_request_number():
    return 111


@pytest.fixture()
def fake_gh_pull_request_base_ref(fake_project_root_dir):
    """The base ref for our PR is the trunk branch as specified in the config file."""
    conf = ProjectConfig(fake_project_root_dir)
    return conf.trunk_branch


@pytest.fixture()
def fake_gh_pull_request_head_ref(default_fake_feature_branch_name):
    """The head ref for our PR is the feature branch used to create the merge commit."""
    return default_fake_feature_branch_name


@pytest.fixture()
def fake_gh_pull_request_title(fake_gh_pull_request_head_ref, fake_gh_pull_request_base_ref):
    return f"Merge {fake_gh_pull_request_head_ref} into {fake_gh_pull_request_base_ref}"


@pytest.fixture()
def fake_gh_pull_request_json(
    fake_gh_pull_request_base_ref, fake_gh_pull_request_number, fake_gh_pull_request_head_ref
):

    return {
        "number": fake_gh_pull_request_number,
        "base": {"ref": fake_gh_pull_request_base_ref},
        "head": {"ref": fake_gh_pull_request_head_ref},
    }


@pytest.fixture()
def gh(
    repo,
    create_git_history,
    fake_gh_pull_request_head_ref,
    fake_gh_owner_json,
    fake_gh_repo_json,
    fake_gh_pull_request_json,
    fake_gh_owner_login,
    fake_gh_repo_id,
    fake_gh_repo_full_name,
    fake_gh_repo_name,
    fake_gh_pull_request_number,
    fake_gh_remote_origin_url,
):
    create_git_history(
        pre=[CommitType.feat],
        post=[CommitType.feat],
        feature=[CommitType.feat, CommitType.feat],
        feature_name=fake_gh_pull_request_head_ref,
        merge_feature=True,
        include_version_tag=True,
        pull_request_number=fake_gh_pull_request_number,
    )

    # Add necessary config to the local repository object
    config = repo.get_config()
    config.set(("remote", "origin"), "url", fake_gh_remote_origin_url)
    config.write_to_path(config.path)

    # Mock out the GitHub API
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:

        # ===== Repositories =====

        rsps.add(
            responses.GET,
            f"{GITHUB_API}/repositories/{fake_gh_repo_id}",
            status=200,
            json=fake_gh_repo_json,
        )

        rsps.add(
            responses.GET,
            f"{GITHUB_API}/repos/{fake_gh_repo_full_name}",
            status=200,
            json=fake_gh_repo_json,
        )

        # ===== Pull Requests =====
        rsps.add(
            responses.GET,
            f"{GITHUB_API}/repos/{fake_gh_owner_login}/{fake_gh_repo_name}/pulls",
            status=200,
            json=[fake_gh_pull_request_json],
        )

        rsps.add(
            responses.GET,
            f"{GITHUB_API}/repos/{fake_gh_owner_login}/{fake_gh_repo_name}/pulls/{fake_gh_pull_request_number}",
            status=200,
            json=fake_gh_pull_request_json,
        )

        yield Github("fake-token")
