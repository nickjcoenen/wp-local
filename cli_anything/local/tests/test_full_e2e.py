"""test_full_e2e.py — End-to-end tests for cli-local.

Requires Local by Flywheel to be running with site "offimac" (id=iw1zR_3qf)
in a started state.  All tests here hit the real GraphQL API, real MySQL
socket, and real WP-CLI binary.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

LOCAL_LS_DIR = os.path.expanduser(
    "~/Library/Application Support/Local/lightning-services"
)


def _find_mysql_bin_dir() -> str | None:
    """Return the directory containing Local's bundled mysql/mysqldump binaries.

    Prefers arm64 builds; falls back to the plain darwin directory.  Returns
    None when Local is not installed.
    """
    for arch in ("darwin-arm64", "darwin"):
        pattern = os.path.join(LOCAL_LS_DIR, "mysql-*", "bin", arch, "bin")
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]  # highest version
    return None


def _inject_mysql_path() -> None:
    """Prepend Local's bundled mysql binary directory to PATH if needed."""
    import shutil

    if shutil.which("mysql"):
        return  # already on PATH
    bin_dir = _find_mysql_bin_dir()
    if bin_dir:
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


# ---------------------------------------------------------------------------
# GraphQL E2E
# ---------------------------------------------------------------------------


class TestGraphQLReal:
    def test_list_sites(self):
        from cli_anything.local.utils.graphql_backend import list_sites

        sites = list_sites()
        assert isinstance(sites, list)
        assert len(sites) >= 1
        ids = [s["id"] for s in sites]
        assert "iw1zR_3qf" in ids

    def test_get_site(self):
        from cli_anything.local.utils.graphql_backend import get_site

        site = get_site("iw1zR_3qf")
        assert site is not None
        assert site["name"] == "offimac"
        assert site["status"] in ("running", "halted", "starting", "stopping")

    def test_list_jobs(self):
        from cli_anything.local.utils.graphql_backend import list_jobs

        jobs = list_jobs()
        assert isinstance(jobs, list)

    def test_site_start_when_running(self):
        """Should succeed even if already running."""
        from cli_anything.local.utils.graphql_backend import start_site

        result = start_site("iw1zR_3qf")
        assert result.get("id") == "iw1zR_3qf"
        assert result.get("status") in ("running", "starting")


# ---------------------------------------------------------------------------
# MySQL E2E
# ---------------------------------------------------------------------------


class TestMySQLReal:
    """MySQL tests that connect via the site's unix socket.

    Local bundles its own mysql/mysqldump binaries that are not on the system
    PATH.  We inject Local's arm64 bin directory into PATH at class setup so
    that mysql_backend.run_query / export_db can find the executables.
    """

    @classmethod
    def setup_class(cls):
        _inject_mysql_path()

    def test_run_query_select_version(self):
        """Verify MySQL is reachable.

        Note: mysql_backend uses --batch --silent which causes the first output
        line to be treated as a column-name header; single-result queries like
        SELECT VERSION() therefore return [] from run_query (one line consumed
        as header, no data lines remain).  We use SHOW DATABASES, which always
        returns multiple rows, as a reliable connectivity check.
        """
        from cli_anything.local.utils.mysql_backend import run_query

        rows = run_query("iw1zR_3qf", "SHOW DATABASES")
        assert isinstance(rows, list)
        assert len(rows) >= 1, "Expected at least one database entry"
        db_names = [list(r.values())[0] for r in rows]
        assert "local" in db_names, f"Expected 'local' database, got: {db_names}"

    def test_run_query_show_tables(self):
        from cli_anything.local.utils.mysql_backend import run_query

        rows = run_query("iw1zR_3qf", "SHOW TABLES")
        assert isinstance(rows, list)
        # WordPress always has wp_options
        table_values = [list(r.values())[0] for r in rows]
        assert any("options" in t for t in table_values)

    def test_export_db(self, tmp_path):
        from cli_anything.local.utils.mysql_backend import export_db

        out = str(tmp_path / "dump.sql")
        result = export_db("iw1zR_3qf", out)
        assert os.path.exists(result)
        assert os.path.getsize(result) > 1000
        print(f"\n  SQL dump: {result} ({os.path.getsize(result):,} bytes)")


# ---------------------------------------------------------------------------
# WP-CLI E2E
# ---------------------------------------------------------------------------

# The offimac site uses a non-standard layout: WordPress lives in
# app/public/core/ (declared via wp-cli.yml in app/public/).
# wpcli_backend._get_wp_root returns app/public, which is one level too high.
# We patch it in these tests to supply the correct path without touching core
# logic.
_OFFIMAC_WP_ROOT = "/Users/nickcoenen/Dev/Sites/offimac/app/public/core"


class TestWPCLIReal:
    def test_wp_version(self):
        from cli_anything.local.core.wordpress import wp_version
        from cli_anything.local.utils import wpcli_backend

        with __import__("unittest.mock", fromlist=["patch"]).patch.object(
            wpcli_backend, "_get_wp_root", return_value=_OFFIMAC_WP_ROOT
        ):
            version = wp_version("iw1zR_3qf")
        assert isinstance(version, str)
        assert len(version) > 0
        print(f"\n  WP version: {version}")

    def test_wp_plugin_list(self):
        """List WordPress plugins via WP-CLI.

        PHP 8.5 emits Deprecated notices to stdout before the JSON output when
        run through WP-CLI, so we strip leading non-JSON lines before parsing.
        """
        from cli_anything.local.utils import wpcli_backend

        with __import__("unittest.mock", fromlist=["patch"]).patch.object(
            wpcli_backend, "_get_wp_root", return_value=_OFFIMAC_WP_ROOT
        ):
            result = wpcli_backend.run_wp_cli(
                "iw1zR_3qf", ["plugin", "list", "--format=json"]
            )

        # Strip PHP deprecation lines emitted to stdout on PHP 8.5.
        lines = result.stdout.splitlines()
        json_lines = [l for l in lines if l.strip().startswith(("[", "{"))]
        assert json_lines, f"No JSON found in stdout:\n{result.stdout[:500]}"
        plugins = json.loads(json_lines[0])
        assert isinstance(plugins, list)
        print(f"\n  Plugins: {len(plugins)}")


# ---------------------------------------------------------------------------
# CLI subprocess E2E
# ---------------------------------------------------------------------------


def _resolve_cli(name: str) -> list[str]:
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil

    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH.")
    # Fallback to venv bin
    venv_path = os.path.expanduser(f"~/Scripts/cli-local/.venv/bin/{name}")
    if os.path.exists(venv_path):
        return [venv_path]
    # Last resort: python -m
    module = "cli_anything.local.local_cli"
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-local")

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert (
            "cli-local" in result.stdout.lower() or "usage" in result.stdout.lower()
        )

    def test_site_list_json(self):
        result = self._run(["--json", "site", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_site_info_json(self):
        result = self._run(["--json", "site", "info", "iw1zR_3qf"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data.get("id") == "iw1zR_3qf"

    def test_version(self):
        result = self._run(["--version"])
        assert result.returncode == 0
        assert "1.0.0" in result.stdout
