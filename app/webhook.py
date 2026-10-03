"""
webhook.py — verifying that a webhook request really came from GitHub.

WHY THIS MATTERS
------------------
Your /webhook endpoint is a public URL. Without verification, *anyone* who
finds that URL could POST a fake payload and inject fake push records into
your dashboard. GitHub signs every webhook request with a secret only you
and GitHub know, so you can confirm the request is genuine before trusting
its contents.

HOW IT WORKS
-------------
1. When you set up the webhook on GitHub, you choose a secret string.
2. For every request, GitHub computes HMAC-SHA256 of the raw request body
   using that secret, and sends it in the `X-Hub-Signature-256` header as
   `sha256=<hex digest>`.
3. You compute the same HMAC yourself, using the same secret, over the
   same raw bytes — and compare. If they match, the request is
   authentic AND untampered with (changing even one byte of the body
   would produce a completely different signature).
"""

import hashlib
import hmac


def verify_signature(secret: str, payload_body: bytes, signature_header: str) -> bool:
    """
    Return True if `signature_header` is a valid HMAC-SHA256 signature of
    `payload_body`, computed with `secret`.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    provided_signature = signature_header.removeprefix("sha256=")

    # hmac.compare_digest instead of `==` deliberately: a plain string
    # comparison can leak timing information (it returns as soon as the
    # first mismatched character is found), which an attacker could use
    # to guess the correct signature one byte at a time. compare_digest
    # always takes the same amount of time regardless of where strings
    # first differ.
    return hmac.compare_digest(expected_signature, provided_signature)
