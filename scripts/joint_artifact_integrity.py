#!/usr/bin/env python3
"""Authenticate durable joint dry-run artifacts with a local shared key."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
CLASSIFICATION = "JOINT_DRY_RUN_ARTIFACT_SET_AUTHENTICATED"
ARTIFACT_NAMES = ("intents", "review", "proposals", "summary")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_key(path: Path) -> bytes:
    raw = path.read_bytes().strip()
    if len(raw) == 64:
        try:
            raw = bytes.fromhex(raw.decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            pass
    if len(raw) < 32:
        raise ValueError("joint artifact integrity key must contain at least 32 bytes")
    return raw


def _signature(manifest: dict[str, Any], key: bytes) -> str:
    unsigned = {
        name: value
        for name, value in manifest.items()
        if name != "manifest_hmac_sha256"
    }
    return hmac.new(key, canonical_bytes(unsigned), hashlib.sha256).hexdigest()


def build_manifest(
    target: date,
    artifacts: dict[str, Any],
    *,
    key: bytes,
) -> dict[str, Any]:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("joint artifact integrity key is invalid")
    if set(artifacts) != set(ARTIFACT_NAMES):
        raise ValueError("joint artifact set is incomplete")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "classification": CLASSIFICATION,
        "target_date": target.isoformat(),
        "artifact_set_id": secrets.token_hex(16),
        "artifact_sha256": {
            name: sha256_json(artifacts[name]) for name in ARTIFACT_NAMES
        },
    }
    manifest["manifest_hmac_sha256"] = _signature(manifest, key)
    return manifest


def verify_manifest(
    manifest: dict[str, Any],
    target: date,
    artifacts: dict[str, Any],
    *,
    key: bytes,
) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("joint artifact manifest must be an object")
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("classification") != CLASSIFICATION
        or manifest.get("target_date") != target.isoformat()
        or not isinstance(manifest.get("artifact_set_id"), str)
        or not manifest.get("artifact_set_id")
    ):
        raise ValueError("joint artifact manifest identity is invalid")
    supplied_signature = manifest.get("manifest_hmac_sha256")
    expected_signature = _signature(manifest, key)
    if not isinstance(supplied_signature, str) or not hmac.compare_digest(
        supplied_signature, expected_signature
    ):
        raise ValueError("joint artifact manifest authentication failed")
    digests = manifest.get("artifact_sha256")
    if not isinstance(digests, dict) or set(digests) != set(ARTIFACT_NAMES):
        raise ValueError("joint artifact manifest digests are incomplete")
    if set(artifacts) != set(ARTIFACT_NAMES):
        raise ValueError("joint artifact set is incomplete")
    for name in ARTIFACT_NAMES:
        supplied_digest = digests.get(name)
        expected_digest = sha256_json(artifacts[name])
        if not isinstance(supplied_digest, str) or not hmac.compare_digest(
            supplied_digest, expected_digest
        ):
            raise ValueError(f"joint {name} artifact digest mismatch")
