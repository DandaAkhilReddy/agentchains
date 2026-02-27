"""L4 Performance — latency and response-size checks from metadata."""
from __future__ import annotations

from marketplace.services.judge.base import JudgeContext, JudgeLevel, LevelVerdict

# Latency thresholds in milliseconds.
_LATENCY_PASS_MS = 5_000
_LATENCY_WARN_MS = 10_000

# Response size threshold in bytes (1 MiB).
_SIZE_WARN_BYTES = 1_048_576


class L4Performance(JudgeLevel):
    """Level 4: Performance.

    Checks ``metadata["latency_ms"]`` and ``metadata["response_size_bytes"]``
    against predefined thresholds.  Score is inversely proportional to latency.
    """

    @property
    def level(self) -> int:
        return 4

    @property
    def name(self) -> str:
        return "performance"

    async def evaluate(self, ctx: JudgeContext) -> LevelVerdict:
        """Evaluate performance metrics from pipeline metadata.

        Args:
            ctx: Pipeline context; reads ``metadata["latency_ms"]`` and
                ``metadata["response_size_bytes"]``.

        Returns:
            LevelVerdict — skipped when no performance metrics are present.
        """
        latency_ms: int | float | None = ctx.metadata.get("latency_ms")
        response_size: int | None = ctx.metadata.get("response_size_bytes")

        if latency_ms is None and response_size is None:
            return LevelVerdict(
                verdict="skip",
                score=1.0,
                confidence=1.0,
                details={"reason": "no performance metrics in metadata"},
            )

        details: dict = {}
        failures: list[str] = []
        warnings: list[str] = []

        # --- Latency check ---
        latency_score = 1.0
        if latency_ms is not None:
            details["latency_ms"] = latency_ms
            if latency_ms < _LATENCY_PASS_MS:
                # Linearly scale 1.0 (0 ms) to 0.5 (5000 ms).
                latency_score = max(0.5, 1.0 - (latency_ms / (_LATENCY_PASS_MS * 2)))
            elif latency_ms < _LATENCY_WARN_MS:
                warnings.append(f"latency {latency_ms}ms exceeds pass threshold ({_LATENCY_PASS_MS}ms)")
                latency_score = 0.3
            else:
                failures.append(f"latency {latency_ms}ms exceeds warn threshold ({_LATENCY_WARN_MS}ms)")
                latency_score = 0.0

        # --- Response size check ---
        size_score = 1.0
        if response_size is not None:
            details["response_size_bytes"] = response_size
            if response_size > _SIZE_WARN_BYTES:
                warnings.append(
                    f"response size {response_size} bytes exceeds 1 MiB threshold"
                )
                size_score = 0.6

        # Combined score weighted 70% latency, 30% size.
        metrics_count = (1 if latency_ms is not None else 0) + (1 if response_size is not None else 0)
        if metrics_count == 2:
            score = latency_score * 0.7 + size_score * 0.3
        elif latency_ms is not None:
            score = latency_score
        else:
            score = size_score

        if failures:
            verdict = "fail"
        elif warnings:
            verdict = "warn"
        else:
            verdict = "pass"

        details["warnings"] = warnings
        details["failures"] = failures

        return LevelVerdict(
            verdict=verdict,
            score=round(score, 4),
            confidence=0.90,
            details=details,
        )
