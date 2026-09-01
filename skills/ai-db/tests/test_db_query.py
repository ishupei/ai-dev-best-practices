"""Unit tests for the ai-db CLI (scripts/db_query.py).

Run with: python -m unittest discover -s skills/ai-db/tests -v
(also compatible with pytest).
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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

    def test_select_limit_validation(self):
        db_query.validate_select_limit("select * from users limit 20", 20)
        db_query.validate_select_limit("select * from users limit 20;", 20)
        db_query.validate_select_limit("select * from users limit 20 ;", 20)
        with self.assertRaises(SystemExit):
            db_query.validate_select_limit("select * from users", 20)
        with self.assertRaises(SystemExit):
            db_query.validate_select_limit("select * from users;", 20)
        with self.assertRaises(SystemExit):
            db_query.validate_select_limit("select * from users limit 21", 20)
        with self.assertRaises(SystemExit):
            db_query.validate_select_limit("select * from users limit 21;", 20)

    def test_extract_sql_limit(self):
        self.assertEqual(db_query.extract_sql_limit("select * from users limit 5"), 5)
        self.assertEqual(db_query.extract_sql_limit("select * from users limit 5 offset 3"), 5)
        self.assertEqual(db_query.extract_sql_limit("select * from users limit 5;"), 5)
        self.assertEqual(db_query.extract_sql_limit("select * from users limit 5 -- note"), 5)

    def test_extract_sql_limit_unknown_returns_none(self):
        self.assertIsNone(db_query.extract_sql_limit("select * from users limit %s"))
        self.assertIsNone(db_query.extract_sql_limit("show tables"))
        self.assertIsNone(db_query.extract_sql_limit("explain select * from users"))
        self.assertIsNone(db_query.extract_sql_limit("select * from users"))

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

    def test_other_locking_clauses_rejected(self):
        for sql in (
            "select * from users for share",
            "select * from users lock in share mode",
        ):
            self.assertFalse(db_query.is_query_only(sql), sql)

    def test_into_outfile_rejected(self):
        self.assertFalse(db_query.is_query_only("select * from users into outfile '/tmp/x'"))

    def test_executable_comments_rejected(self):
        for sql in (
            "select * from users /*!50000 into outfile '/tmp/users.csv' */",
            "select * from users /*!50000 for update */",
            "/*!50000 update users set name = 'x' */",
        ):
            self.assertFalse(db_query.is_query_only(sql), sql)

    def test_executable_comment_marker_inside_string_is_allowed(self):
        self.assertTrue(db_query.is_query_only("select '/*!50000 update users */' as note"))

    def test_keyword_inside_quotes_is_not_mutating(self):
        self.assertTrue(db_query.is_query_only("select 'delete' as word"))

    def test_comment_prefixes_ignored(self):
        self.assertFalse(db_query.is_query_only("-- note\ndelete from users"))
        self.assertFalse(db_query.is_query_only("/* note */ update users set name = 'x'"))
        self.assertTrue(db_query.is_query_only("/* note */ select 1"))


class CommandQueryGuardTest(unittest.TestCase):
    def test_rejected_statement_never_connects(self):
        with patch("db_query.get_spec", return_value=("test", {})), patch(
            "db_query.load_sql", return_value="update users set name = 'x'"
        ), patch("db_query.connect_mysql") as connect_mysql:
            with self.assertRaises(SystemExit):
                db_query.command_query(object())
        connect_mysql.assert_not_called()


class ResolveEnvCommandTest(unittest.TestCase):
    def test_preferred_environment_skips_full_summary(self):
        args = SimpleNamespace(store_dir="unused", prefer="stable", branch=None)
        stdout = io.StringIO()
        with patch("db_query.load_index_optional", return_value={"environments": {"stable": {}}}), patch(
            "db_query.env_summary_rows"
        ) as env_summary_rows, contextlib.redirect_stdout(stdout):
            db_query.command_resolve_env(args)
        env_summary_rows.assert_not_called()
        self.assertIn('"method": "prefer"', stdout.getvalue())
        self.assertNotIn('"environments"', stdout.getvalue())


class ListEnvsCommandTest(unittest.TestCase):
    def test_names_mode_skips_full_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            store_dir = Path(directory)
            db_query.write_json(
                db_query.index_path(store_dir),
                {"default_env": "stable", "environments": {"stable": {}, "uat": {}}},
            )
            args = SimpleNamespace(store_dir=str(store_dir), names=True, format="table")
            stdout = io.StringIO()
            with patch("db_query.env_summary_rows") as env_summary_rows, contextlib.redirect_stdout(stdout):
                db_query.command_list_envs(args)
        env_summary_rows.assert_not_called()
        self.assertEqual(
            json.loads(stdout.getvalue()),
            [{"env": "stable", "default": True}, {"env": "uat", "default": False}],
        )


class StoreWriteTest(unittest.TestCase):
    def test_write_json_replaces_content_without_temp_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "environments.json"
            db_query.write_json(path, {"default_env": "old", "environments": {}})
            db_query.write_json(path, {"default_env": "new", "environments": {}})
            self.assertEqual(db_query.read_json(path)["default_env"], "new")
            self.assertEqual(list(Path(directory).glob(".*.tmp")), [])


class ShowEnvCommandTest(unittest.TestCase):
    def test_show_env_redacts_unexpanded_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            store_dir = Path(directory)
            db_query.write_json(
                db_query.index_path(store_dir),
                {"default_env": "stable", "environments": {"stable": {"file": "envs/stable.json"}}},
            )
            db_query.write_json(
                store_dir / "envs" / "stable.json",
                {
                    "driver": "mysql",
                    "host": "h",
                    "database": "d",
                    "user": "u",
                    "password": "${ENV:AI_DB_TEST_PASSWORD}",
                },
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                db_query.command_show_env(SimpleNamespace(store_dir=str(store_dir), env="stable"))
        self.assertIn('"password": "***"', stdout.getvalue())


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


class MysqlSpecValidationTest(unittest.TestCase):
    def test_invalid_port_rejected(self):
        with self.assertRaises(SystemExit):
            db_query.ensure_mysql_spec({"host": "h", "database": "d", "user": "u", "port": 0})

    def test_invalid_timeout_and_options_rejected(self):
        with self.assertRaises(SystemExit):
            db_query.ensure_mysql_spec(
                {"host": "h", "database": "d", "user": "u", "connect_timeout": 0}
            )
        with self.assertRaises(SystemExit):
            db_query.ensure_mysql_spec(
                {"host": "h", "database": "d", "user": "u", "options": ["bad"]}
            )

    def test_invalid_url_port_rejected(self):
        with self.assertRaises(SystemExit):
            db_query.spec_from_mysql_url("mysql://user@127.0.0.1:99999/app")


class QueryOutputTest(unittest.TestCase):
    def test_output_budget_marks_result_as_truncated(self):
        rows = [{"id": 1}, {"id": 2}, {"id": 3}]
        result, truncated = db_query.fit_rows_to_output_budget(rows, "json", 20)
        self.assertEqual(result, [{"id": 1}, {"id": 2}])
        self.assertTrue(truncated)

    def test_query_reports_more_rows_and_output_budget(self):
        class FakeCursor:
            description = [("id",)]

            def execute(self, sql, params=None):
                self.sql = sql
                self.params = params

            def fetchmany(self, limit):
                return [(1,), (2,), (3,)][:limit]

        class FakeConnection:
            def __init__(self):
                self.cursor_instance = FakeCursor()
                self.closed = False

            def cursor(self):
                return self.cursor_instance

            def close(self):
                self.closed = True

        connection = FakeConnection()
        args = SimpleNamespace(
            limit=2,
            max_output_bytes=20,
            database=None,
            tables="users",
            log_note="sample users",
            format="json",
            params=None,
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("db_query.get_spec", return_value=("stable", {"host": "h", "database": "app", "user": "u"})), patch(
            "db_query.load_sql", return_value="select id from users limit 2"
        ), patch("db_query.connect_mysql", return_value=connection), contextlib.redirect_stdout(
            stdout
        ), contextlib.redirect_stderr(stderr):
            db_query.command_query(args)
        self.assertEqual(json.loads(stdout.getvalue()), [{"id": 1}, {"id": 2}])
        self.assertIn('"has_more": true', stderr.getvalue())
        self.assertIn('"output_truncated": false', stderr.getvalue())
        self.assertIn('"sql_limit": 2', stderr.getvalue())
        self.assertTrue(connection.closed)


class MainErrorOutputTest(unittest.TestCase):
    def test_command_failures_emit_structured_error(self):
        stderr = io.StringIO()
        argv = [
            "db_query.py",
            "query",
            "--direct-json",
            '{"host":"h","database":"d","user":"u"}',
        ]
        with patch.object(sys, "argv", argv), contextlib.redirect_stderr(stderr):
            exit_code = db_query.main()
        self.assertEqual(exit_code, 1)
        self.assertIn('"event": "ai-db-error"', stderr.getvalue())


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
