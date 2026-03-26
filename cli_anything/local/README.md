# wp-local

`wp-local` is a headless command-line harness for [Local by Flywheel](https://localwp.com/). It wraps Local's internal GraphQL API, WP-CLI, and MySQL to let you list, start, stop, and inspect WordPress sites; run arbitrary WP-CLI commands; execute SQL queries; export and import databases; and tail service logs — all from a terminal, with an optional interactive REPL and JSON output mode for scripting.

---

## Prerequisites

- **Local by Flywheel** must be installed. Lifecycle commands (`start`, `stop`, `restart`, `rename`, `add`) also require the Local app to be **running** so its GraphQL API is reachable. Read-only commands (`site list`, `site info`, `log show`) fall back to Local's JSON files and work without the app running.
- **Python 3.9+**
- **WP-CLI commands** require the target site to be running.
- **Database commands** require the target site to be running (MySQL socket must exist).

---

## Installation

**With pipx (recommended — isolated, no venv management):**

```bash
pipx install git+https://github.com/nickjcoenen/wp-local.git
```

**With pip:**

```bash
pip install git+https://github.com/nickjcoenen/wp-local.git
```

**Update to the latest version:**

```bash
pipx upgrade wp-local
# or
pip install --upgrade git+https://github.com/nickjcoenen/wp-local.git
```

> **Note:** macOS only. Requires [Local by Flywheel](https://localwp.com/) to be installed.

---

## Quick Start

```bash
# List all sites
wp-local site list

# Start / stop / restart a site (by ID or name)
wp-local site start my-site
wp-local site stop  my-site
wp-local site restart my-site

# Show full site details
wp-local site info my-site

# Run a WP-CLI command
wp-local wp my-site plugin list
wp-local wp my-site option get siteurl
wp-local wp my-site user list --format=table

# Run a SQL query
wp-local db query my-site "SELECT ID, post_title FROM wp_posts LIMIT 5"

# Export / import database
wp-local db export my-site
wp-local db export my-site /tmp/backup.sql
wp-local db import my-site /tmp/backup.sql

# Tail nginx log (Ctrl-C to stop)
wp-local log tail my-site
wp-local log tail my-site php

# Show last 100 lines of a log
wp-local log show my-site nginx -n 100

# Set a default active site for the session
wp-local session use my-site

# After setting an active site, the SITE argument is optional
wp-local site status
wp-local db query "SELECT option_value FROM wp_options WHERE option_name='siteurl'"
```

---

## Command Reference

### `site`

| Command | Description |
|---|---|
| `site list` | List all sites (ID, Name, Domain, Status). Falls back to Local's JSON files when Local is not running. |
| `site status [SITE]` | Show running/halted status. |
| `site start <SITE>` | Start a site via GraphQL. |
| `site stop <SITE>` | Stop a site via GraphQL. |
| `site restart <SITE>` | Restart a site via GraphQL. |
| `site info [SITE]` | Full details: path, services, ports, PHP/MySQL/nginx versions. |
| `site rename <SITE> <NAME>` | Rename a site via GraphQL. |
| `site add` | Interactive wizard to create a new site. |

### `wp`

Passthrough to WP-CLI. The site's PHP binary and WordPress root are resolved automatically.

```
wp-local wp SITE <wp-cli args...>
```

### `db`

| Command | Description |
|---|---|
| `db query <SITE> <SQL>` | Execute a SQL statement and print results as a table or JSON. |
| `db export <SITE> [OUTPUT]` | Dump the database to a `.sql` file. Defaults to `{site}-{date}.sql`. |
| `db import <SITE> <FILE>` | Import a `.sql` file into the site's database. |

### `log`

| Command | Description |
|---|---|
| `log tail <SITE> [SERVICE]` | Follow a log file in real time (default service: `nginx`). |
| `log show <SITE> [SERVICE] [-n N]` | Print the last N lines of a log (default: 50 lines, default service: `nginx`). |

### `jobs`

| Command | Description |
|---|---|
| `jobs list` | List all background jobs tracked by Local (requires Local running). |

### `session`

| Command | Description |
|---|---|
| `session use <SITE>` | Set the default active site. Persisted to `~/.wp-local/session.json`. |
| `session status` | Show current session state. |
| `session clear` | Clear the session. |

---

## JSON Output Mode

Add `--json` before any subcommand to receive machine-readable JSON output:

```bash
wp-local --json site list
wp-local --json site info my-site
wp-local --json db query my-site "SELECT * FROM wp_options LIMIT 3"
wp-local --json jobs list
```

---

## Session / Default Site

Set a default site once so you don't have to repeat the site argument:

```bash
wp-local session use abc123xyz   # accepts site ID or name
wp-local site status             # uses active site automatically
wp-local wp plugin list          # same
```

Session state is stored in `~/.wp-local/session.json`.

---

## Interactive REPL

Running `wp-local` with no subcommand launches an interactive REPL:

```bash
wp-local
```

Inside the REPL, type `help` for a command summary, or any `wp-local` command without the `wp-local` prefix. Type `exit` or `quit` to leave.

---

## Architecture

```
cli_anything/local/
├── local_cli.py          ← Click CLI (this package's entry point)
├── core/
│   ├── site.py           ← File-based site data (works offline)
│   ├── session.py        ← Session persistence (~/.wp-local/session.json)
│   └── wordpress.py      ← WP-CLI convenience wrappers
└── utils/
    ├── graphql_backend.py ← Local's internal GraphQL API
    ├── wpcli_backend.py   ← WP-CLI subprocess runner
    ├── mysql_backend.py   ← MySQL query / export / import
    └── repl_skin.py       ← Shared REPL UI (banner, prompt, table output)
```
