"""Unit tests for the ai-db CLI (scripts/db_query.py).

Run with: python -m unittest discover -s skills/ai-db/tests -v
(also compatible with pytest).
"""

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import db_query


class IsQueryOnlyTest(unittest.TestCase):
    def test_query_starters_pass(self):
        for sql in (
            "select * from users",
            "show tables",
            "describe users",
            "desc users",
            "explain select 1",
            "select count(*) from users",
        ):
            self.assertTrue(db_query.is_query_only(sql), sql)

    def test_mutating_statements_rejected(self):
        for sql in (
            "delete from users",
            "update users set name = 'x'",
            "insert into users values (1)",
            "drop table users",
            "create table t (id int)",
            "truncate table users",
        ):
            self.assertFalse(db_query.is_query_only(sql), sql)

    def test_multi_statement_rejected(self):
        self.assertFalse(db_query.is_query_only("select 1; select 2"))

    def test_for_update_rejected(self):
        self.assertFalse(db_query.is_query_only("select * from users for update"))

    def test_into_outfile_rejected(self):
        self.assertFalse(db_query.is_query_only("select * from users into outfile '/tmp/x'"))

    def test_keyword_inside_quotes_is_not_mutating(self):
        self.assertTrue(db_query.is_query_only("select 'delete' as word"))

    def test_comment_prefixes_ignored(self):
        self.assertFalse(db_query.is_query_only("-- note\ndelete from users"))
        self.assertFalse(db_query.is_query_only("/* note */ update users set name = 'x'"))
        self.assertTrue(db_query.is_query_only("/* note */ select 1"))


class ResolveTablesTest(unittest.TestCase):
    def test_show_uses_schema_metadata_placeholder(self):
        self.assertEqual(db_query.resolve_tables("show tables", None), ["<schema-metadata>"])

    def test_describe_extracts_table(self):
        self.assertEqual(db_query.resolve_tables("describe users", None), ["users"])

    def test_select_extracts_from_join(self):
        tables = db_query.resolve_tables(
            "select u.id from users u join orders o on o.user_id = u.id", None
        )
        self.assertEqual(tables, ["users", "orders"])

    def test_explicit_tables_win(self):
        self.assertEqual(
            db_query.resolve_tables("select * from users", "users,orders"), ["users", "orders"]
        )

    def test_no_table_reference_raises(self):
        with self.assertRaises(SystemExit):
            db_query.resolve_tables("select 1", None)


class RedactTest(unittest.TestCase):
    def test_secret_keys_masked(self):
        result = db_query.redact(
            {"password": "x", "pwd": "y", "token": "z", "user": "root", "host": "h"}
        )
        self.assertEqual(
            result,
            {"password": "***", "pwd": "***", "token": "***", "user": "root", "host": "h"},
        )

    def test_nested_structures_masked(self):
        result = db_query.redact({"conn": {"Password": "s", "port": 3306}, "list": [{"pwd": "s"}]})
        self.assertEqual(result, {"conn": {"Password": "***", "port": 3306}, "list": [{"pwd": "***"}]})


class ValidateEnvNameTest(unittest.TestCase):
    def test_valid_names(self):
        for name in ("stable", "18beta.1-dev", "uat_2", "a"):
            db_query.validate_env_name(name)

    def test_invalid_names(self):
        for name in ("", "-abc", "a b", "a" * 129):
            with self.assertRaises(SystemExit, msg=name):
                db_query.validate_env_name(name)


class MatchEnvByBranchTest(unittest.TestCase):
    def test_exact_match_scores_100(self):
        matches = db_query.match_env_by_branch("stable", ["stable", "uat_2"])
        self.assertEqual(matches, [("stable", 100)])

    def test_containment_scores_80(self):
        matches = db_query.match_env_by_branch("release/18beta.1-dev", ["18beta.1-dev"])
        self.assertEqual(matches, [("18beta.1-dev", 80)])

    def test_no_match(self):
        self.assertEqual(db_query.match_env_by_branch("master", ["stable"]), [])


class SpecFromUrlTest(unittest.TestCase):
    def test_url_parsed_without_password(self):
        spec = db_query.spec_from_mysql_url("mysql://user@127.0.0.1:3306/app")
        self.assertEqual(
            spec,
            {
                "driver": "mysql",
                "host": "127.0.0.1",
                "port": 3306,
                "database": "app",
                "user": "user",
                "options": {},
            },
        )

    def test_url_with_password_warns(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            spec = db_query.spec_from_mysql_url("mysql://user:secret@127.0.0.1:3306/app")
        self.assertEqual(spec["password"], "secret")
        self.assertIn("warning: --url carries a password", stderr.getvalue())

    def test_unsupported_scheme_rejected(self):
        with self.assertRaises(SystemExit):
            db_query.spec_from_mysql_url("postgres://user@127.0.0.1/app")


class ApplyDatabaseOverrideTest(unittest.TestCase):
    def test_allowlisted_database_passes(self):
        spec = db_query.apply_database_override(
            {"database": "app", "business_databases": ["app", "logs"]}, "logs"
        )
        self.assertEqual(spec["database"], "logs")

    def test_unknown_database_rejected(self):
        spec = {"database": "app", "business_databases": ["app"]}
        with self.assertRaises(SystemExit):
            db_query.apply_database_override(spec, "other")


class ConnectFallbackTest(unittest.TestCase):
    def test_fallback_drops_pymysql_only_kwargs_and_warns(self):
        captured = {}

        class FakeConnector:
            @staticmethod
            def connect(**kwargs):
                captured["kwargs"] = kwargs
                return object()

        def fake_import(name):
            if name == "pymysql":
                raise ImportError("pymysql missing")
            if name == "mysql.connector":
                return FakeConnector
            raise ImportError(name)

        spec = {
            "driver": "mysql",
            "host": "127.0.0.1",
            "port": 3306,
            "database": "app",
            "user": "root",
            "password": "secret",
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
        }
        stderr = io.StringIO()
        with patch("db_query.importlib.import_module", side_effect=fake_import), contextlib.redirect_stderr(
            stderr
        ):
            conn = db_query.connect_mysql(spec)
        self.assertIsNotNone(conn)
        self.assertNotIn("read_timeout", captured["kwargs"])
        self.assertNotIn("write_timeout", captured["kwargs"])
        self.assertEqual(captured["kwargs"]["host"], "127.0.0.1")
        self.assertEqual(captured["kwargs"]["port"], 3306)
        self.assertIn("Dropped pymysql-only options: read_timeout, write_timeout", stderr.getvalue())

    def test_pymysql_path_keeps_all_kwargs(self):
        captured = {}

        class FakePymysql:
            @staticmethod
            def connect(**kwargs):
                captured["kwargs"] = kwargs
                return object()

        def fake_import(name):
            if name == "pymysql":
                return FakePymysql
            raise ImportError(name)

        spec = {
            "driver": "mysql",
            "host": "127.0.0.1",
            "port": 3306,
            "database": "app",
            "user": "root",
            "read_timeout": 30,
        }
        with patch("db_query.importlib.import_module", side_effect=fake_import):
            db_query.connect_mysql(spec)
        self.assertEqual(captured["kwargs"]["read_timeout"], 30)


if __name__ == "__main__":
    unittest.main()
