#!/usr/bin/env python3
"""MySQL helper for the ai-db skill.

The storage model is intentionally split:
- an environment index JSON maps names such as "18beta.1-dev" or "stable" to files;
- each environment file contains one MySQL connection JSON object.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


DEFAULT_LIMIT = 100
DEFAULT_DIR_NAME = "ai-db"
INDEX_FILE_NAME = "environments.json"
ENV_PATTERN = re.compile(r"^\$\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}$")
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
QUERY_STARTERS = ("select", "show", "explain", "describe", "desc")
MUTATING_TOKENS = {
    "alter",
    "analyze",
    "call",
    "create",
    "delete",
    "drop",
    "grant",
    "insert",
    "load",
    "lock",
    "optimize",
    "rename",
    "repair",
    "replace",
    "revoke",
    "set",
    "truncate",
    "unlock",
    "update",
}
MUTATING_PHRASES = ("for update", "into outfile", "into dumpfile")
SECRET_KEYS = {"password", "pwd", "token", "secret", "access_key", "private_key"}
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_$][A-Za-z0-9_.$-]{0,255}$")
TABLE_REF_PATTERN = re.compile(
    r"\b(?:from|join|update|into|table)\s+(`?[A-Za-z0-9_$][A-Za-z0-9_$-]*`?(?:\.`?[A-Za-z0-9_$][A-Za-z0-9_$-]*`?)?)",
    re.IGNORECASE,
)
DESCRIBE_PATTERN = re.compile(
    r"^\s*(?:describe|desc)\s+(`?[A-Za-z0-9_$][A-Za-z0-9_$-]*`?(?:\.`?[A-Za-z0-9_$][A-Za-z0-9_$-]*`?)?)",
    re.IGNORECASE,
)


def default_store_dir() -> Path:
    configured = os.environ.get("AI_DB_DIR")
    if configured:
        return Path(configured).expanduser()
    # 统一存于用户配置目录 ~/.config/ai-db（跨工具一致，不入库、不随 skill 分发）
    return Path.home() / ".config" / DEFAULT_DIR_NAME


def index_path(store_dir: Path) -> Path:
    return store_dir / INDEX_FILE_NAME


def validate_env_name(name: str) -> None:
    if not ENV_NAME_PATTERN.match(name):
        raise SystemExit(
            "Invalid env name. Use 1-128 chars: letters, digits, dot, underscore, hyphen; "
            "the first char must be a letter or digit."
        )


def validate_identifier(value: str, label: str) -> None:
    if not IDENTIFIER_PATTERN.match(value):
        raise SystemExit(f"Invalid {label}: {value}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise SystemExit(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON file: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_index(store_dir: Path, create: bool = False) -> dict[str, Any]:
    path = index_path(store_dir)
    if not path.exists():
        if create:
            return {"default_env": None, "environments": {}}
        raise SystemExit(f"Environment index not found: {path}. Run init-store first.")
    data = read_json(path)
    data.setdefault("default_env", None)
    data.setdefault("environments", {})
    if not isinstance(data["environments"], dict):
        raise SystemExit("Index field 'environments' must be an object.")
    return data


def save_index(store_dir: Path, data: dict[str, Any]) -> None:
    write_json(index_path(store_dir), data)


def resolve_env_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: resolve_env_values(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_env_values(v) for v in value]
    if isinstance(value, str):
        match = ENV_PATTERN.match(value)
        if match:
            name = match.group(1)
            if name not in os.environ:
                raise SystemExit(f"Required environment variable is not set: {name}")
            return os.environ[name]
    return value


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result[key] = "***" if key.lower() in SECRET_KEYS else redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def env_file_for(store_dir: Path, env: str) -> Path:
    validate_env_name(env)
    return store_dir / "envs" / f"{env}.json"


def normalize_path(path: str | Path, base: Path) -> Path:
    raw = Path(path).expanduser()
    if raw.is_absolute():
        return raw
    return base / raw


def mysql_template(env: str) -> dict[str, Any]:
    token = re.sub(r"[^A-Za-z0-9_]", "_", env).upper()
    return {
        "driver": "mysql",
        "host": "127.0.0.1",
        "port": 3306,
        "database": f"{env}_db",
        "user": "app_user",
        "password": f"${{ENV:AI_DB_{token}_PASSWORD}}",
        "charset": "utf8mb4",
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
        "options": {},
    }


def parse_json_object(raw: str, label: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid {label} JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{label} must be a JSON object.")
    return data


def spec_from_mysql_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"mysql", "mariadb"}:
        raise SystemExit("Only mysql:// or mariadb:// URLs are supported.")
    query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
    spec: dict[str, Any] = {
        "driver": "mysql",
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "database": unquote(parsed.path.lstrip("/")) if parsed.path else None,
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
        "options": query,
    }
    return {k: v for k, v in spec.items() if v is not None}


def load_env_spec(store_dir: Path, env: str) -> tuple[str, Path, dict[str, Any]]:
    index = load_index(store_dir)
    env_name = index.get("default_env") if env == "@default" else env
    if not env_name:
        raise SystemExit("Default environment is not configured.")
    validate_env_name(env_name)
    envs = index["environments"]
    if env_name not in envs:
        raise SystemExit(f"Environment not found: {env_name}")
    entry = envs[env_name]
    if isinstance(entry, str):
        path = normalize_path(entry, store_dir)
    elif isinstance(entry, dict) and entry.get("file"):
        path = normalize_path(entry["file"], store_dir)
    else:
        raise SystemExit(f"Invalid index entry for environment: {env_name}")
    return env_name, path, resolve_env_values(read_json(path))


def get_spec(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    sources = [bool(args.env), bool(args.direct_json), bool(args.url)]
    if sum(sources) != 1:
        raise SystemExit("Specify exactly one connection source: --env, --direct-json, or --url.")
    if args.env:
        env_name, _, spec = load_env_spec(Path(args.store_dir), args.env)
        return env_name, spec
    if args.direct_json:
        return "direct-json", resolve_env_values(parse_json_object(args.direct_json, "direct connection"))
    return "direct-url", resolve_env_values(spec_from_mysql_url(args.url))


def ensure_mysql_spec(spec: dict[str, Any]) -> dict[str, Any]:
    driver = str(spec.get("driver", "mysql")).lower()
    if driver not in {"mysql", "mariadb"}:
        raise SystemExit(f"Unsupported driver: {driver}. ai-db currently supports MySQL only.")
    required = ["host", "database", "user"]
    missing = [field for field in required if not spec.get(field)]
    if missing:
        raise SystemExit(f"MySQL connection is missing required field(s): {', '.join(missing)}")
    result = dict(spec)
    result["driver"] = "mysql"
    result.setdefault("port", 3306)
    result.setdefault("charset", "utf8mb4")
    return result


def apply_database_override(spec: dict[str, Any], database: str | None) -> dict[str, Any]:
    if not database:
        return spec
    validate_identifier(database, "database")
    allowed = spec.get("business_databases")
    if isinstance(allowed, list) and allowed and database not in allowed:
        raise SystemExit(f"Database is not configured in business_databases: {database}")
    result = dict(spec)
    result["database"] = database
    return result


def require_module(module_name: str, install_hint: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise SystemExit(f"Missing Python driver '{module_name}'. Install package: {install_hint}") from exc


def connect_mysql(spec: dict[str, Any]) -> Any:
    spec = ensure_mysql_spec(spec)
    kwargs = {
        "host": spec.get("host"),
        "port": int(spec.get("port", 3306)),
        "database": spec.get("database"),
        "user": spec.get("user"),
        "password": spec.get("password"),
        "charset": spec.get("charset", "utf8mb4"),
        "connect_timeout": spec.get("connect_timeout"),
        "read_timeout": spec.get("read_timeout"),
        "write_timeout": spec.get("write_timeout"),
        "autocommit": bool(spec.get("autocommit", False)),
        "cursorclass": None,
    }
    kwargs.update(spec.get("options") or {})
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    try:
        pymysql = importlib.import_module("pymysql")
        kwargs.pop("cursorclass", None)
        return pymysql.connect(**kwargs)
    except ImportError:
        mysql_connector = require_module("mysql.connector", "mysql-connector-python")
        kwargs.pop("cursorclass", None)
        return mysql_connector.connect(**kwargs)


def normalized_sql(sql: str) -> str:
    sql = sql.strip()
    while True:
        if sql.startswith("--"):
            _, _, rest = sql.partition("\n")
            sql = rest.lstrip()
            continue
        if sql.startswith("/*"):
            end = sql.find("*/")
            if end == -1:
                break
            sql = sql[end + 2 :].lstrip()
            continue
        break
    return sql


def sql_for_guard(sql: str) -> str:
    result: list[str] = []
    idx = 0
    length = len(sql)
    while idx < length:
        char = sql[idx]
        nxt = sql[idx + 1] if idx + 1 < length else ""
        if char == "-" and nxt == "-":
            idx = sql.find("\n", idx)
            if idx == -1:
                break
            result.append(" ")
            continue
        if char == "/" and nxt == "*":
            end = sql.find("*/", idx + 2)
            if end == -1:
                break
            result.append(" ")
            idx = end + 2
            continue
        if char in {"'", '"', "`"}:
            quote = char
            result.append(" ")
            idx += 1
            while idx < length:
                current = sql[idx]
                if current == "\\":
                    idx += 2
                    continue
                if current == quote:
                    if quote == "'" and idx + 1 < length and sql[idx + 1] == "'":
                        idx += 2
                        continue
                    idx += 1
                    break
                idx += 1
            continue
        result.append(char.lower())
        idx += 1
    return "".join(result)


def is_query_only(sql: str) -> bool:
    guarded = sql_for_guard(normalized_sql(sql))
    statements = [part.strip() for part in guarded.split(";") if part.strip()]
    if len(statements) != 1:
        return False
    statement = statements[0]
    first = statement.split(None, 1)[0] if statement else ""
    if first not in QUERY_STARTERS:
        return False
    tokens = set(re.findall(r"[a-z_]+", statement))
    if tokens.intersection(MUTATING_TOKENS):
        return False
    collapsed = re.sub(r"\s+", " ", statement)
    return not any(phrase in collapsed for phrase in MUTATING_PHRASES)


def normalize_table_ref(value: str) -> str:
    return value.replace("`", "")


def extract_table_refs(sql: str) -> list[str]:
    normalized = normalized_sql(sql)
    first = normalized.split(None, 1)[0].lower() if normalized else ""
    if first == "show":
        return ["<schema-metadata>"]
    result: list[str] = []
    describe_match = DESCRIBE_PATTERN.search(normalized)
    if describe_match:
        result.append(normalize_table_ref(describe_match.group(1)))
    for match in TABLE_REF_PATTERN.finditer(normalized):
        table = normalize_table_ref(match.group(1))
        if table not in result:
            result.append(table)
    return result


def resolve_tables(sql: str, explicit_tables: str | None) -> list[str]:
    if explicit_tables:
        tables = [item.strip() for item in explicit_tables.split(",") if item.strip()]
        if not tables:
            raise SystemExit("--tables was provided but no table name was found.")
    else:
        tables = extract_table_refs(sql)
    for table in tables:
        if table != "<schema-metadata>":
            validate_identifier(table, "table")
    if not tables:
        raise SystemExit("Unable to determine table name from SQL. Pass --tables after determining it from code/context/entity classes.")
    return tables


def sql_summary(sql: str) -> str:
    compact = re.sub(r"\s+", " ", normalized_sql(sql)).strip()
    if len(compact) > 180:
        return compact[:177] + "..."
    return compact


def print_query_log(env_name: str, database: str, tables: list[str], sql: str, note: str | None) -> None:
    payload = {
        "event": "ai-db-query-log",
        "env": env_name,
        "database": database,
        "tables": tables,
        "summary": sql_summary(sql),
    }
    if note:
        payload["note"] = note
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)


def load_sql(args: argparse.Namespace) -> str:
    if bool(args.sql) == bool(args.file):
        raise SystemExit("Specify exactly one of --sql or --file.")
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    return args.sql


def load_params(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid --params JSON: {exc}") from exc


def cursor_execute(cur: Any, sql: str, params: Any) -> None:
    if params is None:
        cur.execute(sql)
    else:
        cur.execute(sql, params)


def rows_to_dicts(cur: Any, rows: list[Any]) -> list[dict[str, Any]]:
    columns = [col[0] for col in cur.description]
    return [{columns[idx]: value for idx, value in enumerate(row)} for row in rows]


def print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("(no rows)")
        return
    columns = list(rows[0].keys())
    widths = {col: len(str(col)) for col in columns}
    rendered_rows: list[dict[str, str]] = []
    for row in rows:
        rendered: dict[str, str] = {}
        for col in columns:
            value = row.get(col)
            text = "" if value is None else str(value)
            if len(text) > 200:
                text = text[:197] + "..."
            rendered[col] = text
            widths[col] = min(max(widths[col], len(text)), 200)
        rendered_rows.append(rendered)
    print(" | ".join(str(col).ljust(widths[col]) for col in columns))
    print("-+-".join("-" * widths[col] for col in columns))
    for row in rendered_rows:
        print(" | ".join(row[col].ljust(widths[col]) for col in columns))


def print_rows(rows: list[dict[str, Any]], fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
    elif fmt == "csv":
        if not rows:
            return
        writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    else:
        print_table(rows)


def command_init_store(args: argparse.Namespace) -> None:
    store_dir = Path(args.store_dir)
    store_dir.mkdir(parents=True, exist_ok=True)
    index = load_index(store_dir, create=True)
    save_index(store_dir, index)
    (store_dir / "envs").mkdir(parents=True, exist_ok=True)
    print(f"Initialized ai-db store: {store_dir}")


def command_create_env(args: argparse.Namespace) -> None:
    store_dir = Path(args.store_dir)
    validate_env_name(args.env)
    index = load_index(store_dir, create=True)
    env_path = env_file_for(store_dir, args.env)
    if args.from_json:
        spec = parse_json_object(args.from_json, "connection")
    elif args.from_file:
        spec = read_json(Path(args.from_file))
    else:
        spec = mysql_template(args.env)
    spec = ensure_mysql_spec(spec)
    if env_path.exists() and not args.force:
        raise SystemExit(f"Environment file already exists: {env_path}. Use --force to overwrite.")
    write_json(env_path, spec)
    index["environments"][args.env] = {"file": str(env_path.relative_to(store_dir)).replace("\\", "/")}
    if args.default or not index.get("default_env"):
        index["default_env"] = args.env
    save_index(store_dir, index)
    print(json.dumps({"created": args.env, "file": str(env_path), "default": index.get("default_env")}, ensure_ascii=False))


def command_list_envs(args: argparse.Namespace) -> None:
    store_dir = Path(args.store_dir)
    index = load_index(store_dir)
    rows = []
    for env, entry in index.get("environments", {}).items():
        if isinstance(entry, str):
            env_file = normalize_path(entry, store_dir)
        else:
            env_file = normalize_path(entry.get("file", ""), store_dir)
        summary: dict[str, Any] = {
            "env": env,
            "default": env == index.get("default_env"),
            "file": str(env_file),
            "exists": env_file.exists(),
        }
        if env_file.exists():
            spec = read_json(env_file)
            summary.update(
                {
                    "driver": spec.get("driver", "mysql"),
                    "host": spec.get("host"),
                    "port": spec.get("port", 3306),
                    "database": spec.get("database"),
                    "user": spec.get("user"),
                }
            )
        rows.append(summary)
    print_rows(rows, args.format)


def command_show_env(args: argparse.Namespace) -> None:
    env_name, path, spec = load_env_spec(Path(args.store_dir), args.env)
    payload = {"env": env_name, "file": str(path), "connection": redact(spec)}
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def command_set_default(args: argparse.Namespace) -> None:
    store_dir = Path(args.store_dir)
    validate_env_name(args.env)
    index = load_index(store_dir)
    if args.env not in index["environments"]:
        raise SystemExit(f"Environment not found: {args.env}")
    index["default_env"] = args.env
    save_index(store_dir, index)
    print(json.dumps({"default_env": args.env}, ensure_ascii=False))


def command_test(args: argparse.Namespace) -> None:
    env_name, spec = get_spec(args)
    spec = ensure_mysql_spec(apply_database_override(spec, args.database))
    conn = None
    try:
        conn = connect_mysql(spec)
        cur = conn.cursor()
        cursor_execute(cur, "select 1", None)
        row = cur.fetchone()
        print(json.dumps({"env": env_name, "ok": True, "result": list(row) if row else None}, ensure_ascii=False))
    except Exception as exc:
        raise SystemExit(f"MySQL connection test failed: {exc}") from None
    finally:
        if conn is not None:
            conn.close()


def command_query(args: argparse.Namespace) -> None:
    env_name, spec = get_spec(args)
    sql = load_sql(args)
    if not is_query_only(sql):
        raise SystemExit("SQL is not recognized as query-only. ai-db query only runs SELECT/SHOW/EXPLAIN/DESCRIBE statements.")
    spec = ensure_mysql_spec(apply_database_override(spec, args.database))
    tables = resolve_tables(sql, args.tables)
    print_query_log(env_name, spec["database"], tables, sql, args.log_note)
    conn = None
    try:
        conn = connect_mysql(spec)
        cur = conn.cursor()
        cursor_execute(cur, sql, load_params(args.params))
        if cur.description:
            rows = cur.fetchmany(args.limit)
            result = rows_to_dicts(cur, rows)
            print_rows(result, args.format)
            print(f"\n-- env={env_name} driver=mysql rows={len(result)} limit={args.limit}", file=sys.stderr)
        else:
            conn.rollback()
            raise SystemExit("Query completed without a result set; ai-db does not run data-changing statements.")
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"MySQL query failed after ai-db-query-log: {exc}") from None
    finally:
        if conn is not None:
            conn.close()


def add_store_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--store-dir", default=str(default_store_dir()), help="Directory containing environments.json and env files.")


def add_source_args(parser: argparse.ArgumentParser) -> None:
    add_store_arg(parser)
    parser.add_argument("--env", help="Configured environment name, or @default.")
    parser.add_argument("--direct-json", help="MySQL connection JSON object for this command only.")
    parser.add_argument("--url", help="mysql:// connection URL for this command only.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MySQL query helper using an ai-db multi-environment store.")
    sub = parser.add_subparsers(dest="command", required=True)

    init_store = sub.add_parser("init-store", help="Create the environment store and index.")
    add_store_arg(init_store)
    init_store.set_defaults(func=command_init_store)

    create_env = sub.add_parser("create-env", help="Create or update one named MySQL environment.")
    add_store_arg(create_env)
    create_env.add_argument("--env", required=True, help="Environment name, e.g. 18beta.1-dev or stable.")
    create_env.add_argument("--from-json", help="MySQL connection JSON object.")
    create_env.add_argument("--from-file", help="Path to a MySQL connection JSON file.")
    create_env.add_argument("--default", action="store_true", help="Set this environment as default.")
    create_env.add_argument("--force", action="store_true", help="Overwrite the environment file.")
    create_env.set_defaults(func=command_create_env)

    list_envs = sub.add_parser("list-envs", help="List environments without secrets.")
    add_store_arg(list_envs)
    list_envs.add_argument("--format", choices=["table", "json", "csv"], default="table")
    list_envs.set_defaults(func=command_list_envs)

    show_env = sub.add_parser("show-env", help="Show one environment with secrets redacted.")
    add_store_arg(show_env)
    show_env.add_argument("--env", required=True, help="Environment name, or @default.")
    show_env.set_defaults(func=command_show_env)

    set_default = sub.add_parser("set-default", help="Set the default environment.")
    add_store_arg(set_default)
    set_default.add_argument("--env", required=True, help="Environment name.")
    set_default.set_defaults(func=command_set_default)

    test = sub.add_parser("test", help="Test a MySQL connection by running select 1.")
    add_source_args(test)
    test.add_argument("--database", help="Override the configured default database after it has been determined from context.")
    test.set_defaults(func=command_test)

    query = sub.add_parser("query", help="Run SQL against MySQL.")
    add_source_args(query)
    query.add_argument("--sql", help="SQL text.")
    query.add_argument("--file", help="UTF-8 SQL file path.")
    query.add_argument("--params", help="JSON array or object passed to the driver execute call.")
    query.add_argument("--database", help="Override the configured default database after it has been determined from code/context/entity classes.")
    query.add_argument("--tables", help="Comma-separated table names determined from code/context/entity classes.")
    query.add_argument("--log-note", help="Brief query purpose for the ai-db query log.")
    query.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum rows to fetch.")
    query.add_argument("--format", choices=["table", "json", "csv"], default="table")
    query.set_defaults(func=command_query)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
