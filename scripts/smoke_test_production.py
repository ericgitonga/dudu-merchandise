"""One-command production smoke test (issue #41). Places one clearly-marked test order through
the real API (the same /cart/add and /api/checkout/submit a real client hits — no hidden/backdoor
route) and asserts the response's email_status is "sent".

Run this any time after changing a required environment variable (RESEND_API_KEY, SECRET_KEY,
FROM_EMAIL) or redeploying — `e2e/` intentionally never has real secrets configured (it asserts
`email_status == "skipped"` is the *correct* behaviour without one) and so can never catch a live
production misconfiguration. That gap is exactly what let RESEND_API_KEY/SECRET_KEY sit unset in
production for hours (issue #40) — caught only when a real customer's order email never arrived,
not by any automated check.

    conda run -n ds python scripts/smoke_test_production.py
    conda run -n ds python scripts/smoke_test_production.py --base-url https://<preview-url>

Exits non-zero with a clear message on "skipped" (no RESEND_API_KEY configured for that
environment) or "failed" (Resend rejected/errored) rather than "sent".
"""

import argparse
import re
import sys

import requests

DEFAULT_BASE_URL = "https://dudu-merchandise.vercel.app"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL,
        help=f"Site to test, no trailing slash (default: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    session = requests.Session()

    try:
        prints_resp = session.get(f"{base_url}/prints", timeout=15)
        prints_resp.raise_for_status()
        match = re.search(r'name="csrf-token" content="([^"]+)"', prints_resp.text)
        if not match:
            print(f"Could not find a CSRF token on {base_url}/prints — is the site up?", file=sys.stderr)
            return 1
        token = match.group(1)

        add_resp = session.post(
            f"{base_url}/cart/add",
            headers={"X-CSRFToken": token, "Referer": f"{base_url}/prints"},
            data={"type": "print", "photo_id": "001", "size": "A4", "qty": "1"},
            timeout=15,
        )
        add_resp.raise_for_status()
        add_body = add_resp.json()
        if not add_body.get("ok"):
            print(f"Adding a test item to cart failed: {add_body}", file=sys.stderr)
            return 1

        checkout_resp = session.post(
            f"{base_url}/api/checkout/submit",
            headers={"X-CSRFToken": token, "Referer": f"{base_url}/cart"},
            json={
                "name": "SMOKE TEST — automated, please ignore",
                "contact": "smoketest@example.com",
                "location": "N/A — automated production smoke test, not a real order",
                "mpesa_code": "SMOKETEST1",
                "notes": "Placed by scripts/smoke_test_production.py — safe to discard.",
            },
            timeout=15,
        )
        checkout_resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(f"Request to {base_url} failed: {exc}", file=sys.stderr)
        return 1

    body = checkout_resp.json()
    status = body.get("email_status")

    if status == "sent":
        print(f"OK — test order placed against {base_url}, email_status='sent'.")
        print("Check the order-recipient inbox for a \"SMOKE TEST — automated, please ignore\" subject.")
        return 0

    print(f"FAILED — email_status='{status}' (expected 'sent'). Full response: {body}", file=sys.stderr)
    if status == "skipped":
        print("'skipped' means RESEND_API_KEY isn't set for this environment — see README.md.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
