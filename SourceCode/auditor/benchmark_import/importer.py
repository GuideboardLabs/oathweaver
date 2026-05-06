from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


class BenchmarkImport:
    """Imports benchmark signals from cag-bench results directories."""

    def __init__(self, results_root: Path) -> None:
        self.results_root = Path(results_root)

    def latest_snapshot(self) -> dict[str, Any]:
        run_dir = self._latest_results_dir()
        if run_dir is None:
            return {
                "available": False,
                "reason": "no_results_dir",
                "created_at": _now_iso(),
            }

        runs_jsonl = run_dir / "runs.jsonl"
        if runs_jsonl.exists():
            rows = self._read_runs_jsonl(runs_jsonl)
            summary = self._summarize_rows(rows)
            summary.update(
                {
                    "available": True,
                    "source": str(runs_jsonl),
                    "run_id": run_dir.name,
                    "created_at": _now_iso(),
                }
            )
            return summary

        summary_csv = run_dir / "summary.csv"
        if summary_csv.exists():
            rows = self._read_summary_csv(summary_csv)
            summary = self._summarize_rows(rows)
            summary.update(
                {
                    "available": True,
                    "source": str(summary_csv),
                    "run_id": run_dir.name,
                    "created_at": _now_iso(),
                }
            )
            return summary

        aggregated_csv = run_dir / "aggregated_metrics.csv"
        if aggregated_csv.exists():
            modes = self._read_aggregated_modes(aggregated_csv)
            snapshot = {
                "available": True,
                "source": str(aggregated_csv),
                "run_id": run_dir.name,
                "mode_metrics": modes,
                "signals": self._signals_from_modes(modes),
                "created_at": _now_iso(),
            }
            return snapshot

        return {
            "available": False,
            "reason": "no_supported_files",
            "run_id": run_dir.name,
            "created_at": _now_iso(),
        }

    def _latest_results_dir(self) -> Path | None:
        if not self.results_root.exists() or not self.results_root.is_dir():
            return None
        candidates = [p for p in self.results_root.iterdir() if p.is_dir()]
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]

    @staticmethod
    def _read_runs_jsonl(path: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    @staticmethod
    def _read_summary_csv(path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            return [dict(row) for row in reader]

    @staticmethod
    def _read_aggregated_modes(path: Path) -> dict[str, dict[str, float]]:
        with path.open("r", encoding="utf-8") as fh:
            lines = [line.rstrip("\n") for line in fh.readlines() if line.strip()]
        if len(lines) < 3:
            return {}
        header = [x.strip() for x in lines[0].split(",")]
        subheader = [x.strip() for x in lines[1].split(",")]
        out: dict[str, dict[str, float]] = {}
        for raw in lines[2:]:
            cols = [x.strip() for x in raw.split(",")]
            if not cols:
                continue
            mode = cols[0]
            if not mode:
                continue
            metrics: dict[str, float] = {}
            for idx in range(1, min(len(cols), len(header), len(subheader))):
                metric = header[idx]
                stat = subheader[idx]
                if not metric or stat != "mean":
                    continue
                value = _to_float(cols[idx], default=float("nan"))
                if value == value:
                    metrics[metric] = value
            out[mode] = metrics
        return out

    def _summarize_rows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        mode_totals: dict[str, dict[str, float]] = {}
        mode_counts: dict[str, int] = {}
        for row in rows:
            mode = str(row.get("mode", "")).strip()
            if not mode:
                continue
            bucket = mode_totals.setdefault(mode, {
                "score": 0.0,
                "continuity_recall": 0.0,
                "memory_usage_rate": 0.0,
                "memory_recall": 0.0,
                "memory_precision": 0.0,
            })
            bucket["score"] += _to_float(row.get("score", 0.0))
            bucket["continuity_recall"] += _to_float(row.get("continuity_recall", 0.0))
            bucket["memory_usage_rate"] += _to_float(row.get("memory_usage_rate", 0.0))
            bucket["memory_recall"] += _to_float(row.get("memory_recall", 0.0))
            bucket["memory_precision"] += _to_float(row.get("memory_precision", 0.0))
            mode_counts[mode] = mode_counts.get(mode, 0) + 1

        mode_metrics: dict[str, dict[str, float]] = {}
        for mode, totals in mode_totals.items():
            count = max(1, mode_counts.get(mode, 1))
            mode_metrics[mode] = {k: float(v / count) for k, v in totals.items()}

        return {
            "mode_metrics": mode_metrics,
            "signals": self._signals_from_modes(mode_metrics),
            "row_count": len(rows),
        }

    @staticmethod
    def _signals_from_modes(mode_metrics: dict[str, dict[str, float]]) -> dict[str, Any]:
        target = mode_metrics.get("cag", {}) if isinstance(mode_metrics.get("cag", {}), dict) else {}
        if not target:
            # fall back to first mode if cag isn't present
            for row in mode_metrics.values():
                if isinstance(row, dict):
                    target = row
                    break

        continuity = _to_float(target.get("continuity_recall", 0.0))
        memory_usage = _to_float(target.get("memory_usage_rate", 0.0))
        score = _to_float(target.get("score", 0.0))
        return {
            "continuity_recall": continuity,
            "memory_usage_rate": memory_usage,
            "score": score,
            "high_memory_low_continuity": bool(memory_usage >= 70.0 and continuity <= 45.0),
            "high_memory_low_score": bool(memory_usage >= 70.0 and score <= 45.0),
        }
