from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import OutputContract, contract_for_stage


@dataclass
class ContractAuditResult:
    stage: str
    ok: bool
    missing_fields: list[str] = field(default_factory=list)
    forbidden_fields: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "ok": self.ok,
            "missing_fields": list(self.missing_fields),
            "forbidden_fields": list(self.forbidden_fields),
        }


class OutputContractAuditor:
    def validate(self, stage: str, output: dict[str, Any], contract: OutputContract | None = None) -> ContractAuditResult:
        row = dict(output or {})
        spec = contract or contract_for_stage(stage)
        missing = [field for field in spec.must_include if not self._required_present(row, field)]
        forbidden = [field for field in spec.must_not_include if self._present_nonempty(row.get(field))]
        return ContractAuditResult(
            stage=spec.stage,
            ok=not missing and not forbidden,
            missing_fields=missing,
            forbidden_fields=forbidden,
        )

    @staticmethod
    def _required_present(row: dict[str, Any], key: str) -> bool:
        if key not in row:
            return False
        value = row.get(key)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    @staticmethod
    def _present_nonempty(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, dict, tuple, set)):
            return bool(value)
        return True
