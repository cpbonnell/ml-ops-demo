import re
import warnings
from dataclasses import dataclass, replace, field, MISSING
from typing import Self

from version_flow.types import VersionSpec, BumpPriority

DEFAULT_MINIMUM_VERSION = "v0.1.0"

_VERSION_PATTERN = r"""
    v?
    (?:
        (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
        (?P<suffix>                                          # suffix (-label.number)
            [-_\.]?
            (?P<suffix_label>[A-Za-z]+)
            [-_\.]?
            (?P<suffix_number>[0-9]+)?
        )?
    )
"""

version_pattern = re.compile(_VERSION_PATTERN, re.VERBOSE | re.IGNORECASE)


class ProdReleaseLabel(str):
    """Custom string class to represent the label on a production release.

    The main reason for this is to ensure proper comparison logic so that the production
    version without a suffix always compares greater than the version with a suffix.
    """

    def __new__(cls):
        return super().__new__(cls, "")

    def __eq__(self, other):
        if isinstance(other, ProdReleaseLabel):
            return True
        elif isinstance(other, str):
            return False
        else:
            raise ValueError(f"Cannot compare {self} to {other}")

    def __gt__(self, other):
        if isinstance(other, ProdReleaseLabel):
            return False
        elif isinstance(other, str):
            return True
        else:
            raise ValueError(f"Cannot compare {self} to {other}")

    def __lt__(self, other):
        return not self == other and not self > other

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def __repr__(self):
        return "ProdReleaseLabel()"


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int
    suffix_label: str = field(default_factory=ProdReleaseLabel)
    suffix_number: int = field(default=0)

    # Internal Fields
    _default_output_spec: VersionSpec = field(default=VersionSpec.semver, repr=False, compare=False)
    _prefix: str = field(default="v", init=False, repr=False, hash=False)

    @classmethod
    def from_string(cls, version_string: str, default_output_spec: VersionSpec | None = None) -> Self:
        matched_pattern = version_pattern.match(version_string)

        if not matched_pattern:
            raise ValueError(f"Invalid version string: {version_string}")

        parts = matched_pattern.groupdict()
        major, minor, patch = parts["release"].split(".")
        pre_label = parts.get("suffix_label")
        pre_numbers = parts.get("suffix_number")
        if default_output_spec is None:
            default_output_spec = MISSING

        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            suffix_label=pre_label or ProdReleaseLabel(),
            suffix_number=int(pre_numbers) if pre_numbers else 0,
            _default_output_spec=default_output_spec,
        )

    def to_string(self, spec: VersionSpec | None = None) -> str:
        if spec is None:
            spec = self._default_output_spec

        match spec, self.suffix_label, self.suffix_number:
            case _, ProdReleaseLabel(), _:
                suffix = ""
            case VersionSpec.pyver, str(label), int(number):
                suffix = f"{label}{number}"
            case VersionSpec.semver, str(label), int(number):
                suffix = f"-{label}.{number}"
            case _, _, _:
                raise ValueError(f"Could not construct a suffix for version {self} with spec {spec}.")

        return f"{self._prefix}{self.major}.{self.minor}.{self.patch}{suffix}"

    def bump(self, priority: BumpPriority, label: str | None) -> Self:

        # If the current branch has a different label than the version being bumped, reset the
        # version to this branch's label before performing the specified bump.
        label = label or ProdReleaseLabel()
        if label != self.suffix_label:
            current_version = replace(self, suffix_label=label, suffix_number=0)
            if priority == BumpPriority.rc:
                priority = BumpPriority.patch
                warnings.warn(
                    "When changing the suffix label, the bump priority must be at least a patch bump. "
                    "version-flow will automatically upgrade this rc bump to a patch bump."
                )
        else:
            current_version = self

        match current_version, priority:

            case Version(), BumpPriority.from_release:
                warnings.warn(
                    "The 'from_release' BumpPriority is deprecated for  the FDA Git Flow. version-flow will "
                    "perform a patch bump instead.",
                    DeprecationWarning,
                )
                return self.bump(BumpPriority.patch, label)

            case Version(), BumpPriority.to_release:
                warnings.warn(
                    "The 'to_release' BumpPriority is deprecated for  the FDA Git Flow. version-flow will "
                    "perform a patch bump instead.",
                    DeprecationWarning,
                )
                return self.bump(BumpPriority.patch, label)

            case Version(major=int(m)) as v, BumpPriority.major:
                return replace(v, major=m + 1, minor=0, patch=0, suffix_number=0)

            case Version(minor=int(m)) as v, BumpPriority.minor:
                return replace(v, minor=m + 1, patch=0, suffix_number=0)

            case Version(patch=int(p)) as v, BumpPriority.patch:
                return replace(v, patch=p + 1, suffix_number=0)

            case Version(suffix_label=ProdReleaseLabel()) as v, BumpPriority.rc:
                warnings.warn(
                    f"Cannot bump the suffix number of the production release: {v}. Performing a patch bump instead."
                )
                return self.bump(BumpPriority.patch, label)

            case Version(suffix_number=int(prn)) as v, BumpPriority.rc:
                return replace(v, suffix_number=prn + 1)

            case _, _:
                raise ValueError(f"Invalid bump priority: {priority}. Please use the BumpPriority enum.")
