"""local_cli.py — Click CLI harness for Local by Flywheel.

Entry point: wp-local (registered via setup.py console_scripts)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from functools import wraps
from typing import Optional

import click

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_session: Optional["Session"] = None  # noqa: F821
_json_output: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def output(data, message: str = "") -> None:
    """Output data as JSON or human-readable."""
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        elif isinstance(data, (dict, list)):
            click.echo(json.dumps(data, indent=2, default=str))


def handle_errors(func):
    """Print expected CLI errors and return a non-zero exit code."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (RuntimeError, click.UsageError) as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    return wrapper


def json_option(func):
    return click.option("--json", "json_mode", is_flag=True, help="Output JSON")(func)


def enable_command_json(json_mode: bool) -> None:
    global _json_output
    _json_output = _json_output or json_mode


def get_session():
    global _session
    if _session is None:
        from wp_local.local.core.session import Session
        _session = Session.load()
    return _session


def get_global_site_arg() -> str | None:
    ctx = click.get_current_context(silent=True)
    while ctx is not None:
        if isinstance(ctx.obj, dict) and ctx.obj.get("site"):
            return ctx.obj["site"]
        ctx = ctx.parent
    return None


def resolve_site(id_or_name: str | None) -> str:
    """Resolve site ID using arg, global flag, cwd, then session."""
    site_ref = id_or_name or get_global_site_arg()
    if site_ref:
        from wp_local.local.core.site import resolve_site_id
        return resolve_site_id(site_ref)
    from wp_local.local.core.site import resolve_site_from_cwd
    cwd_site = resolve_site_from_cwd()
    if cwd_site:
        return cwd_site
    s = get_session()
    if s.active_site_id:
        return s.active_site_id
    raise click.UsageError(
        "No site specified. Use --site, run from inside a site folder, "
        "or 'wp-local session use <id>'"
    )


def _print_sites_table(sites: list[dict]) -> None:
    """Print sites as a human-readable table."""
    if not sites:
        click.echo("No sites found.")
        return
    col_id = max(len("ID"), max(len(s.get("id", "")) for s in sites))
    col_name = max(len("Name"), max(len(s.get("name", "")) for s in sites))
    col_domain = max(len("Domain"), max(len(s.get("domain", "")) for s in sites))
    col_status = max(len("Status"), max(len(s.get("status", "")) for s in sites))
    fmt = f"{{:<{col_id}}}  {{:<{col_name}}}  {{:<{col_domain}}}  {{:<{col_status}}}"
    header = fmt.format("ID", "Name", "Domain", "Status")
    click.echo(header)
    click.echo("-" * len(header))
    for s in sites:
        click.echo(fmt.format(
            s.get("id", ""),
            s.get("name", ""),
            s.get("domain", ""),
            s.get("status", ""),
        ))


def _print_rows_table(rows: list[dict]) -> None:
    """Print a list of dicts as a simple ASCII table."""
    if not rows:
        click.echo("(no rows)")
        return
    headers = list(rows[0].keys())
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(row.get(h, ""))))
    fmt = "  ".join(f"{{:<{widths[h]}}}" for h in headers)
    header_line = fmt.format(*headers)
    click.echo(header_line)
    click.echo("-" * len(header_line))
    for row in rows:
        click.echo(fmt.format(*[str(row.get(h, "")) for h in headers]))


class HelpOnNoArgsGroup(click.Group):
    def parse_args(self, ctx, args):
        if not args and not ctx.resilient_parsing:
            click.echo(ctx.get_help(), color=ctx.color)
            ctx.exit(0)
        return super().parse_args(ctx, args)


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------


@click.group(cls=HelpOnNoArgsGroup)
@click.option("--json", "json_mode", is_flag=True, help="Output JSON")
@click.option("--site", "site_arg", default=None, help="Site ID or name")
@click.version_option("1.0.0", prog_name="wp-local")
@click.pass_context
def cli(ctx, json_mode, site_arg):
    """CLI harness for Local by Flywheel."""
    global _json_output
    _json_output = json_mode
    ctx.ensure_object(dict)
    ctx.obj["site"] = site_arg


# ---------------------------------------------------------------------------
# site group
# ---------------------------------------------------------------------------


@cli.group()
def site():
    """Manage Local sites."""


@site.command(name="list")
@json_option
@handle_errors
def site_list(json_mode):
    """List all sites."""
    enable_command_json(json_mode)
    try:
        from wp_local.local.utils.graphql_backend import list_sites
        sites = list_sites()
    except RuntimeError:
        from wp_local.local.core.site import list_sites_from_file
        sites = list_sites_from_file()

    if _json_output:
        output(sites)
    else:
        _print_sites_table(sites)


@site.command(name="status")
@click.argument("site_id", required=False)
@json_option
@handle_errors
def site_status(site_id, json_mode):
    """Show running/halted status for a site."""
    enable_command_json(json_mode)
    resolved = resolve_site(site_id)
    from wp_local.local.core.site import is_running, get_site_from_file
    running = is_running(resolved)
    s = get_site_from_file(resolved)
    name = s["name"] if s else resolved
    status_str = "running" if running else "halted"
    output({"id": resolved, "name": name, "status": status_str},
           message=f"{name} ({resolved}): {status_str}")


