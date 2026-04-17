import logging
import re

from version_flow.types import BumpPriority, CommitType

logger = logging.getLogger()

# This regular expression will match a single-line Conventional Commit message with the form
# "topic(scope)!: description". The scope and exclamation (indicating a breaking change) are
# optional, but topic, colon and description are required. When used in a match, the result
# is a dict with the fields "topic", "scope", "break" and "description".
CONVENTIONAL_COMMIT_REGEX = (
    r"^(\* )?(?P<topic>[a-zA-Z]+)(?P<break>!)? ?(\((?P<scope>\S*)\))?(?P<alt_break>!)?: (?P<description>.+)$"
)

_parser = re.compile(CONVENTIONAL_COMMIT_REGEX)

_minor_topics = [
    t.value
    for t in [
        CommitType.feat,
    ]
]
_patch_topics = [
    t.value
    for t in [
        CommitType.build,
        CommitType.chore,
        CommitType.fix,
        CommitType.perf,
        CommitType.refactor,
        CommitType.revert,
        CommitType.test,
    ]
]
_rc_topics = [
    t.value
    for t in [
        CommitType.ci,
        CommitType.docs,
        CommitType.style,
    ]
]


def get_bump_from_messages(messages: str | list[str]) -> BumpPriority:
    """Parse a list of commit messages to determine the bump priority.

    For information on the logic of version bumping from commit messages, see[RFC-1049]
    (https://clairityadmin.atlassian.net/wiki/spaces/Eng/pages/836665346/RFC-1049+Replacement+for+version_flow.sh)
    """
    if isinstance(messages, str):
        messages = [messages]

    minimum_required_bump = BumpPriority.rc
    for message in messages:
        if minimum_required_bump == BumpPriority.major:
            break

        for line in message.splitlines():
            if minimum_required_bump == BumpPriority.major:
                break

            # Parse each line as either a Conventional Commit header, or a body line
            match = _parser.match(line)
            if match:
                parts = match.groupdict()
            else:
                parts = {"body": line}

            # Based on the contents of the captured groups, update the minimum_required_bump
            match parts:

                case {"break": "!"} | {"alt_break": "!"}:
                    minimum_required_bump = max(minimum_required_bump, BumpPriority.major)
                    logger.info(f"Breaking change identified in header. This will require a bump in MAJOR version.")

                case {"topic": t} if t in _minor_topics:
                    minimum_required_bump = max(minimum_required_bump, BumpPriority.minor)
                    logger.info(
                        f"Minor version bump identified (topic {t}). This will require a bump in MINOR version."
                    )

                case {"topic": t} if t in _patch_topics:
                    minimum_required_bump = max(minimum_required_bump, BumpPriority.patch)
                    logger.info(
                        f"Patch version bump identified (topic {t}). This will require a bump in PATCH version."
                    )

                case {"topic": t} if t in _rc_topics:
                    minimum_required_bump = max(minimum_required_bump, BumpPriority.rc)
                    logger.info(
                        f"Release candidate version bump identified (topic {t}). This will require a bump in RC version."
                    )

                case {"topic": t}:
                    # We parsed a Conventional Commit with an unknown topic
                    minimum_required_bump = max(minimum_required_bump, BumpPriority.rc)
                    logger.info(
                        f"version-flow parsed a Conventional Commit message with an unknown topic '{t}'. This will be "
                        f"treated as a 'release candidate' topic."
                    )

                case {"description": s} | {"body": s} if "BREAKING CHANGE" in s:
                    minimum_required_bump = max(minimum_required_bump, BumpPriority.major)
                    logger.info(
                        f"Breaking change identified in the body of a commit. "
                        f"This will require a bump in MAJOR version."
                    )

                case {"body": b} if len(b) == 0:
                    # This is a blank line (probably part of a squashed merge), and we can skip with no action
                    pass

                case _:
                    # This is a nontrivial message, but does not conform to the Conventional Commit style
                    logger.info(f"version-flow skipped a non-parsable body line: {line.strip()}")

    return minimum_required_bump
