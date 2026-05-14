from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


ValidatorFn = Callable[[str], str | None]


@dataclass(frozen=True)
class RetryResult:
    text: str
    attempts_used: int
    validation_error: str
    corrected: bool
    validated: bool


def chat_with_self_fix_retry(
    client: Any,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    num_ctx: int = 16384,
    think: bool | None = None,
    timeout: int = 360,
    retry_attempts: int = 3,
    retry_backoff_sec: float = 1.25,
    keep_alive: str | None = None,
    validator: ValidatorFn | None = None,
    max_self_fix_attempts: int = 2,
    **chat_kwargs: Any,
) -> RetryResult:
    """Run chat with optional contract-aware correction retries.

    Network/model retries remain in the underlying client call. This helper adds
    prompt-level self-correction retries only when validator() reports
    contract/parsing failures.
    """

    attempts = max(1, int(max_self_fix_attempts))
    base_system = str(system_prompt or "").strip()
    base_user = str(user_prompt or "").strip()
    correction_system = (
        f"{base_system}\n\n"
        "You must return output that strictly follows the required format. "
        "When validation errors are shown, fix the output completely and return only the corrected output."
    ).strip()

    latest_text = ""
    latest_error = ""
    validated = False
    for idx in range(attempts):
        current_user = base_user
        current_system = base_system
        if idx > 0:
            current_system = correction_system
            current_user = (
                f"{base_user}\n\n"
                "Previous output that failed validation:\n"
                f"```text\n{_trim_for_retry(latest_text, 8000)}\n```\n\n"
                "Validation error(s):\n"
                f"{_trim_for_retry(latest_error, 1500)}\n\n"
                "Return a fully corrected output now. Do not explain."
            )
        kwargs: dict[str, Any] = {
            "model": model,
            "system_prompt": current_system,
            "user_prompt": current_user,
            "temperature": temperature,
            "num_ctx": num_ctx,
            "think": think,
            "timeout": timeout,
            "retry_attempts": retry_attempts,
            "retry_backoff_sec": retry_backoff_sec,
        }
        if keep_alive is not None:
            kwargs["keep_alive"] = keep_alive
        if chat_kwargs:
            kwargs.update(dict(chat_kwargs))
        raw = client.chat(**kwargs)
        latest_text = str(raw or "").strip()
        if validator is None:
            return RetryResult(
                text=latest_text,
                attempts_used=idx + 1,
                validation_error="",
                corrected=idx > 0,
                validated=True,
            )
        try:
            latest_error = str(validator(latest_text) or "").strip()
        except Exception as exc:
            # Fail open if the validator itself is broken; caller still gets the
            # latest model output instead of a hard crash.
            return RetryResult(
                text=latest_text,
                attempts_used=idx + 1,
                validation_error=f"validator_exception:{type(exc).__name__}",
                corrected=idx > 0,
                validated=False,
            )
        if not latest_error:
            validated = True
            return RetryResult(
                text=latest_text,
                attempts_used=idx + 1,
                validation_error="",
                corrected=idx > 0,
                validated=validated,
            )

    return RetryResult(
        text=latest_text,
        attempts_used=attempts,
        validation_error=latest_error,
        corrected=attempts > 1,
        validated=validated,
    )


def _trim_for_retry(text: str, max_chars: int) -> str:
    body = str(text or "").strip()
    if len(body) <= max_chars:
        return body
    cut = body[:max_chars].rsplit("\n", 1)[0].strip()
    return cut or body[:max_chars]
