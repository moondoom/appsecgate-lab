"""Tests for normalize.py."""

from agent.observer.normalize import (
    extract_db_key,
    extract_repo_url,
    make_asset_key,
    normalize_repo_url,
)


class TestExtractRepoUrl:
    def test_https(self) -> None:
        assert (
            extract_repo_url("git clone https://github.com/org/repo.git")
            == "https://github.com/org/repo.git"
        )

    def test_ssh(self) -> None:
        assert extract_repo_url("git@github.com:org/repo.git") == "git@github.com:org/repo.git"

    def test_no_url(self) -> None:
        assert extract_repo_url("ls -la") == ""


class TestNormalizeRepoUrl:
    def test_git_at(self) -> None:
        assert normalize_repo_url("git@github.com:Org/Repo.git") == "https://github.com/org/repo"

    def test_https(self) -> None:
        assert (
            normalize_repo_url("https://github.com/org/repo.git") == "https://github.com/org/repo"
        )

    def test_ssh_protocol(self) -> None:
        assert normalize_repo_url("ssh://git@github.com/org/repo") == "https://github.com/org/repo"


class TestExtractDbKey:
    def test_host(self) -> None:
        assert extract_db_key('{"host": "db-01.internal"}') == "db-01.internal"

    def test_server(self) -> None:
        assert extract_db_key("server=pg-02.example.com") == "pg-02.example.com"

    def test_no_match(self) -> None:
        assert extract_db_key("some random text") == ""


class TestMakeAssetKey:
    def test_host(self) -> None:
        assert make_asset_key("host", "server-01") == "host:server-01"

    def test_repo(self) -> None:
        assert make_asset_key("repo", "github.com", "org", "repo") == "repo:github.com:org:repo"
