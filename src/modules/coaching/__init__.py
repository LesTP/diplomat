from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml


@dataclass(frozen=True)
class CoachingEvent:
    coaching_type: str
    content: str
    route: str


@dataclass(frozen=True)
class Command:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class RouteRule:
    coaching_type: str
    route: str


class TaggedCoachingParser:
    _TAG_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)\Z", re.DOTALL)
    _COMMAND_RE = re.compile(
        r"^\s*(/[A-Za-z][A-Za-z0-9_-]*)(?::|\s)?\s*(.*)\Z",
        re.DOTALL,
    )

    def __init__(self, routes_path: str | Path) -> None:
        config = load_routes_config(routes_path)
        tags = _require_mapping(config, "tags")
        default_config = _require_mapping(tags, "default")

        self.default_route = _parse_route_rule("default", default_config)
        self.tag_routes = {
            tag.upper(): _parse_route_rule(tag, route_config)
            for tag, route_config in tags.items()
            if tag != "default"
        }
        self.commands = _parse_commands(config)

    def parse(self, raw_input: str) -> CoachingEvent | Command:
        text = raw_input.strip()
        command_match = self._COMMAND_RE.match(raw_input)
        if command_match:
            command, args_text = command_match.groups()
            command = command.lower()
            if command in self.commands:
                name = command.removeprefix("/")
                args = {"text": args_text.strip()} if name == "edit" else {}
                return Command(name=name, args=args)

        tag_match = self._TAG_RE.match(raw_input)
        if tag_match:
            tag, content = tag_match.groups()
            route_rule = self.tag_routes.get(tag.upper())
            if route_rule is not None:
                return CoachingEvent(
                    coaching_type=route_rule.coaching_type,
                    content=content.strip(),
                    route=route_rule.route,
                )

        return CoachingEvent(
            coaching_type=self.default_route.coaching_type,
            content=text,
            route=self.default_route.route,
        )


def load_routes_config(routes_path: str | Path) -> dict[str, Any]:
    try:
        text = Path(routes_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Unable to read coaching routes config: {exc}") from exc

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Coaching routes config is not valid YAML: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Coaching routes config must be a mapping")
    return parsed


def _require_mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Coaching routes config requires mapping: {key}")
    return value


def _parse_route_rule(tag: str, config: Any) -> RouteRule:
    if not isinstance(config, dict):
        raise ValueError(f"Coaching route for {tag} must be a mapping")

    coaching_type = config.get("coaching_type")
    route = config.get("route")
    if not isinstance(coaching_type, str) or not coaching_type.strip():
        raise ValueError(f"Coaching route for {tag} requires coaching_type")
    if not isinstance(route, str) or not route.strip():
        raise ValueError(f"Coaching route for {tag} requires route")

    return RouteRule(coaching_type=coaching_type.strip(), route=route.strip())


def _parse_commands(config: dict[str, Any]) -> frozenset[str]:
    commands = config.get("commands")
    if not isinstance(commands, list):
        raise ValueError("Coaching routes config requires commands list")

    parsed: set[str] = set()
    for command in commands:
        if not isinstance(command, str):
            raise ValueError("Coaching commands must be slash-prefixed strings")
        normalized = command.strip().lower()
        if not normalized.startswith("/"):
            raise ValueError("Coaching commands must be slash-prefixed strings")
        parsed.add(normalized)

    return frozenset(parsed)


__all__ = [
    "CoachingEvent",
    "Command",
    "RouteRule",
    "TaggedCoachingParser",
    "load_routes_config",
]
