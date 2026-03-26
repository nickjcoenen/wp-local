"""WordPress operations via WP-CLI for wp-local.

All functions call wpcli_backend.run_wp_cli() which handles path/socket
resolution and subprocess execution.
"""

import json
import subprocess

from cli_anything.local.utils.wpcli_backend import run_wp_cli


def wp_version(site_id: str) -> str:
    """Return the WordPress core version string for *site_id*.

    Runs: wp core version
    """
    result = run_wp_cli(site_id, ["core", "version"])
    result.check_returncode()
    return result.stdout.strip()


def wp_info(site_id: str) -> dict:
    """Return extended WordPress core information as a dict.

    Runs: wp core version --extra --format=json
    """
    result = run_wp_cli(site_id, ["core", "version", "--extra", "--format=json"])
    result.check_returncode()
    return json.loads(result.stdout)


def list_plugins(site_id: str) -> list[dict]:
    """Return the list of installed plugins for *site_id*.

    Runs: wp plugin list --format=json
    Each item is a dict with keys such as name, status, version, update.
    """
    result = run_wp_cli(site_id, ["plugin", "list", "--format=json"])
    result.check_returncode()
    return json.loads(result.stdout)


def list_themes(site_id: str) -> list[dict]:
    """Return the list of installed themes for *site_id*.

    Runs: wp theme list --format=json
    Each item is a dict with keys such as name, status, version, update.
    """
    result = run_wp_cli(site_id, ["theme", "list", "--format=json"])
    result.check_returncode()
    return json.loads(result.stdout)


def wp_user_list(site_id: str) -> list[dict]:
    """Return the list of WordPress users for *site_id*.

    Runs: wp user list --format=json
    Each item is a dict with keys such as ID, user_login, user_email, roles.
    """
    result = run_wp_cli(site_id, ["user", "list", "--format=json"])
    result.check_returncode()
    return json.loads(result.stdout)


def run_arbitrary(site_id: str, args: list[str]) -> subprocess.CompletedProcess:
    """Run an arbitrary WP-CLI command for *site_id* and return the raw result.

    The caller is responsible for inspecting returncode, stdout, and stderr.

    Example:
        result = run_arbitrary("abc123", ["option", "get", "siteurl"])
        print(result.stdout)
    """
    return run_wp_cli(site_id, args)
