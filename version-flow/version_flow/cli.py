import logging
from pathlib import Path

import click

from version_flow.clairity_repo import ClairityRepo
from version_flow.project_config import ProjectConfig
from version_flow.trunk_flow import trunk_flow
from version_flow.fda_flows import fda_git_flow
from version_flow.types import GitBranchStrategy


@click.command()
@click.argument(
    "config-file-location",
    type=click.Path(exists=True, resolve_path=True, path_type=Path),
)
@click.option(
    "--log-level",
    envvar="VERSION_FLOW_LOG_LEVEL",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Set the logging level",
)
@click.option(
    "--dry-run",
    envvar="VERSION_FLOW_DRY_RUN",
    is_flag=True,
    default=False,
    help=(
        "Do not make any upstream changes to git, but show a list of changes that would happen instead. All local "
        "changes will happen as normal"
    ),
)
def main(config_file_location: Path, log_level: str, dry_run: bool):

    logging.basicConfig(level=log_level.upper())
    logger = logging.getLogger(__name__)

    logger.info(f"Beginning version-flow on project located at {config_file_location}")

    if dry_run:
        logger.info("This run of version-flow will be conducted as a dry run. No files will be pushed to remote.")

    # Instantiate workhorse objects and determine what branch we are running the workflow for
    config = ProjectConfig(config_file_location)

    # Invoke the workflow
    match config.git_branch_strategy:
        case GitBranchStrategy.trunk_flow:
            logger.info("Beginning run with Branch Strategy: Trunk Flow")
            clairity_repo = ClairityRepo(config)
            functional_branch = clairity_repo.get_functional_branch()
            trunk_flow(
                config,
                clairity_repo,
                functional_branch,
                logger=logger,
                dry_run=dry_run,
            )
        case GitBranchStrategy.fda_git_flow:
            logger.info("Beginning run with Branch Strategy: FDA Git Flow")
            fda_git_flow(config, dry_run=dry_run)
        case GitBranchStrategy.fda_trunk_flow:
            raise NotImplementedError("fda trunk flow branching strategy is not yet implemented.")
        case _:
            raise ValueError(
                f"Not a valid git branch strategy. Please check your pyproject.toml file"
                f"and ensure it is one of {[gbs.value for gbs in GitBranchStrategy]}"
            )

    logger.info("Completed version-flow.")
