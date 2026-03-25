"""test_core.py — Unit tests for cli-local core modules.

Uses unittest.mock throughout; no real Local installation is required.
"""

from __future__ import annotations

import json
import os
import sys
import types
from io import StringIO
from unittest.mock import MagicMock, mock_open, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures / shared synthetic data
# ---------------------------------------------------------------------------

FAKE_SITES_JSON = {
    "abc123": {
        "id": "abc123",
        "name": "TestSite",
        "path": "/tmp/testsite",
        "domain": "testsite.test",
        "localVersion": "10.0.0",
        "services": {},
        "multiSite": "No",
        "xdebugEnabled": False,
        "workspace": None,
    }
}

FAKE_STATUSES = {"abc123": "running"}

# ---------------------------------------------------------------------------
# graphql_backend tests
# ---------------------------------------------------------------------------


class TestLoadConnectionInfo:
    def test_load_connection_info_missing_file(self):
        from cli_anything.local.utils import graphql_backend

        with patch("os.path.exists", return_value=False):
            with pytest.raises(RuntimeError, match="GraphQL connection info not found"):
                graphql_backend._load_connection_info()

    def test_load_connection_info_valid(self):
        from cli_anything.local.utils import graphql_backend

        fake_info = {"url": "http://localhost:4000", "authToken": "tok123"}
        m = mock_open(read_data=json.dumps(fake_info))
        with patch("os.path.exists", return_value=True), patch("builtins.open", m):
            result = graphql_backend._load_connection_info()
        assert result["authToken"] == "tok123"
        assert result["url"] == "http://localhost:4000"


