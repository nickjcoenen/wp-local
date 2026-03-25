"""Site data management for Local by Flywheel.

Reads Local's JSON files directly from disk and falls back gracefully
when the Local app is not running.
"""

import json
import os

APPDATA = os.path.expanduser("~/Library/Application Support/Local")
SITES_JSON = os.path.join(APPDATA, "sites.json")
SITE_STATUSES_JSON = os.path.join(APPDATA, "site-statuses.json")
RUN_DIR = os.path.join(APPDATA, "run")


def _read_json(path: str) -> dict:
    """Read a JSON file, returning an empty dict if missing or unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
        return {}


def list_sites_from_file() -> list[dict]:
    """Read sites.json and site-statuses.json, merge status, return sorted list.

    Each dict contains: id, name, domain, path, localVersion, status,
    services, multiSite, xdebugEnabled.
    """
    raw_sites: dict = _read_json(SITES_JSON)
    raw_statuses: dict = _read_json(SITE_STATUSES_JSON)

    sites: list[dict] = []
    for site_id, site_data in raw_sites.items():
        status_entry = raw_statuses.get(site_id, {})
        # Local stores status either as a plain string or nested object.
        if isinstance(status_entry, dict):
            status = status_entry.get("status", "stopped")
        else:
            status = str(status_entry) if status_entry else "stopped"

        # Normalise domain: Local may store it under .domain or .domains[0]
        domain = site_data.get("domain", "")
        if not domain:
            domains = site_data.get("domains", [])
            domain = domains[0] if domains else ""

        sites.append(
            {
                "id": site_id,
                "name": site_data.get("name", ""),
                "domain": domain,
                "path": site_data.get("path", ""),
                "localVersion": site_data.get("localVersion", ""),
                "status": status,
                "services": site_data.get("services", {}),
                "multiSite": site_data.get("multiSite", False),
                "xdebugEnabled": site_data.get("xdebugEnabled", False),
            }
        )

    return sorted(sites, key=lambda s: s["name"].lower())


def get_site_from_file(id_or_name: str) -> dict | None:
    """Return a site dict matching the given ID (exact) or name (case-insensitive).

    Returns None if no match is found.
    """
    sites = list_sites_from_file()
    # Exact ID match first.
    for site in sites:
        if site["id"] == id_or_name:
            return site
    # Case-insensitive name match.
    needle = id_or_name.lower()
    for site in sites:
        if site["name"].lower() == needle:
            return site
    return None


def resolve_site_id(id_or_name: str) -> str:
    """Return the site ID for the given ID or name.

    Raises RuntimeError with "Site not found" if no match exists.
    """
    site = get_site_from_file(id_or_name)
    if site is None:
        raise RuntimeError(f"Site not found: {id_or_name!r}")
    return site["id"]


def get_run_dir(site_id: str) -> str:
    """Return the runtime directory for a site: {RUN_DIR}/{site_id}."""
    return os.path.join(RUN_DIR, site_id)


def get_mysql_socket(site_id: str) -> str:
    """Return the MySQL socket path for a site."""
    return os.path.join(RUN_DIR, site_id, "mysql", "mysqld.sock")


def get_php_fpm_socket(site_id: str) -> str:
    """Return the PHP-FPM socket path for a site."""
    return os.path.join(RUN_DIR, site_id, "php", "php-fpm.socket")


def get_wp_root(site_id: str) -> str:
    """Return the WordPress root directory ({site_path}/app/public) for a site.

    Reads the path from sites.json. Falls back to an empty-base path if the
    site is not found.
    """
    site = get_site_from_file(site_id)
    base = site["path"] if site else ""
    return os.path.join(base, "app", "public")


def get_log_path(site_id: str, service: str, log_name: str = None) -> str:
    """Return the log file path for a site service.

    Defaults to error.log when log_name is not specified.
    Path: {site_path}/logs/{service}/{log_name}
    """
    site = get_site_from_file(site_id)
    base = site["path"] if site else ""
    filename = log_name if log_name else "error.log"
    return os.path.join(base, "logs", service, filename)


def is_running(site_id: str) -> bool:
    """Return True if the site's status is "running" according to site-statuses.json."""
    raw_statuses: dict = _read_json(SITE_STATUSES_JSON)
    status_entry = raw_statuses.get(site_id, {})
    if isinstance(status_entry, dict):
        status = status_entry.get("status", "stopped")
    else:
        status = str(status_entry) if status_entry else "stopped"
    return status == "running"
