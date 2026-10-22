"""Unit tests for the layered configuration loader.

We exercise the three behaviors most likely to break silently: deep-merging an
override onto the base, resolving ``${env:...}`` secret placeholders, and failing
loudly on missing files/keys.
"""

from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "libraries"))

from core.configuration import Configuration  # noqa: E402
from core.exceptions import ConfigurationError  # noqa: E402


class DeepMergeTests(unittest.TestCase):
    def test_override_replaces_leaves_but_keeps_siblings(self) -> None:
        base = {"a": 1, "nested": {"x": 10, "y": 20}}
        override = {"nested": {"y": 99}, "b": 2}
        merged = Configuration._deep_merge(base, override)
        self.assertEqual(merged, {"a": 1, "b": 2, "nested": {"x": 10, "y": 99}})

    def test_merge_does_not_mutate_inputs(self) -> None:
        base = {"nested": {"x": 1}}
        override = {"nested": {"x": 2}}
        Configuration._deep_merge(base, override)
        self.assertEqual(base, {"nested": {"x": 1}})  # untouched


class PlaceholderResolutionTests(unittest.TestCase):
    def test_env_placeholder_is_resolved(self) -> None:
        os.environ["ROBOT_BITLOCKER_TEST_SECRET"] = "resolved-value"
        try:
            node = {"password": "${env:ROBOT_BITLOCKER_TEST_SECRET}"}
            resolved = Configuration._resolve_env_placeholders(node)
            self.assertEqual(resolved["password"], "resolved-value")
        finally:
            del os.environ["ROBOT_BITLOCKER_TEST_SECRET"]

    def test_missing_env_placeholder_raises(self) -> None:
        node = {"password": "${env:DEFINITELY_NOT_SET_12345}"}
        with self.assertRaises(ConfigurationError):
            Configuration._resolve_env_placeholders(node)

    def test_non_placeholder_strings_pass_through(self) -> None:
        node = {"plain": "just text", "n": 5, "list": ["a", "b"]}
        self.assertEqual(Configuration._resolve_env_placeholders(node), node)


class LoadAndAccessTests(unittest.TestCase):
    def test_loads_default_environment(self) -> None:
        config = Configuration.load("default")
        self.assertEqual(config.environment, "default")
        self.assertEqual(config.require("backend.type"), "simulated")

    def test_ci_override_is_merged_on_top_of_default(self) -> None:
        config = Configuration.load("ci")
        self.assertEqual(config.environment, "ci")
        # Value only present in the base survives the merge.
        self.assertIsNotNone(config.get("timeouts.default_seconds"))

    def test_dotted_get_returns_default_when_missing(self) -> None:
        config = Configuration.load("default")
        self.assertIsNone(config.get("does.not.exist"))
        self.assertEqual(config.get("does.not.exist", "fallback"), "fallback")

    def test_require_missing_key_raises(self) -> None:
        config = Configuration.load("default")
        with self.assertRaises(ConfigurationError):
            config.require("totally.missing.key")

    def test_unknown_environment_raises(self) -> None:
        with self.assertRaises(ConfigurationError):
            Configuration.load("no-such-environment")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
