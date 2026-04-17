import pytest
from contextlib import nullcontext
from version_flow.project_version import ProjectVersion
from version_flow.version import Version, ProdReleaseLabel
from version_flow.types import BumpPriority, VersionSpec
import operator as op


@pytest.mark.parametrize(
    "starting, bump, ending, spec, context_manager",
    [
        # Cases to test each bump priority from an RC
        ("v1.2.3-rc.4", BumpPriority.rc, "v1.2.3-rc.5", VersionSpec.semver, nullcontext()),
        ("v1.2.3-rc.4", BumpPriority.patch, "v1.2.4-rc.0", VersionSpec.semver, nullcontext()),
        ("v1.2.3-rc.4", BumpPriority.minor, "v1.3.0-rc.0", VersionSpec.semver, nullcontext()),
        ("v1.2.3-rc.4", BumpPriority.major, "v2.0.0-rc.0", VersionSpec.semver, nullcontext()),
        ("v1.2.3-rc.4", BumpPriority.to_release, "v1.2.3", VersionSpec.semver, nullcontext()),
        ("v1.2.3-rc.4", BumpPriority.from_release, "v2.0.0-rc.0", VersionSpec.semver, pytest.raises(ValueError)),
        # Cases to test each bump from a Release
        ("v1.2.3", BumpPriority.rc, "v1.2.4-rc.0", VersionSpec.semver, pytest.raises(ValueError)),
        ("v1.2.3", BumpPriority.patch, "v1.2.4-rc.0", VersionSpec.semver, pytest.raises(ValueError)),
        ("v1.2.3", BumpPriority.minor, "v1.3.0-rc.0", VersionSpec.semver, pytest.raises(ValueError)),
        ("v1.2.3", BumpPriority.major, "v2.0.0-rc.0", VersionSpec.semver, pytest.raises(ValueError)),
        ("v1.2.3", BumpPriority.to_release, "v1.2.3", VersionSpec.semver, pytest.raises(ValueError)),
        ("v1.2.3", BumpPriority.from_release, "v1.2.4-rc.0", VersionSpec.semver, nullcontext()),
        # Case to test conversion from SemVer to PyVer
        ("v1.2.3-rc4", BumpPriority.major, "v2.0.0rc0", VersionSpec.pyver, nullcontext()),
        # Case to test conversion from PyVer to SemVer
        ("v1.2.3rc4", BumpPriority.major, "v2.0.0-rc.0", VersionSpec.semver, nullcontext()),
    ],
)
def test_project_version(starting: str, bump: BumpPriority, ending: str, spec: VersionSpec, context_manager):
    v_starting = ProjectVersion.from_string(starting, spec)
    v_ending = ProjectVersion.from_string(ending, spec)

    with context_manager:
        v_bumped = v_starting.bump(bump)
        assert v_bumped.to_string() == ending
        assert v_bumped == v_ending


@pytest.mark.parametrize(
    "specification_string, expected_spec",
    [
        ("semver", VersionSpec.semver),
        ("pyver", VersionSpec.pyver),
        ("pep440", VersionSpec.pyver),
    ],
)
def test_version_spec_from_string(specification_string, expected_spec):
    assert VersionSpec.from_string(specification_string) == expected_spec


@pytest.mark.parametrize(
    "version_string, expected_parts",
    [
        ("1.2.3", (1, 2, 3, None, None)),
        ("1.2.3-rc.4", (1, 2, 3, "rc", 4)),
        ("1.2.3-rc4", (1, 2, 3, "rc", 4)),
    ],
)
def test_project_version_parts(version_string: str, expected_parts: tuple[int, int, int, str | None, int | None]):

    v = ProjectVersion.from_string(version_string, VersionSpec.semver)
    assert v.major == expected_parts[0]
    assert v.minor == expected_parts[1]
    assert v.patch == expected_parts[2]
    assert v.prerelease_name == expected_parts[3]
    assert v.prerelease_number == expected_parts[4]


# ========== Tests for New Version Class ==========
@pytest.mark.parametrize(
    "version_string, expected_parts",
    [
        ("1.2.3", (1, 2, 3, ProdReleaseLabel(), 0)),
        ("1.2.3-rc.4", (1, 2, 3, "rc", 4)),
        ("1.2.3rc4", (1, 2, 3, "rc", 4)),
    ],
)
def test_version_parts(version_string: str, expected_parts: tuple[int, int, int, str | None, int | None]):

    v = Version.from_string(version_string)
    assert v.major == expected_parts[0]
    assert v.minor == expected_parts[1]
    assert v.patch == expected_parts[2]
    assert v.suffix_label == expected_parts[3]
    assert v.suffix_number == expected_parts[4]


