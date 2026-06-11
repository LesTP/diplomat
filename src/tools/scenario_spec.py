"""Dataclasses and JSON I/O for reverse scenario builder specs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_SCORE_RANGE = (1, 10)
_DEFAULT_PARETO_COUNT_TARGET = 1
_DEFAULT_BATNA_CLEARING_COUNT_TARGET = 1
_DEFAULT_BATNA_TO_PARETO_GAP_PCT = 0.10
_DEFAULT_GAME_MODE = "mixed"
_DEFAULT_PRIORITY_COLLISION = "none"
_DEFAULT_SEED = 0

_PRIORITY_COLLISION_VALUES = {"none", "soft", "hard"}
_GAME_MODE_VALUES = {"cooperative", "competitive", "mixed"}


def _validate_nonempty_str(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _validate_unique_nonempty_str_list(values: Any, *, label: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{label} must be a non-empty list of strings")
    result: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        item = _validate_nonempty_str(value, label=f"{label}[{index}]")
        if item in seen:
            raise ValueError(f"{label} must not contain duplicates: {item}")
        seen.add(item)
        result.append(item)
    return result


def _validate_score_range(value: Any) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("score_range must be a 2-item list or tuple")
    low, high = value
    if not isinstance(low, int) or not isinstance(high, int):
        raise ValueError("score_range values must be integers")
    if low <= 0 or high <= 0 or low >= high:
        raise ValueError("score_range must contain positive integers with low < high")
    return (low, high)


def _validate_int_target(value: Any, *, label: str) -> int | tuple[int, int]:
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f"{label} must be a positive integer")
        return value
    if isinstance(value, (list, tuple)) and len(value) == 2:
        low, high = value
        if not isinstance(low, int) or not isinstance(high, int):
            raise ValueError(f"{label} range values must be integers")
        if low <= 0 or high <= 0 or low > high:
            raise ValueError(f"{label} range must contain positive integers with low <= high")
        return (low, high)
    raise ValueError(f"{label} must be a positive integer or a 2-item range")


def _validate_fraction(value: Any, *, label: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    fraction = float(value)
    if not 0.0 < fraction < 1.0:
        raise ValueError(f"{label} must be in (0.0, 1.0)")
    return fraction


def _validate_probability(value: Any, *, label: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    probability = float(value)
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"{label} must be in [0.0, 1.0]")
    return probability


def _validate_weight(value: Any, *, label: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    weight = float(value)
    if weight < 0.0:
        raise ValueError(f"{label} must be non-negative")
    return weight


@dataclass
class IssueSpec:
    name: str
    outcomes: list[str]
    description: str = ""

    def __post_init__(self) -> None:
        self.name = _validate_nonempty_str(self.name, label="name")
        self.outcomes = _validate_unique_nonempty_str_list(self.outcomes, label="outcomes")
        self.description = _validate_nonempty_str(self.description, label="description") if self.description else ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IssueSpec":
        return cls(
            name=data["name"],
            outcomes=list(data["outcomes"]),
            description=data.get("description", ""),
        )


@dataclass
class ScenarioSpec:
    factions: list[str]
    issues: list[IssueSpec]
    score_range: tuple[int, int] = _DEFAULT_SCORE_RANGE
    pareto_count_target: int | tuple[int, int] = _DEFAULT_PARETO_COUNT_TARGET
    pareto_distribution_spread: float = 0.0
    pareto_outcome_diversity: float = 0.0
    batna_clearing_count_target: int = _DEFAULT_BATNA_CLEARING_COUNT_TARGET
    batna_to_pareto_gap_pct: float = _DEFAULT_BATNA_TO_PARETO_GAP_PCT
    requires_logrolling: bool = False
    priority_collision: str = _DEFAULT_PRIORITY_COLLISION
    asymmetric_batna_fractions: dict[str, float] = field(default_factory=dict)
    target_weights: dict[str, float] = field(default_factory=dict)
    game_mode: str = _DEFAULT_GAME_MODE
    seed: int = _DEFAULT_SEED

    def __post_init__(self) -> None:
        self.factions = _validate_unique_nonempty_str_list(self.factions, label="factions")
        if not isinstance(self.issues, list) or not self.issues:
            raise ValueError("issues must be a non-empty list of IssueSpec")
        normalized_issues: list[IssueSpec] = []
        seen_issue_names: set[str] = set()
        for index, issue in enumerate(self.issues):
            if isinstance(issue, dict):
                issue = IssueSpec.from_dict(issue)
            if not isinstance(issue, IssueSpec):
                raise ValueError(f"issues[{index}] must be an IssueSpec")
            if issue.name in seen_issue_names:
                raise ValueError(f"issues must not contain duplicate names: {issue.name}")
            seen_issue_names.add(issue.name)
            normalized_issues.append(issue)
        self.issues = normalized_issues
        self.score_range = _validate_score_range(self.score_range)
        self.pareto_count_target = _validate_int_target(
            self.pareto_count_target, label="pareto_count_target"
        )
        if not isinstance(self.pareto_distribution_spread, (int, float)) or self.pareto_distribution_spread < 0:
            raise ValueError("pareto_distribution_spread must be a non-negative number")
        self.pareto_outcome_diversity = _validate_probability(
            self.pareto_outcome_diversity, label="pareto_outcome_diversity"
        )
        if not isinstance(self.batna_clearing_count_target, int) or self.batna_clearing_count_target < 0:
            raise ValueError("batna_clearing_count_target must be a non-negative integer")
        self.batna_to_pareto_gap_pct = _validate_probability(
            self.batna_to_pareto_gap_pct, label="batna_to_pareto_gap_pct"
        )
        if not isinstance(self.requires_logrolling, bool):
            raise ValueError("requires_logrolling must be a boolean")
        if self.priority_collision not in _PRIORITY_COLLISION_VALUES:
            raise ValueError(
                f"priority_collision must be one of {sorted(_PRIORITY_COLLISION_VALUES)}"
            )
        if self.game_mode not in _GAME_MODE_VALUES:
            raise ValueError(f"game_mode must be one of {sorted(_GAME_MODE_VALUES)}")
        if not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")

        validated_fractions: dict[str, float] = {}
        for faction_id, value in self.asymmetric_batna_fractions.items():
            faction = _validate_nonempty_str(faction_id, label="asymmetric_batna_fractions key")
            if faction not in self.factions:
                raise ValueError(
                    f"asymmetric_batna_fractions key {faction} must name a faction in factions"
                )
            validated_fractions[faction] = _validate_fraction(
                value, label=f"asymmetric_batna_fractions[{faction}]"
            )
        self.asymmetric_batna_fractions = validated_fractions

        validated_weights: dict[str, float] = {}
        for target_name, value in self.target_weights.items():
            target = _validate_nonempty_str(target_name, label="target_weights key")
            validated_weights[target] = _validate_weight(value, label=f"target_weights[{target}]")
        self.target_weights = validated_weights

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["score_range"] = list(self.score_range)
        if isinstance(self.pareto_count_target, tuple):
            data["pareto_count_target"] = list(self.pareto_count_target)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioSpec":
        issues_raw = data.get("issues", [])
        return cls(
            factions=list(data.get("factions", [])),
            issues=[IssueSpec.from_dict(issue) if isinstance(issue, dict) else issue for issue in issues_raw],
            score_range=tuple(data.get("score_range", _DEFAULT_SCORE_RANGE)),
            pareto_count_target=data.get("pareto_count_target", _DEFAULT_PARETO_COUNT_TARGET),
            pareto_distribution_spread=data.get("pareto_distribution_spread", 0.0),
            pareto_outcome_diversity=data.get("pareto_outcome_diversity", 0.0),
            batna_clearing_count_target=data.get(
                "batna_clearing_count_target", _DEFAULT_BATNA_CLEARING_COUNT_TARGET
            ),
            batna_to_pareto_gap_pct=data.get(
                "batna_to_pareto_gap_pct", _DEFAULT_BATNA_TO_PARETO_GAP_PCT
            ),
            requires_logrolling=data.get("requires_logrolling", False),
            priority_collision=data.get("priority_collision", _DEFAULT_PRIORITY_COLLISION),
            asymmetric_batna_fractions=dict(data.get("asymmetric_batna_fractions", {})),
            target_weights=dict(data.get("target_weights", {})),
            game_mode=data.get("game_mode", _DEFAULT_GAME_MODE),
            seed=data.get("seed", _DEFAULT_SEED),
        )


def load_spec(path: str | Path) -> ScenarioSpec:
    spec_path = Path(path)
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("scenario spec JSON must be an object")
    return ScenarioSpec.from_dict(data)


def dump_spec(spec: ScenarioSpec, path: str | Path) -> Path:
    spec_path = Path(path)
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        json.dumps(spec.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return spec_path
