---
name: "cli-local"
description: "Manage Local by Flywheel WordPress sites from the command line — start/stop sites, run WP-CLI, query MySQL, view logs"
---

# cli-local

CLI harness for Local by Flywheel. Lets AI agents manage WordPress local development sites headlessly.

## Prerequisites

- Local by Flywheel installed and running (for lifecycle commands)
- Python 3.9+

## Installation

```bash
pip install -e ~/Scripts/cli-local/agent-harness/
# or use the venv:
~/Scripts/cli-local/.venv/bin/cli-local
```

## Basic Usage

```bash
cli-local site list                          # List all sites
cli-local --json site list                   # JSON output
cli-local site start <site-id>               # Start a site
cli-local site stop <site-id>                # Stop a site
cli-local site restart <site-id>             # Restart a site
cli-local site info <site-id>                # Full site details
cli-local wp <site-id> plugin list           # Run WP-CLI
cli-local db query <site-id> "SELECT 1"      # Run MySQL query
cli-local db export <site-id>                # Export database
cli-local log tail <site-id>                 # Tail nginx log
cli-local session use <site-id>              # Set default site
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
cli-local --json site list
cli-local --json site info iw1zR_3qf
cli-local --json db query iw1zR_3qf "SHOW TABLES"
```

## Agent Guidance

1. Always use `--json` for programmatic output
2. Resolve site IDs with `cli-local --json site list` first
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
