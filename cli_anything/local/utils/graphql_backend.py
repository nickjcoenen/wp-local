"""
graphql_backend.py — GraphQL client for Local by Flywheel's internal API.

Reads connection info from Local's graphql-connection-info.json and POSTs
queries/mutations to the local GraphQL endpoint.
"""

import json
import os

import requests

GRAPHQL_INFO_PATH = os.path.expanduser(
    "~/Library/Application Support/Local/graphql-connection-info.json"
)


def _load_connection_info() -> dict:
    """Read Local's GraphQL connection info JSON.

    Returns:
        dict with keys like 'url' and 'token'.

    Raises:
        RuntimeError: if the file doesn't exist (Local is not running or not installed).
    """
    if not os.path.exists(GRAPHQL_INFO_PATH):
        raise RuntimeError(
            f"GraphQL connection info not found at:\n  {GRAPHQL_INFO_PATH}\n"
            "Make sure Local by Flywheel is running."
        )
    with open(GRAPHQL_INFO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def gql(query: str, variables: dict = None) -> dict:
    """Execute a GraphQL query or mutation against Local's API.

    Args:
        query:     GraphQL query or mutation string.
        variables: Optional dict of GraphQL variables.

    Returns:
        The 'data' dict from the GraphQL response.

    Raises:
        RuntimeError: on connection failure, HTTP errors, or GraphQL errors.
    """
    info = _load_connection_info()
    url = info.get("url") or info.get("graphqlUrl") or info.get("endpoint")
    token = info.get("authToken") or info.get("token") or info.get("accessToken")

    if not url:
        raise RuntimeError(
            f"Could not determine GraphQL URL from connection info: {info}"
        )

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.ConnectionError as exc:
        raise RuntimeError(
            f"Could not connect to Local's GraphQL API at {url}.\n"
            "Make sure Local by Flywheel is running."
        ) from exc

    if not response.ok:
        raise RuntimeError(
            f"GraphQL HTTP error {response.status_code}: {response.text}"
        )

    body = response.json()

    if "errors" in body and body["errors"]:
        messages = "; ".join(e.get("message", str(e)) for e in body["errors"])
        raise RuntimeError(f"GraphQL errors: {messages}")

    return body.get("data", {})


# ---------------------------------------------------------------------------
# Site helpers
# ---------------------------------------------------------------------------

_SITE_FIELDS = """
    id
    name
    domain
    status
    path
    localVersion
    multiSite
    xdebugEnabled
    workspace
    services {
      name
      version
      type
      role
      ports
    }
"""


def list_sites() -> list[dict]:
    """Return all sites registered in Local.

    Returns:
        List of site dicts containing id, name, domain, status, path, etc.
    """
    data = gql(f"{{ sites {{ {_SITE_FIELDS} }} }}")
    return data.get("sites", [])


def get_site(site_id: str) -> dict | None:
    """Return the site with the given id, or None if not found.

    Args:
        site_id: Local site ID string.

    Returns:
        Site dict, or None.
    """
    for site in list_sites():
        if site.get("id") == site_id:
            return site
    return None


# ---------------------------------------------------------------------------
# Site lifecycle mutations
# ---------------------------------------------------------------------------

def start_site(site_id: str) -> dict:
    """Start a Local site.

    Args:
        site_id: Local site ID string.

    Returns:
        Dict with 'id' and 'status' fields from the mutation result.
    """
    data = gql('mutation { startSite(id: "%s") { id status } }' % site_id)
    return data.get("startSite", data)


def stop_site(site_id: str) -> dict:
    """Stop a running Local site.

    Args:
        site_id: Local site ID string.

    Returns:
        Dict with 'id' and 'status' fields from the mutation result.
    """
    data = gql('mutation { stopSite(id: "%s") { id status } }' % site_id)
    return data.get("stopSite", data)


def restart_site(site_id: str) -> dict:
    """Restart a Local site (stop then start).

    Args:
        site_id: Local site ID string.

    Returns:
        Dict with 'id' and 'status' fields from the mutation result.
    """
    data = gql('mutation { restartSite(id: "%s") { id status } }' % site_id)
    return data.get("restartSite", data)


def rename_site(site_id: str, name: str) -> dict:
    """Rename a Local site.

    Args:
        site_id: Local site ID string.
        name:    New display name for the site.

    Returns:
        Dict with the updated site fields.
    """
    data = gql('mutation { renameSite(id: "%s", name: "%s") { id name } }' % (site_id, name))
    return data.get("renameSite", data)


def add_site(
    name: str,
    path: str,
    domain: str,
    wp_admin_username: str,
    wp_admin_password: str,
    wp_admin_email: str,
    php_version: str = None,
) -> dict:
    """Create a new Local site.

    Args:
        name:               Display name for the site.
        path:               Local filesystem path for the site root.
        domain:             Local domain (e.g. mysite.local).
        wp_admin_username:  WordPress admin username.
        wp_admin_password:  WordPress admin password.
        wp_admin_email:     WordPress admin email address.
        php_version:        Optional PHP version string (e.g. '8.1.0').

    Returns:
        Dict representing the newly created site.
    """
    variables: dict = {
        "name": name,
        "path": path,
        "domain": domain,
        "wpAdminUsername": wp_admin_username,
        "wpAdminPassword": wp_admin_password,
        "wpAdminEmail": wp_admin_email,
    }
    if php_version is not None:
        variables["phpVersion"] = php_version

    query = """
    mutation AddSite(
        $name: String!
        $path: String!
        $domain: String!
        $wpAdminUsername: String!
        $wpAdminPassword: String!
        $wpAdminEmail: String!
        $phpVersion: String
    ) {
        addSite(input: {
            name: $name
            path: $path
            domain: $domain
            wpAdminUsername: $wpAdminUsername
            wpAdminPassword: $wpAdminPassword
            wpAdminEmail: $wpAdminEmail
            phpVersion: $phpVersion
        }) { id status }
    }
    """
    data = gql(query, variables=variables)
    return data.get("addSite", data)


# ---------------------------------------------------------------------------
# Job helpers
# ---------------------------------------------------------------------------

def list_jobs() -> list[dict]:
    """Return all background jobs tracked by Local.

    Returns:
        List of job dicts with 'id', 'status', and 'error' fields.
    """
    data = gql("{ jobs { id status error } }")
    return data.get("jobs", [])
