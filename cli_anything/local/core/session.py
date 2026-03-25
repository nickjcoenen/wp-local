"""Session state management for cli-local.

Persists the active site and other metadata to ~/.cli-local/session.json
so the selection survives between CLI invocations.
"""

import json
import os

SESSION_DIR = os.path.expanduser("~/.cli-local")
SESSION_FILE = os.path.join(SESSION_DIR, "session.json")


def _locked_save_json(path: str, data: dict) -> None:
    """Write *data* to *path* as JSON, using an exclusive file lock when possible.

    Creates parent directories automatically.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    try:
        f = open(path, "r+")
    except FileNotFoundError:
        f = open(path, "w")
    with f:
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=2)
        f.flush()
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (NameError, OSError):
            pass


class Session:
    """Lightweight session state stored in SESSION_FILE."""

    def __init__(self) -> None:
        self.active_site_id: str | None = None
        self._data: dict = {}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> "Session":
        """Load session from disk, or return an empty session if not found."""
        session = cls()
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as fh:
                data: dict = json.load(fh)
        except (FileNotFoundError, PermissionError, json.JSONDecodeError):
            data = {}
        session._data = data
        session.active_site_id = data.get("active_site_id")
        return session

    def save(self) -> None:
        """Persist current session state to disk."""
        _locked_save_json(SESSION_FILE, self.to_dict())

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def set_active_site(self, site_id: str) -> None:
        """Set the active site and immediately persist."""
        self.active_site_id = site_id
        self._data["active_site_id"] = site_id
        self.save()

    def clear(self) -> None:
        """Clear all session state and persist."""
        self.active_site_id = None
        self._data = {}
        self.save()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation of the session."""
        return {
            **self._data,
            "active_site_id": self.active_site_id,
        }

    # ------------------------------------------------------------------
    # Conveniences
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"Session(active_site_id={self.active_site_id!r})"
