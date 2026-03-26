"""local_cli.py — Click CLI harness for Local by Flywheel.

Entry point: wp-local (registered via setup.py console_scripts)
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from datetime import date
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


def get_session():
    global _session
    if _session is None:
        from cli_anything.local.core.session import Session
        _session = Session.load()
    return _session


def resolve_site(id_or_name: str | None) -> str:
    """Resolve site ID from arg, session default, or error."""
    if id_or_name:
        from cli_anything.local.core.site import resolve_site_id
        return resolve_site_id(id_or_name)
    s = get_session()
    if s.active_site_id:
        return s.active_site_id
    raise click.UsageError("No site specified. Use --site or 'wp-local session use <id>'")


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


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
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
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ---------------------------------------------------------------------------
# site group
# ---------------------------------------------------------------------------


@cli.group()
def site():
    """Manage Local sites."""


@site.command(name="list")
def site_list():
    """List all sites."""
    try:
        from cli_anything.local.utils.graphql_backend import list_sites
        sites = list_sites()
    except RuntimeError:
        from cli_anything.local.core.site import list_sites_from_file
        sites = list_sites_from_file()

    if _json_output:
        output(sites)
    else:
        _print_sites_table(sites)


@site.command(name="status")
@click.argument("site_id", required=False)
def site_status(site_id):
    """Show running/halted status for a site."""
    try:
        resolved = resolve_site(site_id)
        from cli_anything.local.core.site import is_running, get_site_from_file
        running = is_running(resolved)
        s = get_site_from_file(resolved)
        name = s["name"] if s else resolved
        status_str = "running" if running else "halted"
        output({"id": resolved, "name": name, "status": status_str},
               message=f"{name} ({resolved}): {status_str}")
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


@site.command(name="start")
@click.argument("site_id")
def site_start(site_id):
    """Start a site."""
    try:
        resolved = resolve_site(site_id)
        from cli_anything.local.utils.graphql_backend import start_site
        result = start_site(resolved)
        output(result, message=f"Started: {result.get('id', resolved)} → {result.get('status', 'started')}")
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


@site.command(name="stop")
@click.argument("site_id")
def site_stop(site_id):
    """Stop a site."""
    try:
        resolved = resolve_site(site_id)
        from cli_anything.local.utils.graphql_backend import stop_site
        result = stop_site(resolved)
        output(result, message=f"Stopped: {result.get('id', resolved)} → {result.get('status', 'stopped')}")
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


@site.command(name="restart")
@click.argument("site_id")
def site_restart(site_id):
    """Restart a site."""
    try:
        resolved = resolve_site(site_id)
        from cli_anything.local.utils.graphql_backend import restart_site
        result = restart_site(resolved)
        output(result, message=f"Restarted: {result.get('id', resolved)} → {result.get('status', 'running')}")
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


@site.command(name="info")
@click.argument("site_id", required=False)
def site_info(site_id):
    """Show full site details including services and ports."""
    try:
        resolved = resolve_site(site_id)
        # Prefer GraphQL for live data; fall back to file.
        try:
            from cli_anything.local.utils.graphql_backend import get_site
            s = get_site(resolved)
        except RuntimeError:
            from cli_anything.local.core.site import get_site_from_file
            s = get_site_from_file(resolved)

        if s is None:
            click.echo(f"Site not found: {resolved}", err=True)
            return

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
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


@site.command(name="rename")
@click.argument("site_id")
@click.argument("name")
def site_rename(site_id, name):
    """Rename a site."""
    try:
        resolved = resolve_site(site_id)
        from cli_anything.local.utils.graphql_backend import rename_site
        result = rename_site(resolved, name)
        output(result, message=f"Renamed to: {result.get('name', name)}")
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


@site.command(name="add")
def site_add():
    """Create a new Local site interactively."""
    try:
        from cli_anything.local.core.site import get_new_site_defaults
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

        from cli_anything.local.utils.graphql_backend import add_site
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
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


# ---------------------------------------------------------------------------
# wp passthrough command
# ---------------------------------------------------------------------------


@cli.command(name="wp", context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.argument("site", required=False)
@click.argument("wp_args", nargs=-1, type=click.UNPROCESSED)
def wp_cmd(site, wp_args):
    """Run WP-CLI command on a site. Usage: wp-local wp SITE plugin list"""
    try:
        site_id = resolve_site(site)
        from cli_anything.local.utils.wpcli_backend import run_wp_cli
        result = run_wp_cli(site_id, list(wp_args), capture_output=False)
        sys.exit(result.returncode)
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# db group
# ---------------------------------------------------------------------------


@cli.group()
def db():
    """Database operations (query, export, import)."""


@db.command(name="query")
@click.argument("site_id")
@click.argument("sql")
def db_query(site_id, sql):
    """Run a SQL query on a site's database."""
    try:
        resolved = resolve_site(site_id)
        from cli_anything.local.utils.mysql_backend import run_query
        rows = run_query(resolved, sql)
        if _json_output:
            output(rows)
        else:
            _print_rows_table(rows)
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


