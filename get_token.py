#!/usr/bin/env python3
"""
One-time helper script to obtain a Google OAuth2 refresh token for the Google Ads MCP server.

Run this ONCE, sign in with Google, and copy the printed GOOGLE_REFRESH_TOKEN into your .env file.

Requirements:
    pip install google-auth-oauthlib

Usage:
    python get_token.py
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def main():
    print("=" * 55)
    print("  Google Ads — OAuth2 Token Generator")
    print("=" * 55)
    print()
    print("Paste the values from your Google Cloud OAuth 2.0 Client.")
    print("(APIs & Services → Credentials → your Desktop app client)\n")

    client_id = input("GOOGLE_CLIENT_ID     : ").strip()
    client_secret = input("GOOGLE_CLIENT_SECRET : ").strip()

    if not client_id or not client_secret:
        print("\n[ERROR] Both values are required.")
        return

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    print("\nOpening browser for Google sign-in...")
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    print("\n" + "=" * 55)
    print("  SUCCESS — add these to your .env file:")
    print("=" * 55)
    print(f"\nGOOGLE_CLIENT_ID={client_id}")
    print(f"GOOGLE_CLIENT_SECRET={client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print("\nKeep these secret. Never commit them to git.")
    print()


if __name__ == "__main__":
    main()
