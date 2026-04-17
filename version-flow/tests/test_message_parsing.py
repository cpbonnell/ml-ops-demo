import pytest

from version_flow.message_parsing import get_bump_from_messages
from version_flow.types import BumpPriority, CommitType


@pytest.mark.parametrize(
    "types, use_scope, use_breaking, use_alt_breaking, expected_bump",
    [
        # Examples testing all explicitly supported topics
        ([CommitType.build], False, False, False, BumpPriority.patch),
        ([CommitType.chore], False, False, False, BumpPriority.patch),
        ([CommitType.ci], False, False, False, BumpPriority.rc),
        ([CommitType.docs], False, False, False, BumpPriority.rc),
        ([CommitType.feat], False, False, False, BumpPriority.minor),
        ([CommitType.fix], False, False, False, BumpPriority.patch),
        ([CommitType.perf], False, False, False, BumpPriority.patch),
        ([CommitType.refactor], False, False, False, BumpPriority.patch),
        ([CommitType.revert], False, False, False, BumpPriority.patch),
        ([CommitType.style], False, False, False, BumpPriority.rc),
        ([CommitType.test], False, False, False, BumpPriority.patch),
        ([CommitType.unknown], False, False, False, BumpPriority.rc),
        # Some examples for testing messages with scope and breaking changes
        ([CommitType.docs], False, False, False, BumpPriority.rc),
        ([CommitType.docs], True, False, False, BumpPriority.rc),
        ([CommitType.docs], False, True, False, BumpPriority.major),
        ([CommitType.docs], True, True, False, BumpPriority.major),
        ([CommitType.feat], True, True, True, BumpPriority.major),
        ([CommitType.feat], True, False, True, BumpPriority.major),
        # Some examples for testing messages docstring topics
        ([CommitType.feat, CommitType.unknown, CommitType.docs], False, False, False, BumpPriority.minor),
        ([CommitType.feat, CommitType.feat, CommitType.feat], True, False, False, BumpPriority.minor),
        ([CommitType.docs, CommitType.style, CommitType.ci], False, True, False, BumpPriority.major),
        ([CommitType.docs, CommitType.style, CommitType.ci], False, False, True, BumpPriority.major),
    ],
)
def test_get_bump_from_messages(
    types,
    use_scope,
    use_breaking,
    use_alt_breaking,
    expected_bump,
    conventional_commit_message,
    squashed_commit_message,
):

    individual_messages = [
        conventional_commit_message(
            t,
            scope=use_scope,
            breaking=use_breaking,
            alt_breaking=use_alt_breaking,
        )
        for t in types
    ]
    squashed_message = squashed_commit_message(individual_messages)

    assert get_bump_from_messages(individual_messages) == expected_bump
    assert get_bump_from_messages(squashed_message) == expected_bump
