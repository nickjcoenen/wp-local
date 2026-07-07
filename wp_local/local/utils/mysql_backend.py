"""
mysql_backend.py — MySQL operations for Local by Flywheel sites via unix socket.

All operations connect through the per-site mysqld.sock file, so the target
site must be running before any function here is called.
"""

import glob
import os
import shutil
import subprocess
import tempfile

from wp_local.local.core.site import (
    _get_site_data,
    get_mysql_socket,
    version_key_from_path,
)

LOCAL_LIGHTNING_SERVICES_DIRS = [
    os.path.expanduser("~/Library/Application Support/Local/lightning-services"),
    "/Applications/Local.app/Contents/Resources/extraResources/lightning-services",
]


def _find_mysql_binary(tool: str = "mysql") -> str:
    """Locate Local's bundled mysql/mysqldump; fall back to PATH.

    Picks the newest mysql-* lightning service on disk.
    """
    for base in LOCAL_LIGHTNING_SERVICES_DIRS:
        matches = glob.glob(
            os.path.join(base, "mysql-*", "bin", "darwin-arm64", "bin", tool)
        )
        if matches:
            matches.sort(key=lambda path: version_key_from_path(path, "mysql"))
            return matches[-1]
    on_path = shutil.which(tool)
    if on_path:
        return on_path
    raise RuntimeError(
        f"'{tool}' not found in Local's lightning-services or on PATH."
    )


def _get_socket(site_id: str) -> str:
    """Return the path to the mysqld unix socket for a site.

    Args:
        site_id: Local site ID string.

    Returns:
        Absolute path to the socket file.

    Raises:
        RuntimeError: if the socket file does not exist (site not running).
    """
    _get_site_data(site_id)
    socket_path = get_mysql_socket(site_id)
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
        _find_mysql_binary("mysql"),
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
        _find_mysql_binary("mysqldump"),
        f"--socket={socket}",
        "-u", "root",
        "-proot",
        "local",
    ]

    output_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    os.makedirs(output_dir, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=output_dir,
            prefix=f".{os.path.basename(output_path)}.",
            suffix=".tmp",
            delete=False,
        ) as out_file:
            temp_path = out_file.name
            result = subprocess.run(
                cmd,
                stdout=out_file,
                stderr=subprocess.PIPE,
                text=True,
            )

        if result.returncode != 0:
            raise RuntimeError(
                f"mysqldump exited with code {result.returncode}:\n{result.stderr.strip()}"
            )
        os.replace(temp_path, output_path)
    except Exception:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

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
        _find_mysql_binary("mysql"),
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
