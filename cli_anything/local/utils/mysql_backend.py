"""
mysql_backend.py — MySQL operations for Local by Flywheel sites via unix socket.

All operations connect through the per-site mysqld.sock file, so the target
site must be running before any function here is called.
"""

import json
import os
import subprocess

LOCAL_RUN_DIR = os.path.expanduser(
    "~/Library/Application Support/Local/run"
)

SITES_JSON = os.path.expanduser(
    "~/Library/Application Support/Local/sites.json"
)


def _get_site_data(site_id: str) -> dict:
    """Return the configuration dict for a specific site from sites.json.

    Args:
        site_id: Local site ID string.

    Returns:
        Site configuration dict.

    Raises:
        RuntimeError: if sites.json is missing or the site ID is not found.
    """
    if not os.path.exists(SITES_JSON):
        raise RuntimeError(
            f"sites.json not found at:\n  {SITES_JSON}\n"
            "Make sure Local by Flywheel is installed."
        )
    with open(SITES_JSON, "r", encoding="utf-8") as f:
        sites = json.load(f)
    if site_id not in sites:
        available = ", ".join(sites.keys()) if sites else "(none)"
        raise RuntimeError(
            f"Site '{site_id}' not found in sites.json.\n"
            f"Available site IDs: {available}"
        )
    return sites[site_id]


def _get_socket(site_id: str) -> str:
    """Return the path to the mysqld unix socket for a site.

    Args:
        site_id: Local site ID string.

    Returns:
        Absolute path to the socket file.

    Raises:
        RuntimeError: if the socket file does not exist (site not running).
    """
    socket_path = os.path.join(LOCAL_RUN_DIR, site_id, "mysql", "mysqld.sock")
    if not os.path.exists(socket_path):
        raise RuntimeError(
            f"MySQL socket not found at:\n  {socket_path}\n"
            f"Make sure the Local site '{site_id}' is running."
        )
    return socket_path


def run_query(site_id: str, sql: str) -> list[dict]:
    """Execute a SQL statement and return the results as a list of dicts.

    Connects via the site's unix socket using the default Local credentials
    (root / root, database: local).

    Tab-separated output from mysql --batch --silent is parsed so that the
    first row becomes the column names and every subsequent row becomes a dict.

    Args:
        site_id: Local site ID string.
        sql:     SQL statement to execute.

    Returns:
        List of row dicts, or an empty list if the query returns no rows.

    Raises:
        RuntimeError: if the site socket does not exist or the mysql command fails.
    """
    socket = _get_socket(site_id)

    cmd = [
        "mysql",
        f"--socket={socket}",
        "-u", "root",
        "-proot",
        "local",
        "-e", sql,
        "--batch",
        "--silent",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"mysql exited with code {result.returncode}:\n{result.stderr.strip()}"
        )

    output = result.stdout.strip()
    if not output:
        return []

    lines = output.splitlines()
    if not lines:
        return []

    headers = lines[0].split("\t")
    rows: list[dict] = []
    for line in lines[1:]:
        values = line.split("\t")
        rows.append(dict(zip(headers, values)))

    return rows


def export_db(site_id: str, output_path: str) -> str:
    """Dump the site's WordPress database to a SQL file.

    Uses mysqldump via the site's unix socket. The output file is written to
    output_path; any existing file at that path will be overwritten.

    Args:
        site_id:     Local site ID string.
        output_path: Absolute or relative path for the output .sql file.

    Returns:
        The output_path that was written to.

    Raises:
        RuntimeError: if the socket does not exist or mysqldump fails.
    """
    socket = _get_socket(site_id)

    cmd = [
        "mysqldump",
        f"--socket={socket}",
        "-u", "root",
        "-proot",
        "local",
    ]

    with open(output_path, "w", encoding="utf-8") as out_file:
        result = subprocess.run(cmd, stdout=out_file, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"mysqldump exited with code {result.returncode}:\n{result.stderr.strip()}"
        )

    return output_path


def import_db(site_id: str, input_path: str) -> None:
    """Import a SQL dump into the site's WordPress database.

    Pipes the contents of input_path into mysql via the site's unix socket.
    This will overwrite any existing data in the 'local' database.

    Args:
        site_id:    Local site ID string.
        input_path: Path to the .sql file to import.

    Raises:
        RuntimeError: if the socket does not exist, the input file is missing,
                      or mysql fails.
    """
    socket = _get_socket(site_id)

    if not os.path.exists(input_path):
        raise RuntimeError(
            f"SQL import file not found at:\n  {input_path}"
        )

    cmd = [
        "mysql",
        f"--socket={socket}",
        "-u", "root",
        "-proot",
        "local",
    ]

    with open(input_path, "r", encoding="utf-8") as in_file:
        result = subprocess.run(cmd, stdin=in_file, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"mysql import exited with code {result.returncode}:\n{result.stderr.strip()}"
        )
