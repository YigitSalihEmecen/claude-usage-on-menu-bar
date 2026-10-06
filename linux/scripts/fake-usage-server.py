#!/usr/bin/env python3
"""Serves a fake usage payload so the app can be developed without a Claude account.

    scripts/fake-usage-server.py [--port 8765] [--session 42] [--weekly 38]

Then run the app against it, from a throwaway config so your real settings and
login stay untouched:

    CLAUDE_USAGE_API_URL=http://127.0.0.1:8765/api/oauth/usage \\
    XDG_CONFIG_HOME=/tmp/cu/config CLAUDE_CONFIG_DIR=/tmp/cu/claude \\
    python3 -m claude_usage
"""

import argparse
import json
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


def payload(args: argparse.Namespace) -> dict:
    now = datetime.now(timezone.utc)

    def at(**delta) -> str:
        return (now + timedelta(**delta)).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "limits": [
            {
                "kind": "session",
                "group": "session",
                "percent": args.session,
                "resets_at": at(hours=2, minutes=14),
            },
            {
                "kind": "weekly_all",
                "group": "weekly",
                "percent": args.weekly,
                "resets_at": at(days=2, hours=4),
            },
            {
                "kind": "weekly_scoped",
                "group": "weekly",
                "percent": 12,
                "resets_at": at(days=2, hours=4),
                "scope": {"model": {"display_name": "Opus"}},
            },
        ],
        "extra_usage": {"is_enabled": True, "monthly_limit": 50, "used_credits": 4.25, "utilization": 8.5},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--session", type=float, default=42)
    parser.add_argument("--weekly", type=float, default=38)
    args = parser.parse_args()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = json.dumps(payload(args)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            print(f"served usage to {self.headers.get('Authorization', 'no token')[:20]}...")

        def log_message(self, *_args) -> None:
            pass

    print(f"fake usage endpoint on http://127.0.0.1:{args.port}/api/oauth/usage")
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