@site.command(name="start")
@click.argument("site_id", required=False)
@handle_errors
def site_start(site_id):
    """Start a site."""
    resolved = resolve_site(site_id)
    from wp_local.local.utils.graphql_backend import start_site
    result = start_site(resolved)
    output(result, message=f"Started: {result.get('id', resolved)} -> {result.get('status', 'started')}")


@site.command(name="stop")
@click.argument("site_id", required=False)
@handle_errors
def site_stop(site_id):
    """Stop a site."""
    resolved = resolve_site(site_id)
    from wp_local.local.utils.graphql_backend import stop_site
    result = stop_site(resolved)
    output(result, message=f"Stopped: {result.get('id', resolved)} -> {result.get('status', 'stopped')}")


@site.command(name="restart")
@click.argument("site_id", required=False)
@handle_errors
def site_restart(site_id):
    """Restart a site."""
    resolved = resolve_site(site_id)
    from wp_local.local.utils.graphql_backend import restart_site
    result = restart_site(resolved)
    output(result, message=f"Restarted: {result.get('id', resolved)} -> {result.get('status', 'running')}")


@site.command(name="info")
@click.argument("site_id", required=False)
@json_option
@handle_errors
def site_info(site_id, json_mode):
    """Show full site details including services and ports."""
    enable_command_json(json_mode)
    resolved = resolve_site(site_id)
    # Prefer GraphQL for live data; fall back to file.
    try:
        from wp_local.local.utils.graphql_backend import get_site
        s = get_site(resolved)
    except RuntimeError:
        from wp_local.local.core.site import get_site_from_file
        s = get_site_from_file(resolved)

    if s is None:
        raise RuntimeError(f"Site not found: {resolved}")

    if _json_output:
        output(s)
    else:
        click.echo(f"ID:      {s.get('id', '')}")
        click.echo(f"Name:    {s.get('name', '')}")
        click.echo(f"Domain:  {s.get('domain', '')}")
        click.echo(f"Status:  {s.get('status', '')}")
        click.echo(f"Path:    {s.get('path', '')}")
        if s.get("localVersion"):
            click.echo(f"Local:   {s['localVersion']}")
        services = s.get("services") or {}
        if services:
            click.echo("Services:")
            if isinstance(services, dict):
                for svc_name, svc_data in services.items():
                    if isinstance(svc_data, dict):
                        ver = svc_data.get("version", "")
                        click.echo(f"  {svc_name}: {ver}")
                    else:
                        click.echo(f"  {svc_name}: {svc_data}")
            elif isinstance(services, list):
                for svc in services:
                    name = svc.get("name", svc.get("type", "?"))
                    ver = svc.get("version", "")
                    ports = svc.get("ports", "")
                    click.echo(f"  {name} {ver}  ports={ports}")


@site.command(name="rename")
@click.argument("site_id")
@click.argument("name")
@handle_errors
def site_rename(site_id, name):
    """Rename a site."""
    resolved = resolve_site(site_id)
    from wp_local.local.utils.graphql_backend import rename_site
    result = rename_site(resolved, name)
    output(result, message=f"Renamed to: {result.get('name', name)}")


@site.command(name="add")
@handle_errors
def site_add():
    """Create a new Local site interactively."""
    from wp_local.local.core.site import get_new_site_defaults
    defaults = get_new_site_defaults()

    name = click.prompt("Site name")
    slug = name.lower().replace(" ", "-")

    sites_path = defaults["sites_path"] or "~/Local Sites"
    default_path = os.path.join(sites_path, name)
    path = os.path.expanduser(click.prompt("Site path", default=default_path))

    tld = defaults["tld"] or ".local"
    domain = click.prompt("Domain", default=f"{slug}{tld}")

    username = click.prompt("WP admin username", default="admin")
    password = click.prompt("WP admin password", hide_input=True)
    email = click.prompt("WP admin email", default=defaults["admin_email"] or "")
    php_version = click.prompt("PHP version (leave blank for default)", default="")

    from wp_local.local.utils.graphql_backend import add_site
    result = add_site(
        name=name,
        path=path,
        domain=domain,
        wp_admin_username=username,
        wp_admin_password=password,
        wp_admin_email=email,
        php_version=php_version if php_version else None,
    )
    output(result, message=f"Created site: {result.get('name', name)} (id={result.get('id', '?')})")


# ---------------------------------------------------------------------------
# wp passthrough command
# ---------------------------------------------------------------------------


