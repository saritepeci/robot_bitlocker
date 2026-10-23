"""Centralized, layered configuration loader.

Responsibilities (and nothing else — Single Responsibility Principle):
  1. Locate and parse the YAML environment files under ``config/environments``.
  2. Deep-merge an environment override on top of ``default.yaml``.
  3. Resolve ``${env:NAME}`` placeholders from real OS environment variables so
     that secrets never live in the repository.
  4. Expose the result through a small, read-only, dotted-key accessor.

WHY YAML + layered merge (design rationale)?
  * Advantages: human-readable, diff-friendly, supports comments, trivial for a
    non-programmer tester to tweak; the base/override split keeps things DRY.
  * Disadvantages: no type checking by itself (we mitigate with typed getters);
    YAML has sharp edges (e.g. ``no`` parsing as boolean) — we keep files simple.
  * Alternatives considered: .env files (too flat for nested timeouts/creds),
    Python config modules (powerful but let logic creep into config), a settings
    service (overkill here). YAML hits the sweet spot for a test framework.
"""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from core.exceptions import ConfigurationError

# Repository root = three levels up from this file:
#   libraries/core/configuration.py -> libraries/core -> libraries -> <root>
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENVIRONMENTS_DIR = _REPO_ROOT / "config" / "environments"

# The base layer every environment is merged on top of.
_BASE_ENVIRONMENT = "default"

# Matches a whole-string secret placeholder such as "${env:WINDOWS_PASSWORD}".
# We intentionally only support *whole value* substitution to keep the mental
# model simple and avoid accidental partial interpolation of real data.
_ENV_PLACEHOLDER = re.compile(r"^\$\{env:(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}$")


class Configuration:
    """Immutable view over the merged configuration for one environment.

    Instances are created via :meth:`load`. The object is treated as read-only:
    tests and libraries *consume* configuration, they never mutate it. This keeps
    behavior reproducible — two test cases can never influence each other through
    shared, mutable settings.
    """

    def __init__(self, data: Mapping[str, Any], environment: str) -> None:
        # Store a deep copy so external references cannot mutate our state.
        self._data: dict[str, Any] = copy.deepcopy(dict(data))
        self._environment = environment

    # -- Construction ---------------------------------------------------------

    @classmethod
    def load(cls, environment: str | None = None) -> "Configuration":
        """Build the configuration for ``environment`` (default: ``"default"``).

        The lookup order for the environment name is:
          1. The explicit argument.
          2. The ``ROBOT_ENVIRONMENT`` OS environment variable.
          3. The ``_BASE_ENVIRONMENT`` fallback.
        This lets the same code be driven from Robot (``--variable ENVIRONMENT``),
        from a shell (export), or from a Python unit test (argument).
        """
        environment = environment or os.environ.get("ROBOT_ENVIRONMENT") or _BASE_ENVIRONMENT

        base = cls._read_yaml(_ENVIRONMENTS_DIR / f"{_BASE_ENVIRONMENT}.yaml")

        if environment == _BASE_ENVIRONMENT:
            merged = base
        else:
            override = cls._read_yaml(_ENVIRONMENTS_DIR / f"{environment}.yaml")
            merged = cls._deep_merge(base, override)

        merged = cls._resolve_env_placeholders(merged)
        return cls(merged, environment)

    # -- Public accessors -----------------------------------------------------

    @property
    def environment(self) -> str:
        """The resolved environment name (e.g. ``"ci"``)."""
        return self._environment

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Return a value by dotted path, e.g. ``get("timeouts.default_seconds")``.

        Using dotted keys (instead of exposing the nested dict) gives callers a
        stable, flat contract and a single place to add validation later.
        Returns ``default`` when any segment of the path is missing.
        """
        node: Any = self._data
        for segment in dotted_key.split("."):
            if not isinstance(node, Mapping) or segment not in node:
                return default
            node = node[segment]
        return copy.deepcopy(node)

    def require(self, dotted_key: str) -> Any:
        """Like :meth:`get`, but raise if the key is absent.

        Use this for values the framework cannot sensibly default (e.g. the
        backend type). Failing fast with a precise message beats a mysterious
        ``None`` surfacing three layers away.
        """
        sentinel = object()
        value = self.get(dotted_key, sentinel)
        if value is sentinel:
            raise ConfigurationError(
                f"Required configuration key '{dotted_key}' is missing for "
                f"environment '{self._environment}'."
            )
        return value

    def as_dict(self) -> dict[str, Any]:
        """Return a deep copy of the whole configuration tree.

        Consumed by the Robot *variable file* to publish values as ``${VARIABLES}``.
        A copy (not the live dict) preserves immutability.
        """
        return copy.deepcopy(self._data)

    # -- Internal helpers -----------------------------------------------------

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        """Parse a YAML file into a dict, with friendly, specific errors."""
        if not path.is_file():
            available = ", ".join(sorted(p.stem for p in _ENVIRONMENTS_DIR.glob("*.yaml")))
            raise ConfigurationError(
                f"Configuration file not found: {path}. "
                f"Available environments: {available or '(none)'}."
            )
        try:
            with path.open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - defensive
            raise ConfigurationError(f"Failed to parse YAML file {path}: {exc}") from exc

        if not isinstance(loaded, dict):
            raise ConfigurationError(
                f"Configuration file {path} must contain a mapping at the top level."
            )
        return loaded

    @staticmethod
    def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
        """Recursively merge ``override`` onto ``base`` (override wins on leaves).

        Nested mappings are merged key-by-key; any non-mapping value (scalar or
        list) is replaced wholesale. This is deliberately simple and predictable —
        "smart" list merging is a classic source of configuration surprises.
        """
        result: dict[str, Any] = copy.deepcopy(dict(base))
        for key, override_value in override.items():
            base_value = result.get(key)
            if isinstance(base_value, Mapping) and isinstance(override_value, Mapping):
                result[key] = Configuration._deep_merge(base_value, override_value)
            else:
                result[key] = copy.deepcopy(override_value)
        return result

    @classmethod
    def _resolve_env_placeholders(cls, node: Any) -> Any:
        """Replace ``${env:NAME}`` string values with the OS environment variable.

        This is the mechanism that keeps real secrets OUT of the repository: the
        committed YAML holds only a placeholder; the real value is injected by the
        CI secret store or the developer's shell at run time.
        """
        if isinstance(node, Mapping):
            return {key: cls._resolve_env_placeholders(value) for key, value in node.items()}
        if isinstance(node, list):
            return [cls._resolve_env_placeholders(item) for item in node]
        if isinstance(node, str):
            match = _ENV_PLACEHOLDER.match(node.strip())
            if match:
                name = match.group("name")
                if name not in os.environ:
                    raise ConfigurationError(
                        f"Configuration references environment variable '{name}' "
                        f"via '${{env:{name}}}' but it is not set."
                    )
                return os.environ[name]
        return node
