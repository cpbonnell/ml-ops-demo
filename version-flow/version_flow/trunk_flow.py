import logging

from version_flow import message_parsing
from version_flow.clairity_repo import ClairityRepo
from version_flow.errors import VersionFlowCheckoutError
from version_flow.project_config import ProjectConfig
from version_flow.project_version import ProjectVersion
from version_flow.types import FunctionalBranch, VersionSpec, BumpPriority


def trunk_flow(
    config: ProjectConfig,
    clairity_repo: ClairityRepo,
    functional_branch: FunctionalBranch,
    logger: logging.Logger = logging.getLogger(__name__),
    dry_run: bool = True,
):
    # 1. Check the current version string against the last version the repo was tagged with
    config_version_string = config.version_string
    current_version = ProjectVersion.from_string(config_version_string, config.version_spec)

    check_current_version_state(
        config_version_string,
        clairity_repo.get_most_recent_version(),
        functional_branch,
        config.version_spec,
        logger=logger,
    )

    if functional_branch == FunctionalBranch.trunk:

        # 2. Fetch commit messages and determine the magnitude of the bump required
        commit_messages = clairity_repo.get_commit_messages(
            since_tag=clairity_repo.get_most_recent_version_tag(),
            owned_paths=config.owned_paths,
        )
        bump_priority = message_parsing.get_bump_from_messages(commit_messages)
        if bump_priority in [BumpPriority.to_release, BumpPriority.from_release]:
            raise RuntimeError(
                f"Cannot perform an application release from the trunk branch. Please push a release branch to "
                f"continue."
            )
        logger.info(f"Parsed {len(commit_messages)} commit messages, requiring a version bump of {bump_priority.name}.")

        # 3. Create a bumped version and perform the bump commit
        new_version = current_version.bump(bump_priority)
        logger.info(
            f"Bumping from version {current_version} to version {new_version}. Changes will be committed, and "
            f"the repository will be tagged."
        )
        clairity_repo.do_version_bump_commit(new_version, dry_run)

    elif functional_branch == FunctionalBranch.release:

        # 2. Perform a release version bump commit
        new_release_version = current_version.bump(BumpPriority.to_release)
        logger.info(
            f"Performing a release from version {current_version} to version {new_release_version}. Changes will be"
            f"committed, and the repository will be tagged."
        )
        release_commit_id = clairity_repo.do_version_bump_commit(new_release_version, dry_run)

        # 3.a. Switch to the trunk branch and cherry-pick the release commit
        logger.info(f"Switching to trunk branch and cherry-picking release commit {release_commit_id}...")
        try:
            clairity_repo.change_branch_and_cherry_pick(config.trunk_branch, release_commit_id)
        except KeyError as e:
            raise VersionFlowCheckoutError(config.trunk_branch) from e

        # 3.b. Perform a version bump on main to set the version back to a pre-release version
        new_prerelease_version = new_release_version.bump(BumpPriority.from_release)
        logger.info(
            f"Performing a version bump on trunk branch from release version {new_release_version} to prerelease "
            f"version {new_prerelease_version}. Changes will be committed, and the repository will be tagged."
        )
        clairity_repo.do_version_bump_commit(new_prerelease_version, dry_run)

    # 4. Check for the existence of a release PR, and if none exists, then create one
    clairity_repo.create_next_release_pr(dry_run)


def check_current_version_state(
    config_version_string: str,
    tagged_version_string: str | None,
    functional_branch: FunctionalBranch,
    version_spec: VersionSpec,
    logger: logging.Logger = logging.getLogger(__name__),
):
    """Examine the current state of the repo and determine if the version bump can move forward.

    If the function returns, then a version bump is viable given the state of the repository.
    If there are any incompatibilities, then an appropriate error is raised. Relevant information
    about the comparison is logged to the screen.

    Parameters
    ----------
    config_version_string: str The version found in pyproject.toml
    tagged_version_string: str The last version tagged in the repository
    functional_branch: FunctionalBranch The current functional branch of the repository
    version_spec: VersionSpec The version spec found in pyproject.toml
    logger: logging.Logger The logger to print statements to
    """
    config_version = ProjectVersion.from_string(config_version_string, version_spec)

    # Determine if we have a tagged version that we can parse
    if tagged_version_string is None:
        logger.warning(
            f"This repository does not have an existing tagged version. Proceeding with only the "
            f"version from pyproject.toml."
        )
        tagged_version_message = ""
    else:
        tagged_version = ProjectVersion.from_string(tagged_version_string, version_spec)
        tagged_version_message = f"The most recently tagged version is {tagged_version}. "

        # We want to require that for bumps to the trunk branch, we require that the version from pyproject.toml
        # and the tagged version match. If they don't, then a developer should resolve the difference.
        if functional_branch == FunctionalBranch.trunk and tagged_version != config_version:
            raise ValueError(
                f"The version {config_version} from pyproject.toml does not match the most recent tagged "
                f"version {tagged_version}. Cannot proceed with the version-flow process to this trunk branch. "
                f"Please manually tag the repository, or adjust the version string in pyproject.toml."
            )

    # Log the current state of the repository
    logger.info(
        f"The current branch is a {functional_branch.name} branch, "
        f"and the current version from pyproject.toml is {config_version}. "
        f"{tagged_version_message}"
        f"This is an allowed transition for this branch.\n"
    )