@pytest.mark.parametrize(
    "a, b, is_equal, is_less_than",
    [
        pytest.param("1.2.3", "1.2.3", True, False, id="Equality of production releases"),
        pytest.param("1.2.3-rc.4", "1.2.3rc4", True, False, id="Equality of named branches"),
        pytest.param("1.2.3-rc.0", "1.2.3", False, True, id="Suffix vs non-suffix"),
        pytest.param("1.2.3-rc.0", "1.2.3-rc.1", False, True, id="Suffix number"),
        pytest.param("1.2.3-a.0", "1.2.3-b.0", False, True, id="Suffix label"),
        pytest.param("1.2.3-a.0", "1.2.4-a.0", False, True, id="Patch"),
        pytest.param("1.2.3-a.0", "1.3.3-a.0", False, True, id="Minor"),
        pytest.param("1.2.3-a.0", "2.2.3-a.0", False, True, id="Major"),
    ],
)
def test_comparisons(a: str, b: str, is_equal: bool, is_less_than: bool):
    left = Version.from_string(a)
    right = Version.from_string(b)

    # Truth value when comparing left to right
    expected_operator_truth_values = {
        op.eq: is_equal,
        op.ne: not is_equal,
        op.lt: is_less_than,
        op.le: is_less_than or is_equal,
        op.gt: not is_equal and not is_less_than,
        op.ge: is_equal or not is_less_than,
    }

    # Truth value when comparing right to left
    expected_reverse_order_truth_values = {
        op.eq: is_equal,
        op.ne: not is_equal,
        op.lt: not is_equal and not is_less_than,
        op.le: not is_less_than or is_equal,
        op.gt: is_less_than,
        op.ge: is_less_than or is_equal,
    }

    for comp in expected_operator_truth_values.keys():
        forward = expected_operator_truth_values[comp]
        reverse = expected_reverse_order_truth_values[comp]
        assert comp(left, right) == forward, f"Expected {comp}({left}, {right}) to be {forward}"
        assert comp(right, left) == reverse, f"Expected {comp}({right}, {left}) to be {reverse}"


@pytest.mark.parametrize(
    "starting, bump, label, ending, spec, context",
    # fmt: off
    [
        # Cases to test each bump priority from an RC
        ("v1.2.3-rc.4", BumpPriority.rc, "rc", "v1.2.3-rc.5", VersionSpec.semver, nullcontext()),
        ("v1.2.3-dev.4", BumpPriority.patch, "dev", "v1.2.4-dev.0", VersionSpec.semver, nullcontext()),
        ("v1.2.3-draco.4", BumpPriority.minor, "draco", "v1.3.0-draco.0", VersionSpec.semver, nullcontext()),
        ("v1.2.3-cetus.4", BumpPriority.major, "cetus", "v2.0.0-cetus.0", VersionSpec.semver, nullcontext()),
        ("v1.2.3-a.4", BumpPriority.to_release, "a", "v1.2.4-a.0", VersionSpec.semver,pytest.warns(DeprecationWarning)),
        ("v1.2.3-b.4", BumpPriority.from_release, "b", "v1.2.4-b.0", VersionSpec.semver, pytest.warns(DeprecationWarning)),
        # Cases to test each bump from a Release
        ("v1.2.3", BumpPriority.rc, None, "v1.2.4", VersionSpec.semver, pytest.warns()),
        ("v1.2.3", BumpPriority.patch, None, "v1.2.4", VersionSpec.semver, nullcontext()),
        ("v1.2.3", BumpPriority.minor, None, "v1.3.0", VersionSpec.semver, nullcontext()),
        ("v1.2.3", BumpPriority.major, None, "v2.0.0", VersionSpec.semver, nullcontext()),
        ("v1.2.3", BumpPriority.to_release, None, "v1.2.4", VersionSpec.semver, pytest.warns(DeprecationWarning)),
        ("v1.2.3", BumpPriority.from_release, None, "v1.2.4", VersionSpec.semver, pytest.warns(DeprecationWarning)),
        # Case to test conversion from SemVer to PyVer
        ("v1.2.3-rc.4", BumpPriority.major, "rc", "v2.0.0rc0", VersionSpec.pyver, nullcontext()),
        # Case to test conversion from PyVer to SemVer
        ("v1.2.3rc4", BumpPriority.major, "rc", "v2.0.0-rc.0", VersionSpec.semver, nullcontext()),
        # Cases to test version bump when changing label
        ("v1.2.3-rc.4", BumpPriority.rc, "dev", "v1.2.4-dev.0", VersionSpec.semver, pytest.warns()),
        ("v1.2.3-rc.4", BumpPriority.patch, "dev", "v1.2.4-dev.0", VersionSpec.semver, nullcontext()),
        ("v1.2.3", BumpPriority.rc, "dev", "v1.2.4-dev.0", VersionSpec.semver, pytest.warns()),
        ("v1.2.3", BumpPriority.patch, "dev", "v1.2.4-dev.0", VersionSpec.semver, nullcontext()),
        ("v1.2.3-rc.4", BumpPriority.rc, None, "v1.2.4", VersionSpec.semver, pytest.warns()),
        ("v1.2.3-rc.4", BumpPriority.patch, None, "v1.2.4", VersionSpec.semver, nullcontext()),
    ],
    # fmt: on
)
def test_version_bump(starting: str, bump: BumpPriority, label: str | None, ending: str, spec: VersionSpec, context):
    v_starting = Version.from_string(starting)
    v_ending = Version.from_string(ending)

    with context:
        v_bumped = v_starting.bump(bump, label)
        assert v_bumped.to_string(spec) == ending
        assert v_bumped == v_ending