class TestGql:
    def _fake_info(self):
        return {"url": "http://localhost:4000/graphql", "authToken": "mytoken"}

    def test_gql_uses_auth_token(self):
        from cli_anything.local.utils import graphql_backend

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"data": {"sites": []}}

        with patch.object(
            graphql_backend, "_load_connection_info", return_value=self._fake_info()
        ), patch("requests.post", return_value=mock_resp) as mock_post:
            graphql_backend.gql("{ sites { id } }")

        _, kwargs = mock_post.call_args
        headers = kwargs.get("headers", mock_post.call_args[0][1] if len(mock_post.call_args[0]) > 1 else {})
        # requests.post(url, json=..., headers=...) — positional or keyword
        call_kwargs = mock_post.call_args.kwargs
        sent_headers = call_kwargs.get("headers", {})
        assert sent_headers.get("Authorization") == "Bearer mytoken"

    def test_gql_raises_on_http_error(self):
        from cli_anything.local.utils import graphql_backend

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch.object(
            graphql_backend, "_load_connection_info", return_value=self._fake_info()
        ), patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="GraphQL HTTP error 500"):
                graphql_backend.gql("{ sites { id } }")

    def test_gql_raises_on_graphql_errors(self):
        from cli_anything.local.utils import graphql_backend

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "errors": [{"message": "Something went wrong"}],
            "data": None,
        }

        with patch.object(
            graphql_backend, "_load_connection_info", return_value=self._fake_info()
        ), patch("requests.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="GraphQL errors"):
                graphql_backend.gql("{ sites { id } }")


class TestListAndGetSite:
    def test_list_sites_returns_list(self):
        from cli_anything.local.utils import graphql_backend

        fake_sites = [{"id": "abc", "name": "Alpha"}, {"id": "def", "name": "Beta"}]
        with patch.object(graphql_backend, "gql", return_value={"sites": fake_sites}):
            result = graphql_backend.list_sites()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["id"] == "abc"

    def test_get_site_found(self):
        from cli_anything.local.utils import graphql_backend

        fake_sites = [{"id": "abc123", "name": "TestSite"}, {"id": "xyz", "name": "Other"}]
        with patch.object(graphql_backend, "list_sites", return_value=fake_sites):
            site = graphql_backend.get_site("abc123")
        assert site is not None
        assert site["name"] == "TestSite"

    def test_get_site_not_found(self):
        from cli_anything.local.utils import graphql_backend

        fake_sites = [{"id": "abc123", "name": "TestSite"}]
        with patch.object(graphql_backend, "list_sites", return_value=fake_sites):
            site = graphql_backend.get_site("nonexistent")
        assert site is None


# ---------------------------------------------------------------------------
# wpcli_backend tests
# ---------------------------------------------------------------------------


class TestFindPhpBinary:
    def test_find_php_binary_found(self):
        from cli_anything.local.utils import wpcli_backend

        fake_path = "/fake/path/php-8.1.0+1/bin/darwin-arm64/bin/php"
        with patch("glob.glob", return_value=[fake_path]):
            result = wpcli_backend._find_php_binary("8.1.0")
        assert result == fake_path

    def test_find_php_binary_not_found(self):
        from cli_anything.local.utils import wpcli_backend

        with patch("glob.glob", return_value=[]):
            with pytest.raises(RuntimeError, match="PHP binary for version"):
                wpcli_backend._find_php_binary("9.9.9")


class TestLoadSitesJson:
    def test_load_sites_json_missing(self):
        from cli_anything.local.utils import wpcli_backend

        with patch("os.path.exists", return_value=False):
            with pytest.raises(RuntimeError, match="sites.json not found"):
                wpcli_backend._load_sites_json()

    def test_get_site_data_not_found(self):
        from cli_anything.local.utils import wpcli_backend

        with patch.object(wpcli_backend, "_load_sites_json", return_value={}):
            with pytest.raises(RuntimeError, match="not found in sites.json"):
                wpcli_backend._get_site_data("nosuchsite")


class TestGetWpRoot:
    def test_get_wp_root(self):
        from cli_anything.local.utils import wpcli_backend

        site_data = {"path": "/Users/nick/Local Sites/mysite"}
        result = wpcli_backend._get_wp_root(site_data)
        assert result == "/Users/nick/Local Sites/mysite/app/public"


class TestRunWpCli:
    def _fake_site_data(self):
        return {
            "path": "/tmp/testsite",
            "services": {"php": {"version": "8.1.0"}},
        }

    def test_run_wp_cli_constructs_command(self):
        from cli_anything.local.utils import wpcli_backend

        fake_proc = MagicMock()
        fake_proc.returncode = 0

        with patch.object(
            wpcli_backend, "_get_site_data", return_value=self._fake_site_data()
        ), patch.object(
            wpcli_backend, "_find_php_binary", return_value="/fake/php"
        ), patch(
            "subprocess.run", return_value=fake_proc
        ) as mock_run:
            wpcli_backend.run_wp_cli("abc123", ["core", "version"])

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "/fake/php"
        assert wpcli_backend.WPCLI_PHAR in cmd
        assert any("--path=" in arg for arg in cmd)
        assert "--allow-root" in cmd
        assert "core" in cmd
        assert "version" in cmd

    def test_run_wp_cli_sets_mysql_home(self):
        from cli_anything.local.utils import wpcli_backend

        fake_proc = MagicMock()
        fake_proc.returncode = 0

        with patch.object(
            wpcli_backend, "_get_site_data", return_value=self._fake_site_data()
        ), patch.object(
            wpcli_backend, "_find_php_binary", return_value="/fake/php"
        ), patch(
            "subprocess.run", return_value=fake_proc
        ) as mock_run:
            wpcli_backend.run_wp_cli("abc123", ["core", "version"])

        env = mock_run.call_args.kwargs.get("env", {})
        assert "MYSQL_HOME" in env
        assert "abc123" in env["MYSQL_HOME"]


# ---------------------------------------------------------------------------
# site.py tests
# ---------------------------------------------------------------------------


class TestSiteFile:
    """Tests for cli_anything.local.core.site using mocked file I/O."""

    def _patch_json_files(self, sites=None, statuses=None):
        """Return a context manager that patches _read_json for both files."""
        sites_data = sites if sites is not None else FAKE_SITES_JSON
        statuses_data = statuses if statuses is not None else FAKE_STATUSES

        from cli_anything.local.core import site as site_mod

        def fake_read_json(path):
            if "sites.json" in path and "statuses" not in path:
                return sites_data
            if "site-statuses" in path:
                return statuses_data
            return {}

        return patch.object(site_mod, "_read_json", side_effect=fake_read_json)

    def test_list_sites_from_file(self):
        from cli_anything.local.core.site import list_sites_from_file

        with self._patch_json_files():
            result = list_sites_from_file()

        assert isinstance(result, list)
        assert len(result) == 1
        s = result[0]
        assert s["id"] == "abc123"
        assert s["name"] == "TestSite"
        assert s["status"] == "running"

    def test_get_site_by_id(self):
        from cli_anything.local.core.site import get_site_from_file

        with self._patch_json_files():
            site = get_site_from_file("abc123")

        assert site is not None
        assert site["id"] == "abc123"

    def test_get_site_by_name_case_insensitive(self):
        from cli_anything.local.core.site import get_site_from_file

        with self._patch_json_files():
            site = get_site_from_file("testsite")

        assert site is not None
        assert site["name"] == "TestSite"

    def test_get_site_not_found_returns_none(self):
        from cli_anything.local.core.site import get_site_from_file

        with self._patch_json_files():
            site = get_site_from_file("does-not-exist")

        assert site is None

    def test_resolve_site_id_found(self):
        from cli_anything.local.core.site import resolve_site_id

        with self._patch_json_files():
            site_id = resolve_site_id("abc123")

        assert site_id == "abc123"

    def test_resolve_site_id_not_found(self):
        from cli_anything.local.core.site import resolve_site_id

        with self._patch_json_files():
            with pytest.raises(RuntimeError, match="Site not found"):
                resolve_site_id("ghost-site")

    def test_get_run_dir(self):
        from cli_anything.local.core.site import get_run_dir, RUN_DIR

        result = get_run_dir("abc123")
        assert result == os.path.join(RUN_DIR, "abc123")

    def test_get_mysql_socket(self):
        from cli_anything.local.core.site import get_mysql_socket, RUN_DIR

        result = get_mysql_socket("abc123")
        expected = os.path.join(RUN_DIR, "abc123", "mysql", "mysqld.sock")
        assert result == expected

    def test_is_running_true(self):
        from cli_anything.local.core import site as site_mod
        from cli_anything.local.core.site import is_running

        with patch.object(site_mod, "_read_json", return_value={"abc123": "running"}):
            assert is_running("abc123") is True

    def test_is_running_false(self):
        from cli_anything.local.core import site as site_mod
        from cli_anything.local.core.site import is_running

        with patch.object(site_mod, "_read_json", return_value={"abc123": "halted"}):
            assert is_running("abc123") is False


# ---------------------------------------------------------------------------
# session.py tests
# ---------------------------------------------------------------------------


class TestSession:
    def test_session_load_empty(self, tmp_path):
        from cli_anything.local.core import session as session_mod

        nonexistent = str(tmp_path / "no_such_file.json")
        with patch.object(session_mod, "SESSION_FILE", nonexistent):
            s = session_mod.Session.load()

        assert s.active_site_id is None

    def test_session_save_and_load(self, tmp_path):
        from cli_anything.local.core import session as session_mod

        session_file = str(tmp_path / "session.json")
        with patch.object(session_mod, "SESSION_FILE", session_file), patch.object(
            session_mod, "SESSION_DIR", str(tmp_path)
        ):
            s = session_mod.Session.load()
            s.active_site_id = "abc123"
            s._data["active_site_id"] = "abc123"
            s.save()

            s2 = session_mod.Session.load()

        assert s2.active_site_id == "abc123"

    def test_session_set_active_site(self, tmp_path):
        from cli_anything.local.core import session as session_mod

        session_file = str(tmp_path / "session.json")
        with patch.object(session_mod, "SESSION_FILE", session_file), patch.object(
            session_mod, "SESSION_DIR", str(tmp_path)
        ):
            s = session_mod.Session.load()
            s.set_active_site("site_xyz")

        assert s.active_site_id == "site_xyz"

    def test_session_clear(self, tmp_path):
        from cli_anything.local.core import session as session_mod

        session_file = str(tmp_path / "session.json")
        with patch.object(session_mod, "SESSION_FILE", session_file), patch.object(
            session_mod, "SESSION_DIR", str(tmp_path)
        ):
            s = session_mod.Session.load()
            s.set_active_site("site_xyz")
            assert s.active_site_id == "site_xyz"
            s.clear()

        assert s.active_site_id is None
