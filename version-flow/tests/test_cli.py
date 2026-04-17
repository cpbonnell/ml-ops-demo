from click.testing import CliRunner

from version_flow.cli import main


def test_cli_can_be_invoked(
    gh, repo, fake_project_root_dir, most_recent_version_tag, fake_gh_repo_full_name, fake_gh_token_env, caplog
):
    runner = CliRunner(mix_stderr=False)

    with caplog.at_level("DEBUG"):
        result = runner.invoke(main, [fake_project_root_dir.as_posix(), "--log-level", "DEBUG", "--dry-run"])

    assert result.exit_code == 0
    assert "Beginning version-flow" in caplog.text
    assert "Completed version-flow." in caplog.text
