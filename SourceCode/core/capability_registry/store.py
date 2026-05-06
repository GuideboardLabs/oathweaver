from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_DEFAULT_CLAIM = {
    "claim": "8B + CAG + pipeline can approach 70B quality on long-running architecture work",
    "status": "hypothesis",
    "benchmarks": ["cag_long_project_v3"],
    "hardware_profile": "8GB VRAM / 16GB RAM",
    "confidence": "medium",
    "known_limits": [
        "not equivalent for broad factual recall",
        "depends on high-quality CAG memory",
        "slower than one-shot 70B",
    ],
}


class CapabilityRegistry:
    """Registry of benchmark-backed system capability claims."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.root = self.repo_root / "Runtime" / "capability_registry"
        self.root.mkdir(parents=True, exist_ok=True)
        self.claims_path = self.root / "claims.json"
        self.events_path = self.root / "events.jsonl"
        if not self.events_path.exists():
            self.events_path.write_text("", encoding="utf-8")
        self._ensure_defaults()

    def list_claims(self) -> list[dict[str, Any]]:
        payload = self._load_claims()
        return [dict(x) for x in payload if isinstance(x, dict)]

    def upsert_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        incoming = dict(claim or {})
        claim_key = str(incoming.get("claim", "")).strip()
        if not claim_key:
            raise ValueError("Capability claim must include 'claim'.")

        claims = self._load_claims()
        found = False
        for idx, row in enumerate(claims):
            if str(row.get("claim", "")).strip() == claim_key:
                merged = dict(row)
                merged.update(incoming)
                merged["updated_at"] = _now_iso()
                claims[idx] = merged
                incoming = merged
                found = True
                break
        if not found:
            incoming["created_at"] = _now_iso()
            incoming["updated_at"] = incoming["created_at"]
            claims.append(incoming)

        self.claims_path.write_text(json.dumps(claims, indent=2, ensure_ascii=True), encoding="utf-8")
        self._append_event({"event": "claim_upserted", "claim": dict(incoming), "created_at": _now_iso()})
        return dict(incoming)

    def record_run_observation(
        self,
        *,
        claim_text: str,
        run_id: str,
        pipeline: str,
        final_score: float,
        benchmark_id: str = "",
        status: str = "hypothesis",
    ) -> dict[str, Any]:
        claim = self._find_claim(claim_text)
        if not claim:
            claim = self.upsert_claim({"claim": claim_text, "status": status, "benchmarks": []})
        benchmarks = [str(x) for x in claim.get("benchmarks", []) if str(x).strip()]
        if benchmark_id and benchmark_id not in benchmarks:
            benchmarks.append(benchmark_id)

        observations = claim.get("observations", []) if isinstance(claim.get("observations", []), list) else []
        observations.append(
            {
                "run_id": str(run_id),
                "pipeline": str(pipeline),
                "final_score": float(final_score),
                "timestamp": _now_iso(),
            }
        )
        while len(observations) > 100:
            observations.pop(0)

        updated = self.upsert_claim(
            {
                "claim": claim_text,
                "status": status,
                "benchmarks": benchmarks,
                "observations": observations,
            }
        )
        return updated

    def _ensure_defaults(self) -> None:
        claims = self._load_claims()
        if not claims:
            base = dict(_DEFAULT_CLAIM)
            base["created_at"] = _now_iso()
            base["updated_at"] = base["created_at"]
            self.claims_path.write_text(json.dumps([base], indent=2, ensure_ascii=True), encoding="utf-8")
            self._append_event({"event": "default_claim_seeded", "claim": base, "created_at": _now_iso()})
            return
        if not any(str(row.get("claim", "")).strip() == _DEFAULT_CLAIM["claim"] for row in claims):
            self.upsert_claim(dict(_DEFAULT_CLAIM))

    def _load_claims(self) -> list[dict[str, Any]]:
        if not self.claims_path.exists():
            return []
        try:
            payload = json.loads(self.claims_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(payload, list):
            return []
        return [dict(x) for x in payload if isinstance(x, dict)]

    def _find_claim(self, claim_text: str) -> dict[str, Any]:
        key = str(claim_text or "").strip()
        if not key:
            return {}
        for row in self._load_claims():
            if str(row.get("claim", "")).strip() == key:
                return dict(row)
        return {}

    def _append_event(self, payload: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True))
            fh.write("\n")
