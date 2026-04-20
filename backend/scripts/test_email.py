"""
scripts/test_email.py
---------------------
One-off smoke test for the Resend integration.
Run from the project root:  python scripts/test_email.py

What this does:
  - Loads settings from .env via core/config.py (same as the app)
  - Calls the Resend API directly — no service layer involved
  - Prints the full response object so you can confirm delivery
"""

import sys
import os

# Allow imports from the project root (core/, models/, etc.)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import resend
from core.config import settings

# ── Configuration ──────────────────────────────────────────────────────────────

# Resend's built-in test sender works without a verified domain.
# Once your domain is verified, swap this for: "FlowDesk <notifications@yourdomain.com>"
FROM_ADDRESS = "onboarding@resend.dev"

# Send to the email configured in VAPID_CLAIM_EMAIL, which is the account owner's address.
# Change this to any address you want to test delivery to.
# Resend revealed your account email in the error — using it directly.
# Update VAPID_CLAIM_EMAIL in .env to match once confirmed.
TO_ADDRESS = "spamvinup@gmail.com"

# ── Send ───────────────────────────────────────────────────────────────────────

def main():
    resend.api_key = settings.RESEND_API_KEY

    print(f"Sending test email via Resend...")
    print(f"  API key : {settings.RESEND_API_KEY[:12]}...{settings.RESEND_API_KEY[-4:]}")
    print(f"  From    : {FROM_ADDRESS}")
    print(f"  To      : {TO_ADDRESS}")
    print()

    params: resend.Emails.SendParams = {
        "from": FROM_ADDRESS,
        "to": [TO_ADDRESS],
        "subject": "FlowDesk test",
        "text": "It works",
    }

    response = resend.Emails.send(params)
    print("Response:")
    print(response)

if __name__ == "__main__":
    main()
