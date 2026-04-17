# version-flow

A package for bumping version based on commit messages.

## Getting Help

For help with `version-flow`, please contact Christian Bonnell via email, direct
message through Slack, or "@" tag him in your Slack chat. For some common
issues, consult the "Common Issues" in the How-To Guides section.

Christian Bonnell cbonnell@clairity.com

## Why version-flow?

This package is intended to be a drop-in replacement for the old
'version_flow.sh' scripts in Clairity's standard CI/CD workflow. It also adds
some new functionality necessary to bring the CI/CD workflow into compliance
with
["Ozarks Software Configuration Management Plan (DOC-543)"](https://clairity.greenlight.guru/documents/58e862d6-89e7-4a40-b1b3-84aaf3999e2f/revision/8ab8f834-0125-41a7-90a1-d80157f080ae/view),
which can be found in GreenlightGuru. Discussion around the requirements and
design of the package can be found
in [RFC-1049](https://clairityadmin.atlassian.net/wiki/spaces/Eng/pages/836665346/RFC-1049+Replacement+for+version_flow.sh).

## How this documentation is organized

A high level overview of the sections in this document is useful for quickly
finding the information that is relevant to your needs. The main sections of the
document (in order) are:

* **Tutorials** -- A quick set of steps to accomplish a specific common task.
  Using a tutorial requires little or no prior knowledge of the `version-flow`
  tool or Clairity's CI/CD process.
* **How-To Guides** -- These guides are recipies for using specific parts of
  `version-flow`'s functionality. They guide you through the trade-offs and
  decisions you will need to make, and how to configure the tool accordingly.
  They require some prior knowledge of how `version-flow` works.
* **Topic Guides** -- These sections discuss key concepts at a fairly high
  level, and provide useful information about the CI/CD process and the tool's
  implementation.
* **Reference Guide** -- Complete documentation of all `version-flow`'s
  configuration options and command line arguments.

# Tutorials

## Set up a new Python Project

This tutorial covers how to set up `version-flow` in a new project that contains
only a Python library. However, Clairity's codebase includes a large number of
Python projects that are already configured to use `version_flow.
sh`. All of these steps are relevant for converting an existing project, but if
you are converting an existing project please consult the "Converting an
Existing Project" article in the How-To section.

1. Look up the latest release version of `version-flow` by reviewing its
   [GitHub Tags](https://github.com/clairity-inc/version-flow/tags)
   and finding the most recent one that does not have a "-rc" suffix. For
   example, "v0.4.0".
2. Add a "docker/image" section to your "version_flow" job. The container image
   should be specified like the example below, except use the version string you
   looked up in step 1 instead of the "v0.4.0" after the colon on the container
   string:
    ```yaml
    jobs:
      version_flow:
        container:
          - image: 629478721045.dkr.ecr.us-east-2.amazonaws.com/clairity/version-flow:v0.4.0
    ```
3. Add an invocation of `version-flow` to the "steps/run/command" section of the
   "version_flow" job. An example of the resulting ".circleci/config.yaml"
   is shown below:
    ```yaml
    jobs:
      version_flow:
        container:
          - image: 629478721045.dkr.ecr.us-east-2.amazonaws.com/clairity/version-flow:v0.4.0
        steps:
          - add_ssh_keys
          - checkout
          - run:
              name: Running Version Flow
              command: version-flow .
    ```
4. Add a configuration section to the "pyproject.toml" file. The minimum
   configuration involves adding a single `tool.version-flow` section header,
   and then an entry indicating the `version_specification`, with a value of
   either "semver" or "pyver". You may add other options as well, as documented
   in the Reference Guide. The `tool.ßversion-flow` section may be placed
   anywhere in the document, as long as it is a top-level section. An example of
   the minimum specification is shown below.
    ```toml
    [tool.version-flow]
    version_specification = "semver"
    ```
5. You will want to occasionally check to see if newer versions of version-flow
   have been released and update your config.yaml script to include the latest
   changes.

## Set up a new R Project

This tutorial covers setting up version-flow for an R project. It does not cover
the process of setting up a new R project in general, only the addition of
version-flow.

1. Identify all the files in your project that you want the tool to
   automatically update when it is run. This might include a "DESCRIPTION"
   file, or and ".Rproj" file.
2. Add a TOML configuration file to the root directory of your project. The name
   is not important, but you will need to specify the name to a CI/CD script
   later in this tutorial. For simplicity, this tutorial will use the name
   `rproject.toml`. Once you have created this file, open it an add a section to
   the file that looks like this (but add your own files to the list of files to
   update):
   ```toml
    [tool.version-flow]
    version_specification = "semver"
    files_to_update = ["DESCRIPTION", "mylib.Rproj"]
    ```
3. Look up the latest release version of `version-flow` by reviewing its
   [GitHub Tags](https://github.com/clairity-inc/version-flow/tags)
   and finding the most recent one that does not have a "-rc" suffix. For
   example, "v0.4.0".
4. Open the ".circleci/config.yaml" file in your project, and add a
   "docker/image" section to your "version_flow" job. The container image should
   be specified like the example below, except use the version string you looked
   up in step 1 instead of the "v0.4.0" after the colon on the container string:
    ```yaml
    jobs:
      version_flow:
        container:
          - image: 629478721045.dkr.ecr.us-east-2.amazonaws.com/clairity/version-flow:v0.4.0
    ```
5. Add an invocation of `version-flow` to the "steps/run/command" section of the
   "version_flow" job. The only parameter you will need to pass to
   `version-flow` is the name of the YAML file you created in step 2. The name
   should be supplied as a relative file path from the root of the project's
   repo. An example of the resulting ".circleci/config.yaml"
   is shown below:
    ```yaml
    jobs:
      version_flow:
        container:
          - image: 629478721045.dkr.ecr.us-east-2.amazonaws.com/clairity/version-flow:v0.4.0
        steps:
          - add_ssh_keys
          - checkout
          - run:
              name: Running Version Flow
              command: version-flow rproject.toml
    ```
6. You will want to occasionally check to see if newer versions of version-flow
   have been released and update your config.yaml script to include the latest
   changes.

# How-To Guides

## Local development and testing

Local development is similar to other Clairity Inc. projects. After cloning the
repository, most required tasks can be performed by use of various commands (
build targets) in the Makefile. These require no setup other than the normal
steps covered during your onboarding.

For example, after editing some code, you can export AWS credentials to
environment variable and run the tests locally:

```shell
asw sso login --profile delivery
aws_env delivery
make test
make test-pdb
```

## Set up a Monorepo Sub-Project

This guide covers how to configure `version-flow` for a monorepo where multiple
sub-projects live in the same Git repository, each with its own `pyproject.toml`
and independent version lifecycle.

### Overview

version-flow supports monorepos where each sub-project can be versioned
independently. Each sub-project gets its own `pyproject.toml` with version-flow
configuration, its own version tags (prefixed with a project name), and only
commits that touch its owned paths influence its version bumps.

### 1. Add version-flow configuration to the sub-project

Create or update the `pyproject.toml` in your sub-project directory. In addition
to the standard version-flow options, you will need to set two monorepo-specific
options:

- **`project_name_in_tag`**: A unique identifier for this sub-project. It
  changes the tag format from `v1.0.0-rc.3` to
  `my-data-pipeline/v1.0.0-rc.3`. This prevents tag collisions between
  sub-projects in the same repository. Each sub-project must have a unique
  value.
- **`owned_paths`**: A list of directory paths (relative to the repository root)
  that belong to this sub-project. When version-flow reads commit history to
  determine the bump magnitude, only commits that touched files under these
  paths are considered. If `owned_paths` is not configured, all commits in the
  repo influence the bump — which defeats the purpose of independent versioning.
  Include your sub-project's own directory, plus any shared code it depends on.

Note that these two path options use different bases: `owned_paths` is relative
to the **repository root** (so version-flow can match paths in the commit
history), while `files_to_update` is relative to the **project directory** (the
directory containing the sub-project's `pyproject.toml`).

A complete example:

```toml
[project]
version = "1.0.0-rc.3"

[tool.version-flow]
version_specification = "semver"
git_branch_strategy = "fda_git_flow"
project_name_in_tag = "my-data-pipeline"
owned_paths = ["services/my-data-pipeline", "shared/common-lib"]
files_to_update = ["src/__init__.py"]

[tool.version-flow.managed-branches]
trunk = "main"
release = "release"
```

### 2. Run version-flow for the sub-project

Point version-flow at the sub-project's directory (the one containing its
`pyproject.toml`):

```bash
version-flow ./services/my-data-pipeline
```

### 3. Update CI tag filters

Because monorepo tags include the project name as a prefix (e.g.
`my-data-pipeline/v1.0.0-rc.3`), tag-triggered CI pipelines need their filter
regex updated to match the new format. For example, in CircleCI:

```yaml
filters:
  tags:
    only: /^my-data-pipeline\/v(\d+\.){2}\d+(|-?\w+\.?\d+)$/
  branches:
    ignore: /.*/
```

### 4. Gotchas

- **Version string replacement** (`files_to_update`) does a naive string
  replace of the old version with the new version. Keep listed files scoped to
  your sub-project to avoid unintended replacements in other sub-projects.
- If `owned_paths` is **not** configured, all commits in the repo influence
  the bump priority — so you almost certainly want to set it in a monorepo.
- The tag format uses `/` as a separator (`my-data-pipeline/v1.0.0`), which is
  compatible with standard Git tooling.
- The automated release PR title will include the project name (e.g.
  "Release: my-data-pipeline") so that each sub-project gets its own release PR.

## Troubleshooting Common Issues

### The tagged version does not match pyproject.toml

You may encounter an error like the following when merging a feature branch onto
the `trunk` branch:

```
ValueError : The version 0.1.1rc3 from pyproject.toml does not match the most 
recent tagged version 0.1.1rc4. Cannot proceed with version-flow.Please 
manually tag the repository, or adjust the version string in pyproject.toml.
```

This occurs because the "current version" that is listed in your repository's
pyproject.toml does not match the last version string that your branch was
tagged with. When this happens there is no way for version-flow to determine
what the current version of the repository is, and so it cannot correct the
situation.

To resolve the situation, the easiest method is to create a pull request that
changes all the version strings in the repository to match the most recently
tagged version. If you feel like getting more involved with Git, you could
instead perform a manual tag of the repository so match the version string in
pyproject.toml

### The version string is not updated in some files

The version-flow tool has an optional configuration that allows you to specify
additional files that need to have a version update whenever version-flow
updates pyproject.toml. If one of these files is not updating, the usual cause
is that the version string in that file is not an exact match for the
authoritative version string in pyproject.toml. The update that version-flow
performs on all files in the `files_to_update` list is a simple copy-replace
operation. So the version string in all additional files must be an exact copy.

To resolve this issue, check all the version strings that are not updating, and
ensure they match what is in pyproject.toml. It is easy to think the versions
match because the numbers line up, but there may be a typo such as an extra
space. It may also be the case that the version string in the file is a
different format than the authoritative version (e.g. one is pyver, one is
semver).

Once you have identified any inconsistencies, submit a PR with the version
string in the additional files changed to match the version string that is in
pyproject.toml.

### Missing GH_TOKEN environment variable

If you see a failed run of version flow, and the logs contain an error that
looks similar to the following

```
ValueError: No GitHub Token configured. Please check the runtime context for 
the GH_TOKEN environment variable and try again.
```

This error is because version-flow needs a GitHub application token in order to
open a "new release PR". If version-flow fails at this stage, it is likely that
it did, in fact, increment the version string of your project and also tag the
commit, since raw Git authentication is different than GitHub specific
authentication.

**Prerequisites**
Solving this issue will need admin privileges in CircleCI, so if you aren't a
CircleCI admin then just contact a senior member of the Engineering team, and
let them know that your repository needs to have the GH_TOKEN environment
variable cloned into the project workspace.

**Steps to Resolve**
If you are a CircleCi admin, then you can use the following process to add the
correct GH_TOKEN to the repository project:

1. Open the [CircleCI console](app.circleci.com)
   and click on the clairity-inc organization.
2. Once you are on the organization's landing page, select the "Projects" tile
   from the nav bar on the left side of the page.
3. Scroll through the list of Projects until you see the one you need to
   configure the GH_TOKEN for.
4. The list tile for your project will have a context menu button (with three
   dots) the far right. Click the context menu and select "Project settings".
5. Once the Project Settings page has loaded, you will see a new navigation bar
   on the left of your screen.
6. Select the "Environment Variables" tile.
7. Here you will see a list of project specific environment variables (if any)
   that are injected into the runtime context of any CircleCI tasks that run for
   that project. Since you were encountering the above error, you should not see
   any entries for GH_TOKEN.
8. To add an entry for GH_TOKEN, you will want to click the
   "Import Variables" button. This will bring up a popup window with a drop-down
   box control that is populated with other projects in the organization. There
   will also be an "Import Variables" button at the bottom of the popup window,
   but that button will be grayed out.
9. Select one of the other projects (such as the `version-flow`
   project) that has ONLY the environment variable GH_TOKEN, but no others.
   The "Import Variables" button should now become available.
10. Clicking the "Import Variables" button closes out the popup window.

Now the next time `version-flow` runs for that repository, it should have the
token it needs to make changes to the repository.

# Topic Guides

## Conventional Commit Messages

The [Conventional Commit](https://www.conventionalcommits.org/en/v1.0.0/)
specification is a set of instructions for constructing Git commit messages that
follow a predictable convention (hence the name), which is easy for CI/CD
applications to parse. The version-flow tool is able to read the commit history
of any feature branch that is being merged and automatically determine how to
increment the version of the project accordingly. It does this by considering
the "topic" fields of the conventional commits, and conducting the smallest
version increment that is allowable based on the level of change indicated by
the topics (see the chart below). version-flow is able to read and parse these
messages for all commits in the pull request even if you perform a squash merge.

Since the specification is well documented elsewhere, we will only provide a
quick visual reference here:

**Fields of a Conventional Commit**

```topic (scope): description```

**Recognized Topics**

| Required Increment | Topics                                          |
|--------------------|-------------------------------------------------|
| Release Candidate  | ci, docs, style                                 |
| Patch              | build, chore, fix, perf, refactor, revert, test |
| Minor              | feat                                            |
| Major              | any topic followed by a "!" character           |


## Flow Logic

### Legacy Trunk Flow
This is the original logic of the version-flow application, mimicking 
directly the logic of the older "version_flow.sh" that it replaced. The 
logic only runs when feature branches are merged to the trunk branch, or 
when a trunk branch is merged to the release branch.

The general flow when feature branches are merged to trunk is as follows:
1. Determine the last version string tagged on the trunk branch, and ensure 
   it matches the version string in pyproject.toml. Raise if it doesn't
2. Read commit messages in the feature branch, and determine a commit 
   magnitude (will always be at least a suffix number bump)
3. Bump the version, make changes to all required files and commit, tag the 
   commit, and push
4. Ensure that at least one "new release" pull request is open

The general flow when the trunk branch is merged to release is:
1. Perform a "to_release" bump, that drops the suffix of whatever version 
   was the last one that trunk branch was tagged with
2. Make the relevant changes to all files containing the version string, 
   tag, commit and push.
3. Switch branches back to the trunk branch, cherry-pick the version bump 
   commit from the release branch
4. Perform a "from_release" bump to the version inherited from the 
   cherry-pick, which involves bumping the patch version, and then adding a 
   suffix with the appropriate suffix name and a suffix number of 0
5. Commit, tag and push changes to main
6. Ensure that at least one "new release" pull request is open

### FDA Git Flow
This flow is intended to support a modified version of the standard Git Flow,
used by our projects that require complex branch management to meet FDA 
requirements. The workflow is different from Legacy Flow and Trunk Flow in 
that a single run of the version-flow logic only affects the branch that it 
runs on.

The general process of the logic is as follows:
1. Determine the "most recent tagged version" of the head commit (this is, 
   the highest tagged version of the parent branches).
2. Read all commit messages from parent commits that have been added since 
   the last tag, and determine the magnitude of the bump necessary. The bump 
   performed will always be at least a suffix number bump for a non-merge 
   event or for a feature branch merge, and will always be at least a patch 
   bump for any merge between named branches.
3. Perform the necessary bump to the most recently tagged version
4. Write the new version to all files that contain the version string, 
   commit the changes, and tag that commit with the version string
5. All changes are pushed, and then the application exits

# Reference Guide

## Configuration in pyproject.toml

All configuration for the `version-flow` tool may be set in the pyproject. toml
file, in the `[tool.version-flow]` section. This section may take the following
fields:

* **version_string** -- The string representing the current version of the
  project. The tool will default to trying to read a version string from the
  `tool.poetry.version` key in pyproject.toml. If it does not find one, it will
  fall back to looking the `project.version` key as used by `uv` and some other
  older build tools.
* **version_specification** -- REQUIRED. One of `["semver", "pyver", "pep440"]`
  where "pyver" and "pep440" are identical in function. This parameter will set
  the schema that is used for the output of any updated version string.
* **git_branch_strategy** -- One of `["trunk_flow", "fda_git_flow"]`. Indicates
  which strategy for branches will be used for determining version bumps when
  merging to other branches. Most projects will use "trunk_flow".
* **files_to_update** -- A list of strings. When `version-flow` sets the updated
  version in pyproject.toml, it will also search the listed files for any text
  matching the old version string, and replace it with the new version string.
  All file paths are relative to the root of the project directory.
* **project_name_in_tag** -- A string used to prefix version tags for monorepo
  sub-projects. When set, tags take the form `<project_name_in_tag>/v1.2.3`
  instead of `v1.2.3`, and only tags matching this prefix are considered when
  determining the most recent version. Each sub-project in a monorepo must have
  a unique value. Omit this option for single-project repositories.
* **owned_paths** -- A list of directory paths relative to the repository root.
  When set, only commits that modified files under these paths are considered
  when determining the version bump magnitude. This allows independent
  versioning of sub-projects in a monorepo. If not set, all commits in the
  repository influence the bump.
* **trunk_branch** -- Default "main". The name of the Git branch being used as
  the trunk (the branch where feature branches are merged).
* **staging_branch** -- Default "staging". The name of the branch used for
  staging.
* **release_branch** -- Default "release". The name of the branch where the
  trunk is merged to start the release process.

Example configuration:

```toml
[tool.poetry]
version = "v0.1.0-rc.1"
# ...

[tool.version-flow]
git_branch_strategy = "trunk_flow"
version_specification = "semver"
files_to_update = ["workbench/__init__.py"]
trunk_branch = "main"
release_branch = "release"
```

## Configuration in CircleCI

The `version-flow` utility is deployed as docker image in Clairity's Delivery
ECR. This image can be used as the base for a CI/CD step in your project's
CircleCI process. This step should be configured automatically trigger whenever
a pull request is merged in GitHub.

To properly configure the `version-flow` tool in CircleCI, you will need to add
two different sections to your config file. The first will be a new section
inside the top-level header `jobs`. This will tell CircleCI how to execute
version-flow in its workflows, specifying the docker image to execute and
command line arguments.

The second section you must add will be under the top-level header
`workflows`. Workflows will have a section for each chain of jobs that runs on
your project. All workflows that need the version_flow job should include it
with appropriate job dependencies; by default CircleCI executes all jobs in
parallel. Typically, version-flow runs after a successful test, since we do not
want to increment the project's version on a bad build. version-flow is also
constrained to run on certain branches

A typical example of the `version-flow` sections of a CircleCI config is shown
below. The order of sections does matter, but the full configuration of a
project in CircleCI is beyond the scope of this document so the other required
sections for a Clairity project are here omitted.

```yaml
jobs:
  # ...
  version_flow:
    docker:
      - image: 629478721045.dkr.ecr.us-east-2.amazonaws.com/clairity/version-flow:v0.7.2-rc.2
    steps:
      - add_ssh_keys
      - checkout
      - run:
          name: Running Version Flow
          command: |
            version-flow ./python/python_project_root_dir

workflows:
  version: 2
  main:
    jobs:
      # ... 
      - version_flow:
          context: delivery
          requires:
            - test
          filters:
            branches:
              only:
                - release
                - main
```

## Advanced Branch Naming

The fda_git_flow branching strategy allows for more advanced configuration of
branch names, the role those branches serve, and how the branches are identified
in branch-specific version strings.

The trunk_flow strategy allows for only a single "trunk" branch and a single
"release" branch. All other branches are considered feature branches, and a
repository may have as many active feature branches as desired.

The fda_git_flow, on the other hand, allows any number of
"release-candidate" and "named-release" branches. The repository is still
limited to only a single "trunk" branch, and a single "release" branch. And as
with trunk_flow, any branch that is not positively identified one of the special
branch types is treated as a "feature" branch.

**Branch Labels**

The key to understanding the advanced use of version strings in fda_git_flow is
the concept of a branch label. The label is part of the "suffix" portion of a
version string. For example, a SemVer version string might take the form "
1.2.3-label.4", or a pep440 version string would look like "1.2.3label4". In
both version strings, the digit "4" is also part of the suffix, and is known as
the "revision number". The label may be any combination of upper or lower case
letters, but may not contain any numbers or symbols. This is more strict than
what is allowed by the pure SemVer specification, but is necessary in order to
have consistent translation and parsing of both SemVer and pep440 version
strings.

**Configuration Options**

Since multiple branches could be treated as having the release candidate or
named release role, you will need to add the configuration section
`tool.version-flow.managed-branches` when you configure your repository to use
the fda_git_flow branch strategy. This section allows two keys, "trunk" and
"release" to be specified. The values of these keys must be a single string
literal that exactly matches the name of a branch in your repository. The
"release" branch will be considered the clean, authoritative production branch,
and version strings tagged on that branch will not have suffix, only the raw
major.minor.patch numbers. Either key may be alternatively be specified as 
top level keys in the `tool.version-flow` as described in the 
[configurations article](#configuration-in-pyprojecttoml), and if not 
supplied will take the default values documented there.

The `tool.version-flow.managed-branches` table also allows two optional
sub-tables, "release-candidate" and "named-release". The structure of both
sections is the same: a set of values matching a branch label to one or more
string literals. The string literals are regular expressions that are used to
identify which branches should be given version strings using that label in the
suffix. If a branch could potentially match more than one pattern, it will be
assigned to the first pattern it matches. Matches are checked in the
alphabetical order by label in the "named-release" section first, and then
alphabetical order by label in "release-candidate."

Only one branch is allowed to have any particular label at a given time. 
This means that if one branch is using a particular label because it matches 
a pattern (e.g. "release/2020-01-01" could be given the label "rc"), that 
branch must be deleted before another branch (such as "release/2021-01-01") 
can be created. If it is not deleted, then version-flow runs for both 
branches will start failing and require a developer to manually delete one 
of the branches.

Both "release-condidate" and "named-release" branches are treated the same when
it comes to forming the version string, but "named-release" branches will be
treated the same as the "release" branch for the sake of merging rules.

Below is an example of one possible configuration of `managed-branches`. Note
that the strings must all be given using single quotes in order to be literal
strings.

```toml
[tool.version-flow.managed-branches]
trunk = 'main'         # Will always have the label "dev"
release = 'release'    # Will have no suffix or label

[tool.version-flow.managed-branches.release-candidate]
rc = 'release/.*'        # Any branch starting with "release/"
fda = ['fda', 'reg']     # Only the branches "fda" and "reg"

[tool.version-flow.managed-branches.named-release]
# It is recommended to use exact branch names for all named releases
draco = 'prod/draco'
acme = 'prod/acme-corp'
```