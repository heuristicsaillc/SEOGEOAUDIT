#!/usr/bin/env python3
"""One-time OAuth sign-in for Google Search Console + GA4 (personal Google account).

Run from the backend directory after placing your OAuth desktop-client JSON at
secrets/google-oauth-client.json (see README Connected mode section).

Usage:
    cd backend && source .venv/bin/activate
    python scripts/google_auth.py              # full browser sign-in
    python scripts/google_auth.py --list-only  # re-list GSC/GA4 using saved token
"""

from __future__ import annotations  # Forward references for typing

import argparse  # CLI flags
import json  # Parse client secrets JSON
import re  # Extract API enable URL from error messages
import sys  # Exit codes + path setup
from pathlib import Path  # Resolve secrets paths

# Allow `from app.*` when invoked as `python scripts/google_auth.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_auth_oauthlib.flow import InstalledAppFlow  # Desktop OAuth browser flow
from googleapiclient.discovery import build  # GSC + Analytics Admin API clients

from app.config import PROJECT_ROOT, get_settings  # Settings + project root
from app.google_auth import (  # OAuth helpers
    GOOGLE_SCOPES,
    load_google_credentials,
    oauth_client_secrets_path,
    oauth_token_path,
    save_oauth_token,
)


def main() -> int:
    """Run the OAuth flow, save the token, and print accessible GSC/GA4 resources."""
    parser = argparse.ArgumentParser(description="OAuth sign-in for GSC + GA4")
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Skip browser sign-in; list GSC/GA4 using the saved token",
    )
    args = parser.parse_args()

    settings = get_settings()  # Load .env
    token_path = oauth_token_path(settings)  # Saved refresh token path

    if args.list_only:  # Re-list without opening the browser
        if not token_path.exists():
            print(f"No saved token at {token_path}. Run without --list-only first.")
            return 1
        creds = load_google_credentials(settings)
        if creds is None:
            print("Could not load Google credentials.")
            return 1
        print(f"Using saved token: {token_path}\n")
        _print_gsc_sites(creds)
        _print_ga4_properties(creds)
        _print_next_steps()
        return 0

    client_secrets = oauth_client_secrets_path(settings)  # Desktop OAuth client JSON

    if not client_secrets.exists():  # Client secrets must exist before auth
        print(f"Missing OAuth client secrets: {client_secrets}")
        alt = PROJECT_ROOT / "google-oauth-client.json"
        if alt.exists():
            print(f"Found OAuth client at project root: {alt}")
            print(f"Move or copy it to: {PROJECT_ROOT / 'secrets' / 'google-oauth-client.json'}")
        sa = PROJECT_ROOT / "secrets" / "seogeoaudit-498619-ebfcb41ee701.json"
        if sa.exists():
            print("\nNote: seogeoaudit-498619-*.json is a SERVICE ACCOUNT key, not OAuth.")
            print("You need a separate Desktop OAuth client JSON from Google Cloud Console.")
        print("\nCreate a Desktop OAuth client in Google Cloud Console and download the JSON.")
        print(f"Save it as: {PROJECT_ROOT / 'secrets' / 'google-oauth-client.json'}")
        print("See secrets/README.md for full steps.")
        return 1

    # Reject service-account JSON mistaken for OAuth client secrets
    try:
        payload = json.loads(client_secrets.read_text(encoding="utf-8"))
        if payload.get("type") == "service_account":
            print(f"Wrong file type: {client_secrets}")
            print("This is a service-account key (type=service_account), not an OAuth desktop client.")
            print("In Google Cloud: Credentials → Create OAuth client ID → Desktop app → Download JSON.")
            return 1
        if "installed" not in payload and "web" not in payload:
            print(f"Unrecognised OAuth client format in {client_secrets}")
            print('Expected JSON with an "installed" or "web" block (Desktop OAuth client download).')
            return 1
    except Exception as exc:
        print(f"Could not read OAuth client secrets: {exc}")
        return 1

    print("Opening browser for Google sign-in…")
    print("Use the Google account that owns your Search Console property.")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), scopes=GOOGLE_SCOPES)
    creds = flow.run_local_server(port=0)  # Local redirect; opens default browser

    save_oauth_token(token_path, creds)  # Persist refresh token for the auditor
    print(f"\nSaved OAuth token to: {token_path}")

    _print_gsc_sites(creds)  # List Search Console properties you can access
    _print_ga4_properties(creds)  # List GA4 properties (helps find Property ID)
    _print_next_steps()
    return 0


def _print_next_steps() -> None:
    """Print post-auth setup reminders."""
    print("\nNext steps:")
    print("1. Set ga4_property_id in backend/connected_properties.json")
    print("   (gsc_site_url must match a GSC URL above exactly)")
    print("2. Restart the backend and re-run an audit.")
    print("\nManual GA4 Property ID: analytics.google.com → Admin → Property settings")


def _print_gsc_sites(creds) -> None:
    """Print GSC properties visible to the signed-in Google account."""
    print("\n--- Search Console properties ---")
    try:
        service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        resp = service.sites().list().execute()
        sites = resp.get("siteEntry", [])
        if not sites:
            print("  (none — confirm you signed in with the account that owns GSC)")
            return
        for site in sites:
            print(f"  {site.get('siteUrl')}  ({site.get('permissionLevel')})")
    except Exception as exc:  # API disabled or consent missing
        print(f"  Could not list GSC sites: {exc}")


def _print_ga4_properties(creds) -> None:
    """Print GA4 property IDs via the Analytics Admin API."""
    print("\n--- GA4 properties (numeric Property ID for connected_properties.json) ---")
    try:
        admin = build("analyticsadmin", "v1beta", credentials=creds, cache_discovery=False)
        summaries = admin.accountSummaries().list().execute()
        found = False
        for account in summaries.get("accountSummaries", []):
            for prop in account.get("propertySummaries", []):
                found = True
                # property path looks like "properties/123456789"
                prop_id = prop.get("property", "").replace("properties/", "")
                print(f"  {prop.get('displayName')}  →  ga4_property_id: {prop_id}")
        if not found:
            print("  (none — this Google account may have no GA4 properties)")
    except Exception as exc:  # Admin API not enabled or no access
        msg = str(exc)
        print(f"  Could not list GA4 properties.")
        if "SERVICE_DISABLED" in msg or "has not been used" in msg:
            match = re.search(r"https://console\.developers\.google\.com/apis/api/analyticsadmin[^\s\"']+", msg)
            if match:
                print(f"\n  Enable Google Analytics Admin API (required only to auto-list properties):")
                print(f"  {match.group(0)}")
                print("\n  Then run:  python scripts/google_auth.py --list-only")
            else:
                print("  Enable 'Google Analytics Admin API' in Google Cloud Console → APIs & Services.")
        else:
            print(f"  Details: {msg}")
        print("\n  Or find Property ID manually:")
        print("  analytics.google.com → Admin (gear) → Property settings → Property ID (numeric)")


if __name__ == "__main__":
    raise SystemExit(main())
