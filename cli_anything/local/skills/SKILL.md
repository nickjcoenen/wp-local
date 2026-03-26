---
name: "wp-local"
description: "Manage Local by Flywheel WordPress sites from the command line — start/stop sites, run WP-CLI, query MySQL, view logs"
---

# wp-local

CLI harness for Local by Flywheel. Lets AI agents manage WordPress local development sites headlessly.

## Prerequisites

- Local by Flywheel installed and running (for lifecycle commands)
- Python 3.9+

## Installation

```bash
pip install -e ~/Scripts/wp-local/agent-harness/
# or use the venv:
~/Scripts/wp-local/.venv/bin/wp-local
```

## Basic Usage

```bash
wp-local site list                          # List all sites
wp-local --json site list                   # JSON output
wp-local site start <site-id>               # Start a site
wp-local site stop <site-id>                # Stop a site
wp-local site restart <site-id>             # Restart a site
wp-local site info <site-id>                # Full site details
wp-local wp <site-id> plugin list           # Run WP-CLI
wp-local db query <site-id> "SELECT 1"      # Run MySQL query
wp-local db export <site-id>                # Export database
wp-local log tail <site-id>                 # Tail nginx log
wp-local session use <site-id>              # Set default site
```

## Command Groups

| Group | Purpose |
|-------|---------|
| `site` | List, start, stop, restart, rename, add sites |
| `wp`   | Passthrough to WP-CLI (any wp command) |
| `db`   | MySQL query, export, import |
| `log`  | View nginx/php/mysql logs |
| `jobs` | List Local background jobs |
| `session` | Set default site, show state |

## JSON Output

All commands support `--json` for machine-readable output:
```bash
wp-local --json site list
wp-local --json site info iw1zR_3qf
wp-local --json db query iw1zR_3qf "SHOW TABLES"
```

## Agent Guidance

1. Always use `--json` for programmatic output
2. Resolve site IDs with `wp-local --json site list` first
3. Check `status` field: `running` means services are up
4. WP-CLI commands stream output directly — use `wp` subcommand for WordPress operations
5. MySQL socket only available when site status is `running`
6. Auth token is read from `~/Library/Application Support/Local/graphql-connection-info.json` at runtime

## Known Site (current user)

| Field | Value |
|-------|-------|
| ID | iw1zR_3qf |
| Name | offimac |
| Domain | offimac.test |
| Path | /Users/nickcoenen/Dev/Sites/offimac |