@db.command(name="export")
@click.argument("site_id")
@click.argument("output_path", required=False, default=None)
def db_export(site_id, output_path):
    """Export a site's database to a SQL file."""
    try:
        resolved = resolve_site(site_id)
        if not output_path:
            from cli_anything.local.core.site import get_site_from_file
            s = get_site_from_file(resolved)
            site_name = s["name"].lower().replace(" ", "-") if s else resolved
            today = date.today().isoformat()
            output_path = f"{site_name}-{today}.sql"
        from cli_anything.local.utils.mysql_backend import export_db
        written = export_db(resolved, output_path)
        output({"path": written}, message=f"Exported to: {written}")
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


@db.command(name="import")
@click.argument("site_id")
@click.argument("file")
def import_(site_id, file):
    """Import a SQL file into a site's database."""
    try:
        resolved = resolve_site(site_id)
        from cli_anything.local.utils.mysql_backend import import_db
        import_db(resolved, file)
        output({}, message=f"Imported {file} into site {resolved}")
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


# ---------------------------------------------------------------------------
# log group
# ---------------------------------------------------------------------------


@cli.group()
def log():
    """View site logs."""


@log.command(name="tail")
@click.argument("site_id")
@click.argument("service", default="nginx")
def log_tail(site_id, service):
    """Tail a site log file. Ctrl-C to stop."""
    try:
        resolved = resolve_site(site_id)
        from cli_anything.local.core.site import get_log_path
        log_path = get_log_path(resolved, service)
        try:
            subprocess.run(["tail", "-f", log_path])
        except KeyboardInterrupt:
            pass
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


@log.command(name="show")
@click.argument("site_id")
@click.argument("service", default="nginx")
@click.option("-n", "lines", default=50, show_default=True, help="Number of lines to show")
def log_show(site_id, service, lines):
    """Print the last N lines of a site log."""
    try:
        resolved = resolve_site(site_id)
        from cli_anything.local.core.site import get_log_path
        log_path = get_log_path(resolved, service)
        result = subprocess.run(
            ["tail", "-n", str(lines), log_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            click.echo(f"Error reading log: {result.stderr.strip()}", err=True)
        else:
            click.echo(result.stdout, nl=False)
    except (RuntimeError, click.UsageError) as e:
        click.echo(f"Error: {e}", err=True)


# ---------------------------------------------------------------------------
# jobs group
# ---------------------------------------------------------------------------


@cli.group()
def jobs():
    """Background job management."""


@jobs.command(name="list")
def jobs_list():
    """List all background jobs in Local."""
    try:
        from cli_anything.local.utils.graphql_backend import list_jobs
        job_list = list_jobs()
        if _json_output:
            output(job_list)
        else:
            if not job_list:
                click.echo("No jobs found.")
                return
            headers = ["id", "status", "error"]
            rows = [
                {
                    "id": j.get("id", ""),
                    "status": j.get("status", ""),
                    "error": j.get("error") or "",
                }
                for j in job_list
            ]
            _print_rows_table(rows)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)


# ---------------------------------------------------------------------------
# session group
# ---------------------------------------------------------------------------


@cli.group()
def session():
    """Manage CLI session (active site, etc.)."""


@session.command(name="status")
def session_status():
    """Show current session state."""
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
def session_use(site_id):
    """Set the active site for the session."""
    try:
        from cli_anything.local.core.site import resolve_site_id
        resolved = resolve_site_id(site_id)
        s = get_session()
        s.set_active_site(resolved)
        output({"active_site_id": resolved}, message=f"Active site set to: {resolved}")
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)


@session.command(name="clear")
def session_clear():
    """Clear the session state."""
    s = get_session()
    s.clear()
    output({}, message="Session cleared.")


# ---------------------------------------------------------------------------
# repl command
# ---------------------------------------------------------------------------


@cli.command(hidden=True)
def repl():
    """Interactive REPL mode."""
    from cli_anything.local.utils.repl_skin import ReplSkin
    skin = ReplSkin("local", version="1.0.0")
    skin.print_banner()

    pt_session = skin.create_prompt_session()
    s = get_session()

    while True:
        try:
            active_site = s.active_site_id or "no site"
            line = skin.get_input(pt_session, project_name=active_site)
            if not line.strip():
                continue
            if line.strip().lower() in ("exit", "quit", "q"):
                skin.print_goodbye()
                break
            if line.strip() == "help":
                skin.help({
                    "site list": "List all sites",
                    "site start/stop/restart SITE": "Manage site lifecycle",
                    "site info SITE": "Show site details",
                    "wp SITE <cmd>": "Run WP-CLI command",
                    "db query SITE <sql>": "Run MySQL query",
                    "db export/import SITE": "Database backup/restore",
                    "log tail/show SITE [service]": "View logs",
                    "jobs list": "Show running jobs",
                    "session use SITE": "Set active site",
                    "exit/quit": "Exit REPL",
                })
                continue

            # Parse and invoke via Click
            args = shlex.split(line)
            try:
                cli.main(
                    args=args,
                    standalone_mode=False,
                    obj={"site": s.active_site_id},
                )
            except click.UsageError as e:
                skin.error(str(e))
            except SystemExit:
                pass
            except Exception as e:
                skin.error(str(e))
        except (KeyboardInterrupt, EOFError):
            skin.print_goodbye()
            break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    cli()
