#!/usr/bin/env python3
"""
Jednorázové získání GMAIL_REFRESH_TOKEN pro Fakturovatko (odesílání z hello@redbuttonedu.cz).

Před spuštěním:
  - V Google Cloud Console zapněte Gmail API.
  - Vytvořte OAuth klient typu „Desktop app“ a stáhněte JSON (doporučeno), NEBO
    použijte Web application + v Authorized redirect URIs přidejte přesně:
    http://localhost:8080/  (výchozí host a port skriptu; viz google_auth_oauthlib).

Použití (z kořene repa, venv s backend/requirements.txt):
  python3 scripts/obtain_gmail_refresh_token.py --secrets-file ~/Downloads/client_secret_....json

  Nebo bez souboru:
  export GOOGLE_CLIENT_ID=...
  export GOOGLE_CLIENT_SECRET=...
  python3 scripts/obtain_gmail_refresh_token.py

  V Docker image po buildu: python3 /app/scripts/obtain_gmail_refresh_token.py …
  (OAuth z kontejneru často vyžaduje mapování portu 8080 na hosta; jednodušší je běh lokálně.)

Scope odpovídá backendu: https://www.googleapis.com/auth/gmail.send
"""

from __future__ import annotations

import argparse
import os
import sys

# Spouštějte z repa: PYTHONPATH musí obsahovat backend pro konzistenci (volitelné).
# Skript google-auth nepotřebuje backend app.

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Install: python3 -m pip install google-auth-oauthlib google-auth", file=sys.stderr)
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _flow_from_args(args: argparse.Namespace) -> InstalledAppFlow:
    if args.secrets_file:
        path = os.path.expanduser(args.secrets_file)
        if not os.path.isfile(path):
            print(f"File not found: {path}", file=sys.stderr)
            sys.exit(1)
        return InstalledAppFlow.from_client_secrets_file(path, SCOPES)

    cid = args.client_id or os.environ.get("GOOGLE_CLIENT_ID")
    csec = args.client_secret or os.environ.get("GOOGLE_CLIENT_SECRET")
    if not cid or not csec:
        print(
            "Provide --secrets-file (Desktop OAuth JSON) or "
            "GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET in env / --client-id --client-secret",
            file=sys.stderr,
        )
        sys.exit(1)

    # „installed“ = typ Desktop v Google Cloud
    client_config = {
        "installed": {
            "client_id": cid,
            "client_secret": csec,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    return InstalledAppFlow.from_client_config(client_config, SCOPES)


def main() -> None:
    parser = argparse.ArgumentParser(description="Obtain Gmail OAuth refresh token for Fakturovatko")
    parser.add_argument(
        "--secrets-file",
        help="OAuth client JSON from Google Cloud (type: Desktop app)",
    )
    parser.add_argument("--client-id", default=os.environ.get("GOOGLE_CLIENT_ID"))
    parser.add_argument("--client-secret", default=os.environ.get("GOOGLE_CLIENT_SECRET"))
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Local redirect port (must match Authorized redirect URIs for Web client). Default 8080.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open browser automatically",
    )
    args = parser.parse_args()

    flow = _flow_from_args(args)
    # Musí přesně odpovídat Authorized redirect URIs u Web client (google_auth_oauthlib default host=localhost).
    print(
        f"Redirect URI pro Google Cloud Console (Web application): http://localhost:{args.port}/\n",
        file=sys.stderr,
    )
    creds = flow.run_local_server(
        host="localhost",
        port=args.port,
        open_browser=not args.no_browser,
        success_message="Hotovo. Můžete zavřít toto okno a vrátit se do terminálu.",
    )

    if not creds.refresh_token:
        print(
            "Refresh token nebyl vrácen. Zkuste odvolat přístup aplikace v "
            "https://myaccount.google.com/permissions a spusťte skript znovu (první souhlas).",
            file=sys.stderr,
        )
        sys.exit(1)

    print()
    print("--- Zkopírujte do Coolify / backend/.env ---")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("---")
    print()
    print("Stejný GOOGLE_CLIENT_ID a GOOGLE_CLIENT_SECRET musí být jako u tohoto OAuth klienta.")


if __name__ == "__main__":
    main()
