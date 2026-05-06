from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

_STATE_LOCK = Lock()
_VAPID_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _urlsafe_b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _state_path(repo_root: Path, user_id: str) -> Path:
    path = repo_root / "Runtime" / "users" / str(user_id).strip() / "web_push.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _vapid_path(repo_root: Path) -> Path:
    path = repo_root / "Runtime" / "web_push" / "vapid.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _default_state() -> dict[str, Any]:
    return {
        "enabled": True,
        "subscriptions": [],
        "recent_event_keys": [],
        "last_error": "",
        "last_test_sent_at": "",
        "updated_at": "",
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default)
    if not isinstance(raw, dict):
        return dict(default)
    merged = dict(default)
    merged.update(raw)
    return merged


def _normalize_subscription(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    endpoint = str(payload.get("endpoint", "")).strip()
    keys = payload.get("keys", {})
    if not endpoint or not isinstance(keys, dict):
        return None
    p256dh = str(keys.get("p256dh", "")).strip()
    auth = str(keys.get("auth", "")).strip()
    if not p256dh or not auth:
        return None
    result = {
        "endpoint": endpoint,
        "keys": {
            "p256dh": p256dh,
            "auth": auth,
        },
        "expirationTime": payload.get("expirationTime"),
    }
    return result


def load_state(repo_root: Path, user_id: str) -> dict[str, Any]:
    with _STATE_LOCK:
        state = _load_json(_state_path(repo_root, user_id), _default_state())
        subs = []
        for row in state.get("subscriptions", []):
            normalized = _normalize_subscription(row if isinstance(row, dict) else {})
            if normalized is None:
                continue
            if isinstance(row, dict):
                normalized["created_at"] = str(row.get("created_at", "")).strip()
                normalized["updated_at"] = str(row.get("updated_at", "")).strip()
                normalized["user_agent"] = str(row.get("user_agent", "")).strip()
                normalized["installed"] = bool(row.get("installed", False))
            subs.append(normalized)
        state["subscriptions"] = subs
        state["recent_event_keys"] = [
            str(item).strip()
            for item in state.get("recent_event_keys", [])
            if str(item).strip()
        ][-200:]
        state["enabled"] = bool(state.get("enabled", True))
        state["last_error"] = str(state.get("last_error", "")).strip()
        state["last_test_sent_at"] = str(state.get("last_test_sent_at", "")).strip()
        state["updated_at"] = str(state.get("updated_at", "")).strip()
        return state


def save_state(repo_root: Path, user_id: str, state: dict[str, Any]) -> dict[str, Any]:
    with _STATE_LOCK:
        payload = _default_state()
        payload["enabled"] = bool(state.get("enabled", True))
        payload["subscriptions"] = list(state.get("subscriptions", []))
        payload["recent_event_keys"] = list(state.get("recent_event_keys", []))[-200:]
        payload["last_error"] = str(state.get("last_error", "")).strip()
        payload["last_test_sent_at"] = str(state.get("last_test_sent_at", "")).strip()
        payload["updated_at"] = str(state.get("updated_at", "")).strip() or _now_iso()
        _atomic_write_json(_state_path(repo_root, user_id), payload)
        return payload


def _generate_vapid_payload(subject: str) -> dict[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return {
        "subject": subject,
        "private_key_pem": private_pem,
        "public_key": _urlsafe_b64(public_bytes),
        "created_at": _now_iso(),
    }


def _webpush_library_error() -> str:
    try:
        import pywebpush  # noqa: F401
    except Exception as exc:
        return f"{exc.__class__.__name__}: {exc}"
    return ""


def get_vapid_config(repo_root: Path) -> dict[str, Any]:
    subject = "mailto:oathweaver@example.invalid"
    path = _vapid_path(repo_root)
    with _VAPID_LOCK:
        try:
            payload = _load_json(path, {})
            if not str(payload.get("public_key", "")).strip() or not str(payload.get("private_key_pem", "")).strip():
                generated = _generate_vapid_payload(subject)
                _atomic_write_json(path, generated)
                payload = generated
            lib_error = _webpush_library_error()
            if lib_error:
                return {
                    "supported": False,
                    "public_key": str(payload.get("public_key", "")).strip(),
                    "private_key_pem": str(payload.get("private_key_pem", "")).strip(),
                    "subject": str(payload.get("subject", subject)).strip() or subject,
                    "error": lib_error,
                }
            return {
                "supported": True,
                "public_key": str(payload.get("public_key", "")).strip(),
                "private_key_pem": str(payload.get("private_key_pem", "")).strip(),
                "subject": str(payload.get("subject", subject)).strip() or subject,
                "error": "",
            }
        except Exception as exc:
            return {
                "supported": False,
                "public_key": "",
                "private_key_pem": "",
                "subject": subject,
                "error": f"{exc.__class__.__name__}: {exc}",
            }


def get_user_settings(repo_root: Path, user_id: str) -> dict[str, Any]:
    state = load_state(repo_root, user_id)
    vapid = get_vapid_config(repo_root)
    return {
        "server_supported": bool(vapid.get("supported", False)),
        "public_key": str(vapid.get("public_key", "")).strip(),
        "vapid_subject": str(vapid.get("subject", "")).strip(),
        "enabled": bool(state.get("enabled", True)),
        "subscription_count": len(state.get("subscriptions", [])),
        "has_subscription": bool(state.get("subscriptions", [])),
        "last_error": str(state.get("last_error", "")).strip() or str(vapid.get("error", "")).strip(),
        "last_test_sent_at": str(state.get("last_test_sent_at", "")).strip(),
    }


def has_subscriptions(repo_root: Path, user_id: str) -> bool:
    state = load_state(repo_root, user_id)
    return bool(state.get("enabled", True)) and bool(state.get("subscriptions", []))


def subscribe_user(
    repo_root: Path,
    user_id: str,
    subscription: dict[str, Any],
    *,
    user_agent: str = "",
    installed: bool = False,
) -> dict[str, Any]:
    normalized = _normalize_subscription(subscription)
    if normalized is None:
        raise ValueError("Invalid push subscription payload.")
    now = _now_iso()
    state = load_state(repo_root, user_id)
    subscriptions = []
    matched = False
    for row in state.get("subscriptions", []):
        if str(row.get("endpoint", "")).strip() != normalized["endpoint"]:
            subscriptions.append(row)
            continue
        matched = True
        merged = dict(row)
        merged.update(normalized)
        merged["updated_at"] = now
        merged["user_agent"] = str(user_agent).strip()
        merged["installed"] = bool(installed)
        subscriptions.append(merged)
    if not matched:
        normalized["created_at"] = now
        normalized["updated_at"] = now
        normalized["user_agent"] = str(user_agent).strip()
        normalized["installed"] = bool(installed)
        subscriptions.append(normalized)
    state["enabled"] = True
    state["subscriptions"] = subscriptions
    state["last_error"] = ""
    state["updated_at"] = now
    return save_state(repo_root, user_id, state)


def unsubscribe_user(repo_root: Path, user_id: str, endpoint: str = "") -> dict[str, Any]:
    needle = str(endpoint).strip()
    state = load_state(repo_root, user_id)
    if needle:
        state["subscriptions"] = [
            row for row in state.get("subscriptions", [])
            if str(row.get("endpoint", "")).strip() != needle
        ]
    else:
        state["subscriptions"] = []
    state["updated_at"] = _now_iso()
    return save_state(repo_root, user_id, state)


def _record_send_result(
    repo_root: Path,
    user_id: str,
    state: dict[str, Any],
    *,
    event_key: str,
    last_error: str,
    stale_endpoints: set[str],
    test_send: bool = False,
) -> dict[str, Any]:
    if stale_endpoints:
        state["subscriptions"] = [
            row for row in state.get("subscriptions", [])
            if str(row.get("endpoint", "")).strip() not in stale_endpoints
        ]
    if event_key:
        recent = list(state.get("recent_event_keys", []))
        recent.append(event_key)
        state["recent_event_keys"] = recent[-200:]
    state["last_error"] = str(last_error).strip()
    if test_send:
        state["last_test_sent_at"] = _now_iso()
    state["updated_at"] = _now_iso()
    return save_state(repo_root, user_id, state)


def send_notification(
    repo_root: Path,
    user_id: str,
    payload: dict[str, Any],
    *,
    event_key: str = "",
    test_send: bool = False,
) -> dict[str, Any]:
    state = load_state(repo_root, user_id)
    if not bool(state.get("enabled", True)):
        return {"ok": False, "reason": "disabled"}
    subscriptions = list(state.get("subscriptions", []))
    if not subscriptions:
        return {"ok": False, "reason": "no_subscriptions"}
    if event_key and event_key in state.get("recent_event_keys", []):
        return {"ok": True, "reason": "duplicate"}

    vapid = get_vapid_config(repo_root)
    if not bool(vapid.get("supported", False)):
        _record_send_result(
            repo_root,
            user_id,
            state,
            event_key="",
            last_error=str(vapid.get("error", "")).strip() or "Web Push support is unavailable on the server.",
            stale_endpoints=set(),
            test_send=test_send,
        )
        return {"ok": False, "reason": "unsupported", "error": vapid.get("error", "")}

    from pywebpush import WebPushException, webpush

    serialized = json.dumps(payload, ensure_ascii=True)
    claims = {"sub": str(vapid.get("subject", "")).strip() or "mailto:oathweaver@example.invalid"}
    stale_endpoints: set[str] = set()
    errors: list[str] = []
    sent = 0

    for row in subscriptions:
        sub_info = _normalize_subscription(row if isinstance(row, dict) else {})
        if sub_info is None:
            continue
        try:
            webpush(
                subscription_info=sub_info,
                data=serialized,
                vapid_private_key=str(vapid.get("private_key_pem", "")).strip(),
                vapid_claims=claims,
                ttl=60 * 60 * 12,
            )
            sent += 1
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            status = getattr(response, "status_code", None)
            if status in {404, 410}:
                stale_endpoints.add(str(sub_info.get("endpoint", "")).strip())
            else:
                errors.append(f"{status or exc.__class__.__name__}: {exc}")
        except Exception as exc:
            errors.append(f"{exc.__class__.__name__}: {exc}")

    state = _record_send_result(
        repo_root,
        user_id,
        state,
        event_key=(event_key if sent > 0 else ""),
        last_error=(errors[0] if errors else ""),
        stale_endpoints=stale_endpoints,
        test_send=test_send,
    )
    return {
        "ok": sent > 0,
        "sent": sent,
        "subscription_count": len(state.get("subscriptions", [])),
        "errors": errors,
    }
