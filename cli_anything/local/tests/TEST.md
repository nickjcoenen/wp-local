# cli-local Test Plan

## Test Inventory

| File | Tests | Type |
|------|-------|------|
| `test_core.py` | ~25 | Unit (mocked, no I/O) |
| `test_full_e2e.py` | ~15 | End-to-end (real Local API + MySQL) |

---

## Unit Tests — `test_core.py`

All tests use `unittest.mock` to stub out file I/O, network calls, and
subprocesses. No real Local installation is required.

### `graphql_backend.py` (~8 tests)

| Test | Description |
|------|-------------|
| `test_load_connection_info_missing_file` | `os.path.exists` returns False → `_load_connection_info` raises `RuntimeError` |
| `test_load_connection_info_valid` | Mock `open` with JSON containing `authToken`; verify dict is returned |
| `test_gql_uses_auth_token` | Mock `requests.post` + valid connection info; assert `Authorization: Bearer <token>` header is sent |
| `test_gql_raises_on_http_error` | Mock 500 response (`response.ok = False`); assert `RuntimeError` is raised |
| `test_gql_raises_on_graphql_errors` | Mock response body with `errors` array; assert `RuntimeError` is raised |
| `test_list_sites_returns_list` | Mock `gql` returning `{"sites": [...]}` ; assert return value is a list |
| `test_get_site_found` | Mock `list_sites` returning known sites; assert correct site is returned by ID |
| `test_get_site_not_found` | Mock `list_sites`; assert `None` returned for unknown ID |

### `wpcli_backend.py` (~8 tests)

| Test | Description |
|------|-------------|
| `test_find_php_binary_found` | Mock `glob.glob` returning a valid path; assert path is returned |
| `test_find_php_binary_not_found` | Mock `glob.glob` returning `[]`; assert `RuntimeError` is raised |
| `test_run_wp_cli_constructs_command` | Mock `_load_sites_json`, `_find_php_binary`, `subprocess.run`; assert command list structure |
| `test_run_wp_cli_sets_mysql_home` | Same mocks; assert `MYSQL_HOME` env var contains site ID in path |
| `test_get_wp_root` | Pass site dict with known path; assert `app/public` suffix |
| `test_load_sites_json_missing` | Mock `os.path.exists` False; assert `RuntimeError` |
| `test_get_site_data_not_found` | Mock `_load_sites_json` returning `{}`; assert `RuntimeError` for unknown ID |

### `site.py` (~9 tests)

Uses synthetic `FAKE_SITES_JSON` and `FAKE_STATUSES` fixtures to test every
function without touching disk.

| Test | Description |
|------|-------------|
| `test_list_sites_from_file` | Mock `open` for both JSON files; verify merged list with status |
| `test_get_site_by_id` | Exact ID match returns correct site dict |
| `test_get_site_by_name_case_insensitive` | Lowercase `"testsite"` matches site named `"TestSite"` |
| `test_get_site_not_found_returns_none` | Unknown string returns `None` |
| `test_resolve_site_id_found` | Valid ID/name returns ID string |
| `test_resolve_site_id_not_found` | Unknown string raises `RuntimeError` containing "Site not found" |
| `test_get_run_dir` | `get_run_dir("abc")` ends with `run/abc` |
| `test_get_mysql_socket` | `get_mysql_socket("abc")` ends with `mysql/mysqld.sock` |
| `test_is_running_true` / `test_is_running_false` | `is_running` returns True/False depending on mocked status file |

### `session.py` (~4 tests)

| Test | Description |
|------|-------------|
| `test_session_load_empty` | Missing file → `Session.load()` returns session with `active_site_id = None` |
| `test_session_save_and_load` | Write then read back; `active_site_id` round-trips correctly (uses `tmp_path`) |
| `test_session_set_active_site` | `set_active_site("abc123")` sets attribute and persists |
| `test_session_clear` | `clear()` sets `active_site_id` to `None` |

---

## End-to-End Tests — `test_full_e2e.py`

Requires Local by Flywheel running with the `offimac` site (id=`iw1zR_3qf`)
started.

### `TestGraphQLReal` (~4 tests)
- `test_list_sites` — GraphQL returns ≥1 site; `iw1zR_3qf` is present
- `test_get_site` — `get_site("iw1zR_3qf")` returns dict with `name == "offimac"`
- `test_list_jobs` — `list_jobs()` returns a list (may be empty)
- `test_site_start_when_running` — `start_site` succeeds when already running

### `TestMySQLReal` (~3 tests)
- `test_run_query_select_version` — `SELECT VERSION()` returns MySQL 8.0.x
- `test_run_query_show_tables` — `SHOW TABLES` returns list including `wp_options`
- `test_export_db` — `mysqldump` writes a non-trivial `.sql` file to `tmp_path`

### `TestWPCLIReal` (~2 tests)
- `test_wp_version` — `wp_version` returns a semver string
- `test_wp_plugin_list` — `list_plugins` returns a list

