"""Cryptographically secure token generation and hashing utilities for email verification and password resets."""

import secrets
import hashlib


def generate_secure_token() -> str:
    """Generates a URL-safe cryptographically secure 256-bit random token string."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """Calculates a SHA-256 hex digest of the raw token for secure server-side storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_token_hash(raw_token: str, stored_hash: str) -> bool:
    """Verifies whether a raw token matches the stored SHA-256 hash using constant-time comparison."""
    calculated = hash_token(raw_token)
    return secrets.compare_digest(calculated, stored_hash)
