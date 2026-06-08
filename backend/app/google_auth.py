"""Load Google credentials for GSC + GA4 (OAuth user token or service account).

OAuth is preferred when a refresh-token file exists (personal Google account).
Falls back to GOOGLE_APPLICATION_CREDENTIALS service-account JSON when present.
"""

from __future__ import annotations  # Forward references for typing

import json  # Read/write the OAuth token file
from pathlib import Path  # Resolve credential file paths

from google.auth.transport.requests import Request  # Refresh expired OAuth access tokens
from google.oauth2.credentials import Credentials  # User OAuth credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials  # SA credentials

from app.config import PROJECT_ROOT, Settings  # Application settings + project root

# Read-only scopes for Search Console and GA4 Data API
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",  # GSC read
    "https://www.googleapis.com/auth/analytics.readonly",  # GA4 read
]


def oauth_token_path(settings: Settings) -> Path:
    """Path to the saved OAuth refresh-token JSON."""
    if settings.google_oauth_token_path:
        return Path(settings.google_oauth_token_path)
    return PROJECT_ROOT / "secrets" / "google-oauth-token.json"


def oauth_client_secrets_path(settings: Settings) -> Path:
    """Path to the OAuth desktop-client secrets JSON from Google Cloud Console."""
    if settings.google_oauth_client_secrets:
        return Path(settings.google_oauth_client_secrets)
    # Default location, then common mistake: project root instead of secrets/
    default = PROJECT_ROOT / "secrets" / "google-oauth-client.json"
    if default.exists():
        return default
    root_copy = PROJECT_ROOT / "google-oauth-client.json"
    if root_copy.exists():
        return root_copy
    return default  # Expected path (may not exist yet)


def google_credentials_available(settings: Settings) -> bool:
    """Return True when OAuth token or service-account JSON is configured."""
    return oauth_token_path(settings).exists() or _service_account_path(settings).exists()


def load_google_credentials(settings: Settings):
    """Return refreshed Google credentials, or None when nothing is configured.

    Priority: OAuth refresh token file, then service-account JSON key.
    """
    token_path = oauth_token_path(settings)  # Saved user OAuth token
    if token_path.exists():  # OAuth takes priority for personal/single-owner sites
        return _load_oauth_credentials(token_path, settings)

    sa_path = _service_account_path(settings)  # Service-account JSON key
    if sa_path.exists():  # Agency / multi-tenant fallback
        return ServiceAccountCredentials.from_service_account_file(str(sa_path), scopes=GOOGLE_SCOPES)

    return None  # No credentials configured


def save_oauth_token(token_path: Path, creds: Credentials) -> None:
    """Persist OAuth credentials (including refresh token) to disk."""
    token_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure secrets/ exists
    payload = {  # Fields needed to restore and refresh the session
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or GOOGLE_SCOPES),
    }
    token_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _service_account_path(settings: Settings) -> Path:
    """Resolve the service-account JSON path from settings."""
    if not settings.google_application_credentials:
        return Path("__missing__")  # Non-existent sentinel
    return Path(settings.google_application_credentials)


def _load_oauth_credentials(token_path: Path, settings: Settings):
    """Load OAuth credentials from disk and refresh if the access token expired."""
    data = json.loads(token_path.read_text(encoding="utf-8"))  # Parse saved token

    # Backfill client_id/secret from desktop-client JSON when absent from token file
    if not data.get("client_id"):
        secrets_path = oauth_client_secrets_path(settings)
        if secrets_path.exists():
            block = json.loads(secrets_path.read_text(encoding="utf-8"))
            installed = block.get("installed") or block.get("web") or {}
            data["client_id"] = installed.get("client_id", "")
            data["client_secret"] = installed.get("client_secret", "")

    creds = Credentials.from_authorized_user_info(data, scopes=GOOGLE_SCOPES)  # Restore session

    if creds.expired and creds.refresh_token:  # Access token stale but refreshable
        creds.refresh(Request())  # Obtain a fresh access token
        save_oauth_token(token_path, creds)  # Persist updated token

    return creds
