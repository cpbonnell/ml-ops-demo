import logging
import re
from functools import cache
from pathlib import Path
from typing import Optional, Iterable, Callable

import giturlparse
from dulwich import diff_tree
from dulwich import porcelain
from dulwich.objects import Commit
from dulwich.repo import Repo
from dulwich.walk import ORDER_TOPO
from github import Github, Auth
from github.Branch import Branch
from github.PullRequest import PullRequest
from github.GithubException import UnknownObjectException
from github.Repository import Repository as RemoteRepository
from packaging.version import VERSION_PATTERN

from version_flow import git
from version_flow.project_config import ProjectConfig
from version_flow.project_version import ProjectVersion
from version_flow.types import FunctionalBranch
from version_flow.errors import VersionFlowCIError, VersionFlowConcurrencyError

logger = logging.getLogger(__name__)


class ClairityRepo:
    """
    This is an abstraction on top of a normal Git repository.

    Clairity uses a number of conventions and CI processes to organize repositories and tag code with release versions.
    This class exposes an interface to many of the most common and useful elements of those conventions. It can also be
    used to conduct some of the common tasks, such as version tagging.
    """

    def __init__(self, project_root_or_config: str | Path | ProjectConfig):
        """Construct a ClairityRepo object.

        Parameters
        ----------
        project_root_or_config: Path
            The root directory of the Git repository.
        """
        match project_root_or_config:
            case Path() | str():
                config = ProjectConfig(project_root_or_config)
            case ProjectConfig():
                config = project_root_or_config
            case _:
                raise ValueError(
                    f"ClairityRepo must be initialized with a ProjectConfig or a path, "
                    f"but got {type(project_root_or_config)} instead."
                )

        # Config git user
        self._config = config
        self._repo = self._config.get_repo()
        git_config = self._repo.get_config()
        git_config.set("user", "name", "clairityBot")
        git_config.set("user", "email", "infra+clairitybot@clairity.com")
        git_config.write_to_path(git_config.path)

        # Note: the regex below will match well-formed SemVer as well as PyVer version strings,
        # both with an optional 'v' at the beginning.
        self._version_regex = re.compile(VERSION_PATTERN, re.VERBOSE | re.IGNORECASE)

    @property
    def base_repo(self) -> Repo:
        return self._repo

    @property
    def remote_repository_name(self) -> str:
        remote_origin_url = self._repo.get_config().get(("remote", "origin"), "url").decode()
        parts = giturlparse.parse(remote_origin_url)
        return f"{parts.owner}/{parts.repo}"

    def get_functional_branch(self) -> FunctionalBranch:
        match porcelain.active_branch(self._repo).decode():
            case self._config.trunk_branch:
                return FunctionalBranch.trunk
            case self._config.staging_branch:
                raise NotImplementedError("Clairity does not currently support repositories with a staging branch.")
            case self._config.release_branch:
                return FunctionalBranch.release
            case _:
                return FunctionalBranch.other

    def get_most_recent_version_tag(self) -> Optional[str]:
        """Returns the full tag name of the most recent release.

        When the project has a ``project_name_in_tag`` prefix, only tags
        matching that prefix are considered and the full prefixed tag name
        is returned (e.g. ``"svc-a/v1.2.3"``).
        """
        prefix = self._config.project_name_in_tag

        version_tagged_commit_ids = {
            git.dereference_tag(self._repo, ref): tag
            for tag, ref in self._repo.refs.as_dict(b"refs/tags/").items()
            if _is_version_tag(tag.decode(), prefix, self._version_regex)
        }

        walker = self._repo.get_walker(order=ORDER_TOPO)
        for entry in walker:
            if entry.commit.id in version_tagged_commit_ids:
                return version_tagged_commit_ids[entry.commit.id].decode()

        return None

    def get_most_recent_version(self) -> Optional[str]:
        """Returns the version string of the most recent release, without any tag prefix."""
        tag = self.get_most_recent_version_tag()
        prefix = self._config.project_name_in_tag
        if tag and prefix:
            return tag.removeprefix(f"{prefix}/")

        return tag

    def get_commit_messages(
        self, since_tag: Optional[str], owned_paths: list[Path] | None = None
    ) -> list[str]:
        """
        Get commit messages of the repo, starting at HEAD and going backward in topological order.

        Parameters
        ----------
        since_tag: str | bytes
            If supplied, then only commit messages more recent than that tag will be returned.
        owned_paths: list[Path] | None
            If supplied, only commits that touched files under these paths are included.

        Returns
        -------
        message_list: list[str]
            A list of all commit messages in chronological order from head to tail
        """
        return git.get_commit_messages(
            self._repo,
            since_tag,
            owned_paths=owned_paths,
            repo_root=self._config.repository_root if owned_paths else None,
        )

    def do_version_bump_commit(self, new_version: ProjectVersion, dry_run: bool = False) -> bytes:
        """Do a standard version bump commit, and return the commit ID and tag ID."""
        return git.do_version_bump_commit(self._config, self._repo, new_version, dry_run)

    def change_branch_and_cherry_pick(self, branch_name: str, commit: bytes | Commit) -> tuple[bytes, list[str]]:
        """Check out the branch_name, and cherry-pick the commit.

        Note: the cherry-pick performed is not the fully implemented cherry-pick from the Git command line utility, but
        rather a quick-and-dirty implementation that naively pulls over the exact content of the cherry-picked commit
        without performing proper conflict resolution.

        Parameters
        ----------
        branch_name: str
            The new branch to be checked out and cherry-picked to
        commit: bytes | Commit
            The Commit object or commit ID to cherry-pick onto the new branch

        Returns
        -------
        new_commit_id: bytes
            The commit ID of the newly created commit
        files: list[str]
            The file paths that were changed by the cherry-pick commit.
        """

        if type(commit) is bytes:
            commit = self._repo[commit]

        # Switch to our new branch
        porcelain.checkout(self._repo, branch_name)
        copied_files = list()

        for relative_path, blob in git.get_filenames_from_commit(self._repo, commit).items():
            # Overwrite the file content with the new version
            full_path = Path(self._repo.path) / relative_path
            content = blob.data
            copied_files.append(full_path.as_posix())
            with open(full_path, "wb") as f:
                f.write(content)

        added_files, ignored_files = porcelain.add(self._repo, copied_files)

        # Perform the new commit with the same metadata
        new_commit_id = porcelain.commit(
            self._repo,
            message=commit.message,
            author=commit.author,
            commit_timestamp=commit.commit_time,
        )

        return new_commit_id, added_files

    @cache
    def get_remote_repo(self) -> RemoteRepository:
        """Get an instance of the GitHub Repository object from an authenticated GitHub API.

        Returns
        -------
        remote_repo: RemoteRepository

        Raises
        ------
        ValueError
            If the environment variable GH_TOKEN is not set.
        """
        if not self._config.github_token:
            # If we can't find the auth token for GitHub, don't continue
            raise VersionFlowCIError(
                "No GitHub Token configured. Please check the runtime context for the GH_TOKEN "
                "environment variable and try again."
            )

        logger.info("Found GitHub token in environment variables.")
        logger.info("Authenticating with GitHub...")
        gh_auth = Auth.Token(self._config.github_token)
        gh = Github(auth=gh_auth)

        logger.info(f"Identified remote repository {self.remote_repository_name} as the target repository for the PR.")

        try:

            remote_repo = gh.get_repo(self.remote_repository_name)

        except UnknownObjectException as e:
            raise VersionFlowCIError(
                "version-flow received an 'object not found' error from GitHub while trying to retrieve the repository "
                "data. This usually indicates that your repository has not been fully configured. Please ensure that "
                "the 'clairity-inc/cicd' team has been added to your repository's 'Collaborators and teams' section "
                "with at least a 'Maintain' role."
            ) from e

        logger.info("Repository info has been retrieved from GitHub.")
        return remote_repo

    def release_branch_exists(self, branches: Iterable[Branch] | None = None) -> bool:
        """Check whether the release branch specified in the project config exists.

        If branches is not supplied, then the function will attempt to automatically connect to GitHub and retrieve
        a list of branches.

        Parameters
        ----------
        branches: Iterable[Branch] | None

        Returns
        -------
        exists: bool
        """
        if branches is None:
            branches = self.get_remote_repo().get_branches()

        return len([branch for branch in branches if branch.name == self._config.release_branch]) > 0

    def _release_pr_title(self) -> str:
        prefix = self._config.project_name_in_tag
        if prefix:
            return f"Release: {prefix}"

        return "Next Release"

    def next_release_pr_exists(
        self,
        pull_requests: Iterable[PullRequest] | None = None,
        logging_callback: Callable[[Iterable[PullRequest]], None] | None = lambda pulls: None,
    ) -> bool:
        """Check whether a "Next Release" PR exists.

        If pull_requests is not supplied, then the function will attempt to automatically connect to GitHub and retrieve
        a list of open pull requests.

        When ``project_name_in_tag`` is configured, only PRs whose title matches this
        sub-project are considered, so that independent sub-projects don't block each
        other.

        Parameters
        ----------
        pull_requests: Iterable[PullRequest] | None
        logging_callback: Callable[[Iterable[PullRequest]], None] | None
            If any "Next Release" pull requests are found, then this call back will be invoked on the list of
            pull request objects that could classify as a "Next Release" pull request.

        Returns
        -------
        exists: bool
        """
        # Note: the get_pulls() method that feeds this method does have a parameter for selecting only pull
        # requests with a specific head, but the GitHub web API is unreliable about respecting that filter.
        if pull_requests is None:
            pull_requests = self.get_remote_repo().get_pulls(state="open")

        expected_title = self._release_pr_title()
        release_pulls = [
            pull
            for pull in pull_requests
            if pull.base.ref == self._config.release_branch
            and pull.head.ref == self._config.trunk_branch
            and pull.title == expected_title
        ]

        if len(release_pulls) > 0:
            logging_callback(release_pulls)
            return True

        return False

    def create_next_release_pr(self, dry_run: bool = False) -> None:
        """Create a new pull request to merge trunk branch to release branch.

        The merging of this pull request is the event that will trigger the next release event. The names of the
        release branch and trunk branch are pulled from the project configuration.

        Parameters
        ----------
        dry_run: bool
            If True, then the call to this function will be logged, but no calls will be made to the GitHub API.
        """
        # Early termination conditions
        if dry_run:
            # If this is a dry run, don't continue
            logger.info(
                f"This dry-run is skipping creation of release PR from {self._config.trunk_branch} "
                f"to {self._config.release_branch}."
            )
            return

        # Check to make sure release branch actually exists, and if not we log it and terminate here
        if not self.release_branch_exists():
            logger.error(
                f"Cannot create a release PR from {self._config.trunk_branch} to "
                f"{self._config.release_branch} because branch {self._config.release_branch} does not exist."
            )
            return

        # Check to see if the "Next Release" PR already exists, and if so we log it and exit
        if self.next_release_pr_exists(logging_callback=existing_pr_logging_callback):
            return

        # Look up remote name, and submit PR.
        title = self._release_pr_title()
        logger.info(f"No release PRs currently exist for this project, so a new one will be created: '{title}'")
        remote_repo = self.get_remote_repo()

        prefix = self._config.project_name_in_tag
        if prefix:
            body = (
                f"Automated release PR for **{prefix}**. "
                "I was generated by our clairityBot. Beep. Boop.\n\n"
                "Merge this Pull Request in order to trigger the next release event."
            )
        else:
            body = (
                "Automated release PR. I was generated by our clairityBot. Beep. Boop.\n\n"
                "Merge this Pull Request in order to trigger the next release event."
            )

        result = remote_repo.create_pull(
            head=self._config.trunk_branch,
            base=self._config.release_branch,
            title=title,
            body=body,
        )
        logger.info(f"Successfully created Pull Request {result.number}: {result.html_url}")


def _is_version_tag(tag_name: str, prefix: str | None, regex: re.Pattern) -> bool:
    if prefix:
        if not tag_name.startswith(f"{prefix}/"):
            return False
        return bool(regex.match(tag_name.removeprefix(f"{prefix}/")))
    return b"/" not in tag_name.encode() and bool(regex.match(tag_name))


# Utility functions that don't need to be methods
def existing_pr_logging_callback(pulls: Iterable[PullRequest]):
    logger.info(
        "A release PR for this repository already exists, so no new one will be created. To create "
        "another release, you may merge any of the following pull requests:"
    )
    for pull in pulls:
        logger.info(f"    -- #{pull.number} ''{pull.title}'' {pull.html_url}")
