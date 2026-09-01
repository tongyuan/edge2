#!/usr/bin/env python3
from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def main() -> int:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_value = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_value = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    print(f"WEB_PUSH_VAPID_PUBLIC_KEY={base64url(public_value)}")
    print(f"WEB_PUSH_VAPID_PRIVATE_KEY={base64url(private_value)}")
    print("WEB_PUSH_VAPID_SUBJECT=mailto:operator@example.com")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
