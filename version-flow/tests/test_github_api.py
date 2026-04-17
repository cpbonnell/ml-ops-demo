"""
Tests for fixtures are not usually desirable. However, since the full stack of
the calls made goes version-flow -> pygithub -> requests -> responses -> fixtures,
and we are supplying only the minimum necessary information in the mocked JSON,
this is helpful to ensure that sufficient fields were being filled for pygithub
to correctly reconstruct the entity classes.
"""

from github import Github


def test_mocked_gh_repositories(gh, fake_gh_repo_id, fake_gh_repo_full_name, fake_gh_owner_login):
    repo_by_id = gh.get_repo(fake_gh_repo_id)
    repo_by_full_name = gh.get_repo(fake_gh_repo_full_name)
    assert repo_by_id.id == repo_by_full_name.id == fake_gh_repo_id
    assert repo_by_id.full_name == repo_by_full_name.full_name == fake_gh_repo_full_name


def test_mocked_gh_pull_request(
    gh,
    fake_gh_pull_request_json,
    fake_gh_repo_id,
    fake_gh_pull_request_number,
    default_fake_feature_branch_name,
):
    gh_repo = gh.get_repo(fake_gh_repo_id)

    pull_request = gh_repo.get_pull(fake_gh_pull_request_number)
    assert pull_request.number == fake_gh_pull_request_number
    assert pull_request.head.ref == default_fake_feature_branch_name
    assert pull_request.base.ref == "x_main"