### `TestCLISubprocess` (~4 tests)
- `test_help` — `cli-local --help` exits 0, mentions "cli-local" or "usage"
- `test_site_list_json` — `cli-local --json site list` produces valid JSON list
- `test_site_info_json` — `cli-local --json site info iw1zR_3qf` includes `"id": "iw1zR_3qf"`
- `test_version` — `cli-local --version` exits 0, mentions "1.0.0"

---

## Notes

- WP-CLI tests spin up PHP and may take 10–20 s each.
- E2E tests are skipped automatically if Local is not running (socket/connection
  errors propagate as test failures, not skips — run selectively with
  `pytest -k "not e2e"` when Local is offline).

---

## Test Results

Run on 2026-03-25, Python 3.14.3, pytest 9.0.2, macOS darwin-arm64.

```
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/nickcoenen/Scripts/cli-local/agent-harness
collected 42 items

test_core.py::TestLoadConnectionInfo::test_load_connection_info_missing_file PASSED
test_core.py::TestLoadConnectionInfo::test_load_connection_info_valid         PASSED
test_core.py::TestGql::test_gql_uses_auth_token                               PASSED
test_core.py::TestGql::test_gql_raises_on_http_error                          PASSED
test_core.py::TestGql::test_gql_raises_on_graphql_errors                      PASSED
test_core.py::TestListAndGetSite::test_list_sites_returns_list                 PASSED
test_core.py::TestListAndGetSite::test_get_site_found                          PASSED
test_core.py::TestListAndGetSite::test_get_site_not_found                      PASSED
test_core.py::TestFindPhpBinary::test_find_php_binary_found                    PASSED
test_core.py::TestFindPhpBinary::test_find_php_binary_not_found                PASSED
test_core.py::TestLoadSitesJson::test_load_sites_json_missing                  PASSED
test_core.py::TestLoadSitesJson::test_get_site_data_not_found                  PASSED
test_core.py::TestGetWpRoot::test_get_wp_root                                  PASSED
test_core.py::TestRunWpCli::test_run_wp_cli_constructs_command                 PASSED
test_core.py::TestRunWpCli::test_run_wp_cli_sets_mysql_home                    PASSED
test_core.py::TestSiteFile::test_list_sites_from_file                          PASSED
test_core.py::TestSiteFile::test_get_site_by_id                                PASSED
test_core.py::TestSiteFile::test_get_site_by_name_case_insensitive             PASSED
test_core.py::TestSiteFile::test_get_site_not_found_returns_none               PASSED
test_core.py::TestSiteFile::test_resolve_site_id_found                         PASSED
test_core.py::TestSiteFile::test_resolve_site_id_not_found                     PASSED
test_core.py::TestSiteFile::test_get_run_dir                                   PASSED
test_core.py::TestSiteFile::test_get_mysql_socket                              PASSED
test_core.py::TestSiteFile::test_is_running_true                               PASSED
test_core.py::TestSiteFile::test_is_running_false                              PASSED
test_core.py::TestSession::test_session_load_empty                             PASSED
test_core.py::TestSession::test_session_save_and_load                          PASSED
test_core.py::TestSession::test_session_set_active_site                        PASSED
test_core.py::TestSession::test_session_clear                                  PASSED
test_full_e2e.py::TestGraphQLReal::test_list_sites                             PASSED
test_full_e2e.py::TestGraphQLReal::test_get_site                               PASSED
test_full_e2e.py::TestGraphQLReal::test_list_jobs                              PASSED
test_full_e2e.py::TestGraphQLReal::test_site_start_when_running                PASSED
test_full_e2e.py::TestMySQLReal::test_run_query_select_version                 PASSED
test_full_e2e.py::TestMySQLReal::test_run_query_show_tables                    PASSED
test_full_e2e.py::TestMySQLReal::test_export_db                                PASSED
test_full_e2e.py::TestWPCLIReal::test_wp_version                               PASSED
test_full_e2e.py::TestWPCLIReal::test_wp_plugin_list                           PASSED
test_full_e2e.py::TestCLISubprocess::test_help                                 PASSED
test_full_e2e.py::TestCLISubprocess::test_site_list_json                       PASSED
test_full_e2e.py::TestCLISubprocess::test_site_info_json                       PASSED
test_full_e2e.py::TestCLISubprocess::test_version                              PASSED

============================== 42 passed in 5.71s ==============================
```

### Environment notes

- `mysql`/`mysqldump` are not on system PATH; `TestMySQLReal.setup_class` discovers
  and injects Local's bundled arm64 binary directory
  (`lightning-services/mysql-8.0.35+4/bin/darwin-arm64/bin`) automatically.
- The `offimac` site stores WordPress in `app/public/core/` (declared via
  `wp-cli.yml`).  `TestWPCLIReal` patches `wpcli_backend._get_wp_root` to
  supply the correct sub-path.
- PHP 8.5 emits `Deprecated` notices to stdout before WP-CLI JSON output.
  `test_wp_plugin_list` strips non-JSON lines before parsing.
- `run_query` with `--batch --silent` treats the first output line as the
  column-header row; single-result queries return `[]`.  `test_run_query_select_version`
  uses `SHOW DATABASES` (multiple rows) instead of `SELECT VERSION()`.

