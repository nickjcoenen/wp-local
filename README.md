<p align="center">
  <img src=".github/assets/local-icon.png" width="96" alt="Local by Flywheel" />
</p>

<h1 align="center">wp-local</h1>

<p align="center">
  A headless CLI for <a href="https://localwp.com/">Local by Flywheel</a> — manage WordPress sites from the terminal.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/platform-macOS-lightgrey?logo=apple&logoColor=white" alt="macOS" />
  <img src="https://img.shields.io/badge/Local-10%2B-brightgreen" alt="Local 10+" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License" />
</p>

---

`wp-local` wraps Local's internal GraphQL API, bundled WP-CLI, and MySQL socket into a single `wp-local` command. Start and stop sites, run WP-CLI commands, query the database, tail logs — all without touching the Local GUI. Works great for scripting, CI workflows, and AI agents.

```
$ wp-local site list
ID         Name     Domain        Status
-----------------------------------------
iw1zR_3qf  offimac  offimac.test  running

$ wp-local wp offimac plugin list --format=table
+---------+-----------------------------+-----------+---------+
| name    | title                       | status    | version |
+---------+-----------------------------+-----------+---------+
| acf     | Advanced Custom Fields      | active    | 6.3.1   |
| yoast   | Yoast SEO                   | active    | 22.4    |
+---------+-----------------------------+-----------+---------+

$ wp-local db query offimac "SELECT option_value FROM wp_options WHERE option_name='siteurl'"
+-----------------------+
| option_value          |
+-----------------------+
| https://offimac.test  |
+-----------------------+
```

## Requirements

- **macOS** (uses Local's macOS app bundle)
- **[Local by Flywheel](https://localwp.com/) v10+** installed
- **Python 3.9+**
- Local app must be **running** for lifecycle commands (`start`, `stop`, `restart`, `add`). Read-only commands (`site list`, `site info`, `log show`) work offline.

## Installation

**With [pipx](https://pipx.pypa.io/) — recommended (isolated, no venv needed):**

```bash
pipx install git+https://github.com/nickjcoenen/wp-local.git
```

**With pip:**

```bash
pip install git+https://github.com/nickjcoenen/wp-local.git
```

**Update:**

```bash
pipx upgrade wp-local
# or
pip install --upgrade git+https://github.com/nickjcoenen/wp-local.git
```

## Quick Start

```bash
# List all your Local sites
wp-local site list

# Start / stop / restart
wp-local site start my-site
wp-local site stop  my-site
wp-local site restart my-site

# Full site details (services, ports, PHP/MySQL versions)
wp-local site info my-site

# Run any WP-CLI command
wp-local wp my-site plugin list
wp-local wp my-site option get siteurl
wp-local wp my-site search-replace 'http://' 'https://'

# Query the database directly
wp-local db query my-site "SELECT ID, post_title FROM wp_posts LIMIT 5"

# Export / import database
wp-local db export my-site
wp-local db export my-site ~/backups/before-update.sql
wp-local db import my-site ~/backups/before-update.sql

# Tail logs in real time
wp-local log tail my-site          # nginx (default)
wp-local log tail my-site php      # PHP errors
wp-local log show my-site nginx -n 100

# Set a default site so you can skip the site argument
wp-local session use my-site
wp-local site status               # uses default
wp-local wp plugin list            # uses default
```

## Command Reference

### `site`

| Command | Description |
|---------|-------------|
| `site list` | List all sites with ID, name, domain, and status. Falls back to Local's JSON files when Local is not running. |
| `site status [SITE]` | Show running/halted status for a site. |
| `site start <SITE>` | Start a site (requires Local running). |
| `site stop <SITE>` | Stop a running site. |
| `site restart <SITE>` | Restart a site. |
| `site info [SITE]` | Full details: path, services, ports, PHP/MySQL/nginx versions. |
| `site rename <SITE> <NAME>` | Rename a site. |
| `site add` | Interactive wizard to provision a new WordPress site. |

`SITE` can be either the site ID (e.g. `iw1zR_3qf`) or the site name (e.g. `offimac`).

---

### `wp`

Passthrough to WP-CLI. The correct PHP binary and WordPress root are resolved automatically from Local's config.

```bash
wp-local wp <SITE> <wp-cli args…>
```

Examples:

```bash
wp-local wp my-site core version
wp-local wp my-site plugin install woocommerce --activate
wp-local wp my-site user create bob bob@example.com --role=editor
wp-local wp my-site cache flush
wp-local wp my-site cron event run --due-now
```

---

### `db`

| Command | Description |
|---------|-------------|
| `db query <SITE> <SQL>` | Execute a SQL statement. Output as table (default) or JSON with `--json`. |
| `db export <SITE> [FILE]` | Dump the database to a `.sql` file. Defaults to `{site}-{date}.sql`. |
| `db import <SITE> <FILE>` | Import a `.sql` file into the site's database. |

Connects via the site's MySQL unix socket — no port forwarding needed.

---

### `log`

| Command | Description |
|---------|-------------|
| `log tail <SITE> [SERVICE]` | Follow a log file in real time (Ctrl-C to stop). Default service: `nginx`. |
| `log show <SITE> [SERVICE] [-n N]` | Print the last N lines. Default: 50 lines, `nginx`. |

Available services: `nginx`, `php`, `mysql`.

---

### `jobs`

| Command | Description |
|---------|-------------|
| `jobs list` | List background jobs tracked by Local (e.g. site provisioning). |

---

### `session`

Set a default site so you don't have to type it for every command.

| Command | Description |
|---------|-------------|
| `session use <SITE>` | Set the active site. Saved to `~/.wp-local/session.json`. |
| `session status` | Show the current session. |
| `session clear` | Clear the session. |

---

## JSON Output

Add `--json` before any subcommand for machine-readable output — useful for scripting and AI agents:

```bash
wp-local --json site list
wp-local --json site info my-site
wp-local --json db query my-site "SHOW TABLES"
wp-local --json jobs list
```

---

## Interactive REPL

Running `wp-local` with no arguments launches an interactive REPL with history, autocompletion, and a status prompt:

```
$ wp-local
┌─────────────────────────────────┐
│  wp-local  v1.0.0               │
│  Type 'help' for commands       │
└─────────────────────────────────┘
local (offimac) › site list
...
local (offimac) › wp plugin list
...
local (offimac) › exit
```

---

## How it works

`wp-local` talks to Local through three interfaces:

| Interface | Used for |
|-----------|----------|
| **GraphQL API** (`localhost:4000`) | Site lifecycle — start, stop, restart, list, add, rename |
| **WP-CLI** (bundled with Local) | All WordPress operations |
| **MySQL unix socket** | Direct database queries, export, import |

The GraphQL auth token is read automatically from `~/Library/Application Support/Local/graphql-connection-info.json` — no configuration needed.

---

## License

MIT
