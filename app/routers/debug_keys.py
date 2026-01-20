from __future__ import annotations

import hashlib
import os

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/debug", tags=["debug"])


def _expected_admin_key() -> str:
    # Keep in sync with require_admin logic (accept multiple env names)
    v = (
        os.getenv("ADMIN_KEY")
        or os.getenv("ADMIN_API_KEY")
        or os.getenv("ADMIN_TOKEN")
        or os.getenv("X_ADMIN_KEY")
        or ""
    )
    return (v or "").strip()


@router.get("/admin_key_fingerprint")
def admin_key_fingerprint(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    """
    Returns ONLY a short fingerprint of the configured ADMIN key and the provided header.
    Never returns the key itself.
    """
    expected = _expected_admin_key()
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_KEY not configured")

    expected_sha8 = hashlib.sha256(expected.encode("utf-8")).hexdigest()[:8]

    provided = (x_admin_key or "").strip()
    provided_sha8 = hashlib.sha256(provided.encode("utf-8")).hexdigest()[:8] if provided else ""
    return {
        "expected_len": len(expected),
        "expected_sha256_8": expected_sha8,
        "provided_len": len(provided),
        "provided_sha256_8": provided_sha8,
        "match": bool(provided) and (provided == expected),
    }