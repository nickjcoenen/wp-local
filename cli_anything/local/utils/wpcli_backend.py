"""
wpcli_backend.py — WP-CLI invocation helper for Local by Flywheel sites.

Locates the bundled wp-cli.phar, resolves the correct PHP binary for a site's
configured PHP version, and runs WP-CLI commands inside the site's WordPress
root.
"""

import glob
import json
import os
import subprocess

WPCLI_PHAR = (
    "/Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/wp-cli.phar"
)

LOCAL_LIGHTNING_SERVICES_DIR = os.path.expanduser(
    "~/Library/Application Support/Local/lightning-services"
)

LOCAL_RUN_DIR = os.path.expanduser(
    "~/Library/Application Support/Local/run"
)

SITES_JSON = os.path.expanduser(
    "~/Library/Application Support/Local/sites.json"
)


def _load_sites_json() -> dict:
    """Read Local's sites.json and return its contents as a dict.

    Returns:
        Dict mapping site IDs to site configuration dicts.

    Raises:
        RuntimeError: if sites.json does not exist.
    """
    if not os.path.exists(SITES_JSON):
        raise RuntimeError(
            f"sites.json not found at:\n  {SITES_JSON}\n"
            "Make sure Local by Flywheel is installed."
        )
    with open(SITES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_site_data(site_id: str) -> dict:
    """Return the configuration dict for a specific site.

    Args:
        site_id: Local site ID string.

    Returns:
        Site configuration dict from sites.json.

    Raises:
        RuntimeError: if the site ID is not found in sites.json.
    """
    sites = _load_sites_json()
    if site_id not in sites:
        available = ", ".join(sites.keys()) if sites else "(none)"
        raise RuntimeError(
            f"Site '{site_id}' not found in sites.json.\n"
            f"Available site IDs: {available}"
        )
    return sites[site_id]


def _find_php_binary(php_version: str) -> str:
    """Locate the PHP binary for the given version in Local's lightning-services.

    Searches for a path matching:
        {LOCAL_LIGHTNING_SERVICES_DIR}/php-{php_version}+*/bin/darwin-arm64/bin/php

    Args:
        php_version: PHP version string as stored in site services (e.g. '8.1.0').

    Returns:
        Absolute path to the php binary.

    Raises:
        RuntimeError: if no matching PHP binary is found.
    """
    pattern = os.path.join(
        LOCAL_LIGHTNING_SERVICES_DIR,
        f"php-{php_version}+*",
        "bin",
        "darwin-arm64",
        "bin",
        "php",
    )
    matches = glob.glob(pattern)
    if not matches:
        raise RuntimeError(
            f"PHP binary for version '{php_version}' not found.\n"
            f"Searched: {pattern}\n"
            "Make sure the PHP version is installed in Local."
        )
    # Prefer the highest-versioned build if multiple matches exist.
    matches.sort()
    return matches[-1]


def _get_wp_root(site_data: dict) -> str:
    """Return the WordPress document root path for a site.

    Args:
        site_data: Site configuration dict from sites.json.

    Returns:
        Absolute path to the WordPress installation (app/public).
    """
    return os.path.join(site_data["path"], "app", "public")


def run_wp_cli(
    site_id: str,
    wp_args: list[str],
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """Run a WP-CLI command for a Local site.

    Resolves the site's PHP binary and WordPress root, then invokes:
        {php_bin} {WPCLI_PHAR} --path={wp_root} --allow-root {wp_args...}

    The MYSQL_HOME environment variable is set so WP-CLI can locate the
    site's MySQL configuration, and WP_CLI_CACHE_DIR is pointed at /tmp to
    avoid permission issues.

    Args:
        site_id:        Local site ID string.
        wp_args:        List of WP-CLI arguments (e.g. ['option', 'get', 'siteurl']).
        capture_output: If True (default), stdout/stderr are captured and
                        available on the returned CompletedProcess object.
                        Set to False to stream output directly to the terminal.

    Returns:
        subprocess.CompletedProcess instance. Check .returncode, .stdout,
        and .stderr as needed.

    Raises:
        RuntimeError: if the site or its PHP binary cannot be found.
    """
    site_data = _get_site_data(site_id)

    # Locate the PHP service version for this site.
    services = site_data.get("services", {})
    php_version: str | None = None

    # services may be a dict keyed by service name or a list of service dicts.
    if isinstance(services, dict):
        php_service = services.get("php", {})
        php_version = php_service.get("version")
    elif isinstance(services, list):
        for svc in services:
            if svc.get("type") == "php" or svc.get("name", "").startswith("php"):
                php_version = svc.get("version")
                break

    if not php_version:
        raise RuntimeError(
            f"Could not determine PHP version for site '{site_id}'.\n"
            f"Site services data: {services}"
        )

    php_bin = _find_php_binary(php_version)
    wp_root = _get_wp_root(site_data)

    cmd = [
        php_bin,
        WPCLI_PHAR,
        f"--path={wp_root}",
        "--allow-root",
    ] + wp_args

    env = os.environ.copy()
    env["MYSQL_HOME"] = os.path.join(LOCAL_RUN_DIR, site_id, "conf", "mysql")
    env["WP_CLI_CACHE_DIR"] = "/tmp/wp-cli-cache"

    return subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        env=env,
    )
