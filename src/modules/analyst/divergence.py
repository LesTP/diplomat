from __future__ import annotations

from typing import Any

from modules.types import AnalysisResult, Divergence


DEFAULT_THRESHOLDS = {
    "threat_level_steps": 1,
    "missing_leverage_item": True,
    "coalition_stability_mismatch": True,
}


def compare(a: AnalysisResult, b: AnalysisResult) -> list[Divergence]:
    if not a.success or not b.success or a.report is None or b.report is None:
        return []

    divergences: list[Divergence] = []
    _compare_threat_level(a.report, b.report, divergences)
    _compare_leverage_points(a.report, b.report, divergences)
    _compare_coalition_stability(a.report, b.report, divergences)
    return divergences


def _compare_threat_level(
    primary: dict[str, Any],
    secondary: dict[str, Any],
    divergences: list[Divergence],
) -> None:
    primary_value = primary.get("threat_level")
    secondary_value = secondary.get("threat_level")
    if not isinstance(primary_value, int) or not isinstance(secondary_value, int):
        return

    delta = abs(primary_value - secondary_value)
    threshold = DEFAULT_THRESHOLDS["threat_level_steps"]
    if delta > threshold:
        divergences.append(
            Divergence(
                field="threat_level",
                primary_value=str(primary_value),
                secondary_value=str(secondary_value),
                note=(
                    f"Threat level differs by {delta} steps, above threshold "
                    f"{threshold}."
                ),
            )
        )


def _compare_leverage_points(
    primary: dict[str, Any],
    secondary: dict[str, Any],
    divergences: list[Divergence],
) -> None:
    if not DEFAULT_THRESHOLDS["missing_leverage_item"]:
        return

    primary_points = _string_set(primary.get("key_leverage_points"))
    secondary_points = _string_set(secondary.get("key_leverage_points"))
    missing_from_secondary = sorted(primary_points - secondary_points)
    missing_from_primary = sorted(secondary_points - primary_points)
    if missing_from_secondary or missing_from_primary:
        divergences.append(
            Divergence(
                field="key_leverage_points",
                primary_value=", ".join(sorted(primary_points)),
                secondary_value=", ".join(sorted(secondary_points)),
                note="One analyst omitted leverage points present in the other report.",
            )
        )


def _compare_coalition_stability(
    primary: dict[str, Any],
    secondary: dict[str, Any],
    divergences: list[Divergence],
) -> None:
    if not DEFAULT_THRESHOLDS["coalition_stability_mismatch"]:
        return

    primary_value = primary.get("coalition_stability")
    secondary_value = secondary.get("coalition_stability")
    if primary_value != secondary_value:
        divergences.append(
            Divergence(
                field="coalition_stability",
                primary_value=str(primary_value),
                secondary_value=str(secondary_value),
                note="Analysts disagree on coalition stability.",
            )
        )


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


__all__ = ["DEFAULT_THRESHOLDS", "compare"]
