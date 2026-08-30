from __future__ import annotations

import importlib.util
import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tianyin_wiki.py"
SPEC = importlib.util.spec_from_file_location("tianyin_wiki", MODULE_PATH)
assert SPEC and SPEC.loader
tianyin_wiki = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tianyin_wiki
SPEC.loader.exec_module(tianyin_wiki)


class MermaidRuntimeTest(unittest.TestCase):
    def test_mermaid_environment_preserves_explicit_browser(self) -> None:
        env = {
            "PUPPETEER_EXECUTABLE_PATH": r"D:\Tools\Chrome\chrome.exe",
            "PUPPETEER_SKIP_DOWNLOAD": "false",
        }

        resolved = tianyin_wiki.mermaid_environment(env)

        self.assertEqual(resolved["PUPPETEER_EXECUTABLE_PATH"], r"D:\Tools\Chrome\chrome.exe")
        self.assertEqual(resolved["PUPPETEER_SKIP_DOWNLOAD"], "false")

    def test_windows_chrome_path_is_auto_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir) / "runtime.json"
            chrome = (
                Path(temp_dir)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe"
            )
            chrome.parent.mkdir(parents=True)
            chrome.write_text("", encoding="utf-8")
            env = {
                "PROGRAMFILES": temp_dir,
                "TIANYIN_WIKI_RUNTIME_CACHE": str(cache),
            }

            with mock.patch.object(tianyin_wiki.sys, "platform", "win32"):
                resolved = tianyin_wiki.mermaid_environment(env)
                cached = tianyin_wiki.mermaid_environment({"TIANYIN_WIKI_RUNTIME_CACHE": str(cache)})

            self.assertEqual(Path(resolved["PUPPETEER_EXECUTABLE_PATH"]), chrome)
            self.assertEqual(Path(cached["PUPPETEER_EXECUTABLE_PATH"]), chrome)
            self.assertEqual(resolved["PUPPETEER_SKIP_DOWNLOAD"], "true")

    def test_cached_mermaid_command_skips_path_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            npx = Path(temp_dir) / "npx.cmd"
            npx.write_text("", encoding="utf-8")
            env = {"TIANYIN_WIKI_RUNTIME_CACHE": str(Path(temp_dir) / "runtime.json")}
            tianyin_wiki.save_runtime_cache(
                {"mermaidCommand": [str(npx), "--yes", "@mermaid-js/mermaid-cli"]},
                env,
            )

            with mock.patch.object(tianyin_wiki.shutil, "which", side_effect=AssertionError("PATH probe should be skipped")):
                command = tianyin_wiki.resolve_mermaid_command(env)

        self.assertEqual(command[0], str(npx))

    def test_cached_missing_mermaid_command_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {"TIANYIN_WIKI_RUNTIME_CACHE": str(Path(temp_dir) / "runtime.json")}
            tianyin_wiki.save_runtime_cache(
                {"mermaidCommand": [], "mermaidProbeComplete": True},
                env,
            )

            with mock.patch.object(tianyin_wiki.shutil, "which", side_effect=AssertionError("PATH probe should be skipped")):
                with self.assertRaisesRegex(RuntimeError, "install mmdc or npx"):
                    tianyin_wiki.resolve_mermaid_command(env)


class AuthConfigTest(unittest.TestCase):
    def test_missing_basic_credentials_requires_user_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "Wiki username/password are required"):
            tianyin_wiki.build_headers(None, None)

    def test_removed_remote_fallback_commands_are_not_registered(self) -> None:
        commands = tianyin_wiki.build_parser()._subparsers._group_actions[0].choices

        self.assertNotIn("diag" + "nose-auth", commands)
        self.assertNotIn("get" + "-login-url", commands)

    def test_complete_cli_auth_skips_config_file(self) -> None:
        args = argparse.Namespace(
            remote_url="http://wiki.example.com/pages/viewpage.action?pageId=123",
            username="alice",
            password="secret",
        )

        with mock.patch.object(tianyin_wiki, "load_config_file", side_effect=AssertionError("config should not be read")):
            config = tianyin_wiki.load_runtime_config(args)

        self.assertEqual(config.page_id, "123")
        self.assertIn("Authorization", config.headers)


class TemplateResolutionTest(unittest.TestCase):
    def test_explicit_template_skips_config_file(self) -> None:
        args = argparse.Namespace(template="1-n")

        with mock.patch.object(tianyin_wiki, "load_config_file", side_effect=AssertionError("config should not be read")):
            self.assertEqual(tianyin_wiki.resolve_template(args), "1-n")


if __name__ == "__main__":
    unittest.main()
