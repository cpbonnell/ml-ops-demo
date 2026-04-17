import re

from packaging.version import VERSION_PATTERN
from packaging.version import Version as PythonVersion
from semver import Version as SemanticVersion

from version_flow.types import BumpPriority, VersionSpec

version_pattern = re.compile(VERSION_PATTERN, re.VERBOSE | re.IGNORECASE)


class ProjectVersion:
    """A class representing the specific types and behaviors of a Clairity project version string."""

    _version_string_prefix = "v"
    _rc_0_suffix = "rc.0"

    DEFAULT_MINIMUM_VERSION = "v0.1.0"

    def __init__(self, version: SemanticVersion, spec: VersionSpec = VersionSpec.semver) -> None:
        """Instantiate version.

        Must be instantiated from a semver Version object. The is_semver parameter only affects the way
        this object outputs its own version string.

        Parameters
        ----------
        version: SemanticVersion
            The underlying version object that holds state and performs comparison
        spec: VersionSpec
            The specification used to define the version string
        """
        self._spec = spec
        self._version = version

        if spec == VersionSpec.semver:
            self._version_string = self._version_string_prefix + str(self._version)
        elif spec == VersionSpec.pyver:
            self._version_string = self._version_string_prefix + PythonVersion(str(self._version)).public
        else:
            raise ValueError("Invalid version spec.")

    def bump(self, priority: BumpPriority) -> "ProjectVersion":

        match self._version, priority:

            case SemanticVersion(prerelease=None), BumpPriority.from_release:
                # We only allow a from_release transition from a release version
                new_version = self._version.bump_patch().replace(prerelease=self._rc_0_suffix)

            case SemanticVersion(prerelease=None), _:
                # For a release version, all transitions other than from_release are forbidden
                raise ValueError(f"version-flow only allows a patch bump to a release version (not {priority.name})")

            case SemanticVersion(), BumpPriority.to_release:
                new_version = self._version.finalize_version()

            case SemanticVersion(), BumpPriority.major:
                new_version = self._version.bump_major().replace(prerelease=self._rc_0_suffix)

            case SemanticVersion(), BumpPriority.minor:
                new_version = self._version.bump_minor().replace(prerelease=self._rc_0_suffix)

            case SemanticVersion(), BumpPriority.patch:
                new_version = self._version.bump_patch().replace(prerelease=self._rc_0_suffix)

            case SemanticVersion(), BumpPriority.rc:
                new_version = self._version.bump_prerelease()

            case _, _:
                raise ValueError(f"Invalid bump priority: {priority}. Please use the BumpPriority enum.")

        return ProjectVersion(new_version, self._spec)

    @staticmethod
    def from_string(version: str, output_spec: VersionSpec) -> "ProjectVersion":
        """Instantiate from a string.

        May be initialized with a Python Version or a Semantic Version string, regardless of is_semver. The
        version string may be optionally started with a v. The parameter is_semver controls whether the object
        will be represented as a Semantic Version or a Python version when converted to a string.

        Parameters
        ----------
        version: str
            A string that can be converted to a Version object
        output_spec: VersionSpec
            The specification used to define the string form of the version
        """
        match = version_pattern.match(version)
        if not match:
            raise ValueError(f"Invalid version string: could not parse {version}")

        parts = match.groupdict()
        major, minor, patch = parts["release"].split(".")
        pre_letters = parts["pre_l"]
        pre_numbers = parts["pre_n"]

        new_version = SemanticVersion(
            major=major,
            minor=minor,
            patch=patch,
            prerelease=f"{pre_letters}.{pre_numbers}" if pre_letters and pre_numbers else None,
        )

        return ProjectVersion(new_version, output_spec)

    def to_string(self) -> str:
        return self._version_string

    def __str__(self) -> str:
        return self.to_string()

    def __eq__(self, other: "ProjectVersion") -> bool:
        return self._version == other._version

    def __gt__(self, other: "ProjectVersion") -> bool:
        return self._version > other._version

    def __ge__(self, other: "ProjectVersion") -> bool:
        return self._version >= other._version

    def __lt__(self, other: "ProjectVersion") -> bool:
        return self._version < other._version

    def __le__(self, other: "ProjectVersion") -> bool:
        return self._version <= other._version

    @property
    def major(self) -> int:
        """Major number of the version string (e.g. major.minor.patch-release_name.release_number)"""
        return self._version.major

    @property
    def minor(self) -> int:
        """Minor number of the version string (e.g. major.minor.patch-release_name.release_number)"""
        return self._version.minor

    @property
    def patch(self) -> int:
        """Patch number of the version string (e.g. major.minor.patch-release_name.release_number)"""
        return self._version.patch

    @property
    def prerelease_name(self) -> str | None:
        """Prerelease name of the version string (e.g. major.minor.patch-release_name.release_number)"""
        return self._version.prerelease.split(".")[0] if self._version.prerelease else None

    @property
    def prerelease_number(self) -> int | None:
        """Prerelease number of the version string (e.g. major.minor.patch-release_name.release_number)"""
        return int(self._version.prerelease.split(".")[1]) if self._version.prerelease else None