@cli.command(name="wp", context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.argument("site", required=False)
@click.argument("wp_args", nargs=-1, type=click.UNPROCESSED)
@handle_errors
def wp_cmd(site, wp_args):
    """Run WP-CLI command on a site.

    Usage: wp-local wp SITE plugin list
    Or, from inside a site folder: wp-local wp plugin list
    """
    args = list(wp_args)
    site_id = None
    if site:
        # First arg may be a site name/id, or the start of the wp command
        # when running from inside a site folder.
        from wp_local.local.core.site import get_site_from_file
        match = get_site_from_file(site)
        if match:
            site_id = match["id"]
        else:
            args = [site] + args
    if site_id is None:
        site_id = resolve_site(None)
    from wp_local.local.utils.wpcli_backend import run_wp_cli
    result = run_wp_cli(site_id, args, capture_output=False)
    sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# db group
# ---------------------------------------------------------------------------


@cli.group()
def db():
    """Database operations (query, export, import)."""


@db.command(name="query")
@click.argument("site_id")
@click.argument("sql", required=False)
@json_option
@handle_errors
def db_query(site_id, sql, json_mode):
    """Run a SQL query on a site's database.

    Usage: wp-local db query SITE "SQL"
    Or, from inside a site folder: wp-local db query "SQL"
    """
    enable_command_json(json_mode)
    if sql is None:
        site_id, sql = None, site_id
    resolved = resolve_site(site_id)
    from wp_local.local.utils.mysql_backend import run_query
    rows = run_query(resolved, sql)
    if _json_output:
        output(rows)
    else:
        _print_rows_table(rows)


@db.command(name="export")
@click.argument("site_id")
@click.argument("output_path", required=False, default=None)
@handle_errors
def db_export(site_id, output_path):
    """Export a site's database to a SQL file."""
    resolved = resolve_site(site_id)
    if not output_path:
        from wp_local.local.core.site import get_site_from_file
        s = get_site_from_file(resolved)
        site_name = s["name"].lower().replace(" ", "-") if s else resolved
        today = date.today().isoformat()
        output_path = f"{site_name}-{today}.sql"
    from wp_local.local.utils.mysql_backend import export_db
    written = export_db(resolved, output_path)
    output({"path": written}, message=f"Exported to: {written}")


@db.command(name="import")
@click.argument("site_id")
@click.argument("file")
@handle_errors
def import_(site_id, file):
    """Import a SQL file into a site's database."""
    resolved = resolve_site(site_id)
    from wp_local.local.utils.mysql_backend import import_db
    import_db(resolved, file)
    output({}, message=f"Imported {file} into site {resolved}")


# ---------------------------------------------------------------------------
# log group
# ---------------------------------------------------------------------------


@cli.group()
def log():
    """View site logs."""


@log.command(name="tail")
@click.argument("site_id")
@click.argument("service", default="nginx")
@handle_errors
def log_tail(site_id, service):
    """Tail a site log file. Ctrl-C to stop."""
    resolved = resolve_site(site_id)
    from wp_local.local.core.site import get_log_path
    log_path = get_log_path(resolved, service)
    try:
        subprocess.run(["tail", "-f", log_path])
    except KeyboardInterrupt:
        pass


@log.command(name="show")
@click.argument("site_id")
@click.argument("service", default="nginx")
@click.option("-n", "lines", default=50, show_default=True, help="Number of lines to show")
@handle_errors
def log_show(site_id, service, lines):
    """Print the last N lines of a site log."""
    resolved = resolve_site(site_id)
    from wp_local.local.core.site import get_log_path
    log_path = get_log_path(resolved, service)
    result = subprocess.run(
        ["tail", "-n", str(lines), log_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Error reading log: {result.stderr.strip()}")
    click.echo(result.stdout, nl=False)


# ---------------------------------------------------------------------------
# jobs group
# ---------------------------------------------------------------------------


@cli.group()
def jobs():
    """Background job management."""


@jobs.command(name="list")
@json_option
@handle_errors
def jobs_list(json_mode):
    """List all background jobs in Local."""
    enable_command_json(json_mode)
    from wp_local.local.utils.graphql_backend import list_jobs
    job_list = list_jobs()
    if _json_output:
        output(job_list)
    else:
        if not job_list:
            click.echo("No jobs found.")
            return
        rows = [
            {
                "id": j.get("id", ""),
                "status": j.get("status", ""),
                "error": j.get("error") or "",
            }
            for j in job_list
        ]
        _print_rows_table(rows)


# ---------------------------------------------------------------------------
# session group
# ---------------------------------------------------------------------------


@cli.group()
def session():
    """Manage CLI session (active site, etc.)."""


@session.command(name="status")
@json_option
@handle_errors
def session_status(json_mode):
    """Show current session state."""
    enable_command_json(json_mode)
    s = get_session()
    data = s.to_dict()
    if _json_output:
        output(data)
    else:
        active = s.active_site_id or "(none)"
        click.echo(f"Active site: {active}")
        for k, v in data.items():
            if k != "active_site_id":
                click.echo(f"{k}: {v}")


@session.command(name="use")
@click.argument("site_id")
@handle_errors
def session_use(site_id):
    """Set the active site for the session."""
    from wp_local.local.core.site import resolve_site_id
    resolved = resolve_site_id(site_id)
    s = get_session()
    s.set_active_site(resolved)
    output({"active_site_id": resolved}, message=f"Active site set to: {resolved}")


@session.command(name="clear")
@handle_errors
def session_clear():
    """Clear the session state."""
    s = get_session()
    s.clear()
    output({}, message="Session cleared.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    cli()
