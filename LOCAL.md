# LOCAL — CLI Harness SOP for Local by Flywheel

## Overview

Local by Flywheel (v10+) is a proprietary Electron-based GUI application for managing WordPress local development environments. It orchestrates per-site stacks of PHP, MySQL, Nginx, and Mailpit using bundled "lightning service" binaries.

## Backend Interfaces

### 1. GraphQL API (Primary)

Local exposes an internal GraphQL API at `http://127.0.0.1:4000/graphql` (only available when Local.app is running).

- **Auth**: Bearer token from `~/Library/Application Support/Local/graphql-connection-info.json`
- **Token is rotated** on each Local startup — always read from the JSON file at call time

**Confirmed queries:**
```graphql
{ sites { id name domain status path localVersion multiSite xdebugEnabled workspace
          services { name version type role ports } } }
{ jobs { id status error } }
```

**Confirmed mutations:**
```graphql
mutation { startSite(id: "SITE_ID") { id status } }
mutation { stopSite(id: "SITE_ID") { id status } }
mutation { restartSite(id: "SITE_ID") { id status } }
mutation { renameSite(id: "SITE_ID", name: "new-name") { id name } }
mutation { addSite(input: {
  name: "mysite"
  path: "/Users/user/Dev/Sites/mysite"
  domain: "mysite.test"
  wpAdminUsername: "admin"
  wpAdminPassword: "password"
  wpAdminEmail: "admin@example.com"
  phpVersion: "8.2"   # optional
}) { id status } }
```

### 2. WP-CLI (WordPress Operations)

WP-CLI phar bundled with Local:
- **Binary**: `/Applications/Local.app/Contents/Resources/extraResources/bin/wp-cli/wp-cli.phar`
- **PHP**: Resolved from `~/Library/Application Support/Local/lightning-services/php-{version}+*/bin/darwin-arm64/bin/php`
- **Invocation**: `{php} {phar} --path={site_path}/app/public --allow-root {args}`
- **Required env**: `MYSQL_HOME={run_dir}/conf/mysql` so WP-CLI connects via the site's unix socket

### 3. MySQL (Direct Database Access)

Each running site has a MySQL unix socket:
- **Socket**: `~/Library/Application Support/Local/run/{site_id}/mysql/mysqld.sock`
- **Credentials**: user=`root`, password=`root`, database=`local`
- Use `mysql` CLI or PyMySQL for queries

### 4. Filesystem

- **Site configs**: `{site_path}/conf/` — Handlebars templates (source of truth)
- **Runtime configs**: `~/Library/Application Support/Local/run/{site_id}/conf/` — rendered versions
- **WordPress root**: `{site_path}/app/public/` (may be standard WP or Bedrock)
- **Logs**: `{site_path}/logs/{service}/` (nginx/error.log, php/error.log, php/php-fpm.log)
- **DB dump**: `{site_path}/app/sql/local.sql`

## Site Data Model

Sites are stored in `~/Library/Application Support/Local/sites.json`:

```json
{
  "SITE_ID": {
    "id": "SITE_ID",
    "name": "sitename",
    "path": "/path/to/site",
    "domain": "sitename.test",
    "localVersion": "10.0.0+6907",
    "mysql": { "database": "local", "user": "root", "password": "root" },
    "environment": "custom",
    "services": {
      "mailpit": { "name": "mailpit", "version": "1.24.1", "ports": { "WEB": [N], "SMTP": [N+1] } },
      "php":     { "name": "php",     "version": "8.5.3",  "role": "php" },
      "mysql":   { "name": "mysql",   "version": "8.0.35", "role": "db",   "ports": { "MYSQL": [N+2] } },
      "nginx":   { "name": "nginx",   "version": "1.26.1", "role": "http", "ports": { "HTTP": [N+3] } }
    }
  }
}
```

Status (running/halted) is in `site-statuses.json`.

## Request Flow

```
Browser/curl → Router nginx (port 80/443, root launchd service)
    → Site nginx (port N+3, e.g. 10004)
    → PHP-FPM (unix socket: run/{id}/php/php-fpm.socket)
    → MySQL (unix socket: run/{id}/mysql/mysqld.sock)
              + Mailpit SMTP (port N+1)
```

## Important Notes

- **Local.app must be running** for the GraphQL API to work. `site list` falls back to reading JSON files when the API is unavailable.
- **Ports are dynamic** — allocated at site creation and stored in `sites.json`. Never hardcode them.
- **PHP version** can differ per site and may be a downloaded version (not the bundled one).
- **WP root** may be `app/public/` (standard) or the document root set in the nginx config.
- **Site IDs** are short random strings (e.g. `iw1zR_3qf`). The CLI accepts either the ID or the site name.
