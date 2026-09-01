#!/usr/bin/env python3
"""MySQL helper for the ai-db skill.

The storage model is intentionally split:
- an environment index JSON maps names such as "18beta.1-dev" or "stable" to files;
- each environment file contains one MySQL connection JSON object.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


DEFAULT_LIMIT = 20
MAX_LIMIT = 500
DEFAULT_MAX_OUTPUT_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_CELL_CHARS = 200
STORE_LOCK_TIMEOUT_SECONDS = 10
STALE_STORE_LOCK_SECONDS = 300
MIN_MATCH_LEN = 3
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
MUTATING_PHRASES = (
    "for update",
    "for share",
    "lock in share mode",
    "into outfile",
    "into dumpfile",
)
SECRET_KEYS = {"password", "pwd", "token", "secret", "access_key", "private_key"}
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_$][A-Za-z0-9_.$-]{0,255}$")
TABLE_REF_PATTERN = re.compile(
    r"\b(?:from|join|table)\s+(`?[A-Za-z0-9_$][A-Za-z0-9_$-]*`?(?:\.`?[A-Za-z0-9_$][A-Za-z0-9_$-]*`?)?)",
    re.IGNORECASE,
)
DESCRIBE_PATTERN = re.compile(
    r"^\s*(?:describe|desc)\s+(`?[A-Za-z0-9_$][A-Za-z0-9_$-]*`?(?:\.`?[A-Za-z0-9_$][A-Za-z0-9_$-]*`?)?)",
    re.IGNORECASE,
)
SELECT_LIMIT_PATTERN = re.compile(r"\blimit\s+(\d+|%s)(?:\s+offset\s+\d+)?\s*$", re.IGNORECASE)


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


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_json(path: Path, data: dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    write_bytes(path, payload)


@contextlib.contextmanager
def store_write_lock(store_dir: Path):
    store_dir.mkdir(parents=True, exist_ok=True)
    lock_path = store_dir / ".ai-db.lock"
    deadline = time.monotonic() + STORE_LOCK_TIMEOUT_SECONDS
    descriptor = None
    while descriptor is None:
        try:
            descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > STALE_STORE_LOCK_SECONDS:
                    lock_path.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise SystemExit("Environment store is busy. Retry the write command shortly.")
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


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


def load_index_optional(store_dir: Path) -> dict[str, Any] | None:
    """Load the index without failing when it does not exist yet; returns None then."""
    path = index_path(store_dir)
    if not path.exists():
        return None
    return load_index(store_dir)


def env_summary_rows(store_dir: Path, index: dict[str, Any]) -> list[dict[str, Any]]:
    """Build secret-free per-environment summaries for list-envs."""
    rows: list[dict[str, Any]] = []
    default_env = index.get("default_env")
    for env, entry in index.get("environments", {}).items():
        if isinstance(entry, str):
            env_file = normalize_path(entry, store_dir)
        else:
            env_file = normalize_path(entry.get("file", ""), store_dir)
        summary: dict[str, Any] = {
            "env": env,
            "default": env == default_env,
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
    return rows


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


def git_current_branch() -> str | None:
    """Return the current git branch in the working directory, or None when unavailable."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    branch = proc.stdout.strip()
    if not branch or branch == "HEAD":
        return None
    return branch


def branch_match_candidates(branch: str) -> list[str]:
    """Expand a git branch name into candidate strings for env-name matching.

    Produces the full branch name, tokens split on separators, and the compact
    alphanumeric form, e.g. "release/18beta.1-dev" -> ["release/18beta.1-dev",
    "release", "18beta", "dev", "18beta1dev"].
    """
    lowered = branch.strip().lower()
    candidates = [lowered] if lowered else []
    for token in re.split(r"[^a-z0-9]+", lowered):
        if len(token) >= MIN_MATCH_LEN:
            candidates.append(token)
    compact = re.sub(r"[^a-z0-9]+", "", lowered)
    if len(compact) >= MIN_MATCH_LEN:
        candidates.append(compact)
    seen: set[str] = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]


def match_env_by_branch(branch: str, envs: list[str]) -> list[tuple[str, int]]:
    """Score configured env names against a git branch name.

    Exact candidate match scores 100; one-side containment (length >= 3) scores 80.
    Returns env names sorted by descending score, then descending name length.
    """
    candidates = branch_match_candidates(branch)
    scored: dict[str, int] = {}
    for env in envs:
        env_lower = env.lower()
        best = 0
        for cand in candidates:
            if cand == env_lower:
                best = max(best, 100)
            else:
                shorter, longer = (cand, env_lower) if len(cand) <= len(env_lower) else (env_lower, cand)
                if len(shorter) >= MIN_MATCH_LEN and shorter in longer:
                    best = max(best, 80)
        if best:
            scored[env] = best
    return sorted(scored.items(), key=lambda item: (-item[1], -len(item[0])))


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
    if parsed.password is not None:
        print(
            "warning: --url carries a password; prefer --direct-json with ${ENV:NAME} "
            "so the secret is not exposed in process lists or logs",
            file=sys.stderr,
        )
    try:
        port = parsed.port or 3306
    except ValueError as exc:
        raise SystemExit(f"Invalid MySQL URL port: {exc}") from exc
    spec: dict[str, Any] = {
        "driver": "mysql",
        "host": parsed.hostname,
        "port": port,
        "database": unquote(parsed.path.lstrip("/")) if parsed.path else None,
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
        "options": query,
    }
    return {k: v for k, v in spec.items() if v is not None}


def load_env_spec(
    store_dir: Path, env: str, resolve_values: bool = True
) -> tuple[str, Path, dict[str, Any]]:
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
    spec = read_json(path)
    return env_name, path, resolve_env_values(spec) if resolve_values else spec


def get_spec(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    sources = [bool(args.env), bool(args.direct_json), bool(args.url)]
    if sum(sources) != 1:
        raise SystemExit(
            "Specify exactly one connection source: --env, --direct-json, or --url. "
            "When no environment is known, run the 'resolve-env' command to infer one "
            "from session context or the git branch."
        )
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
    raw_port = result.get("port", 3306)
    if isinstance(raw_port, bool):
        raise SystemExit("MySQL connection port must be an integer from 1 to 65535.")
    try:
        port = int(raw_port)
    except (TypeError, ValueError) as exc:
        raise SystemExit("MySQL connection port must be an integer from 1 to 65535.") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("MySQL connection port must be an integer from 1 to 65535.")
    result["port"] = port
    result.setdefault("charset", "utf8mb4")
    for field in ("connect_timeout", "read_timeout", "write_timeout"):
        value = result.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0):
            raise SystemExit(f"MySQL connection {field} must be a positive number.")
    options = result.get("options")
    if options is None:
        result["options"] = {}
    elif not isinstance(options, dict):
        raise SystemExit("MySQL connection options must be an object.")
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


def driver_install_hint() -> str:
    """pip command for the MySQL driver that matches this Python version.

    pymysql 2.x requires Python 3.9+; the 1.x series still supports 3.7/3.8.
    """
    if sys.version_info >= (3, 9):
        return "pip install pymysql"
    return 'pip install "pymysql>=1.1,<2"'


# mysql.connector does not accept pymysql-only timeout kwargs; the fallback
# call is filtered down to the parameter set shared by both drivers.
MYSQL_CONNECTOR_KWARGS = {
    "host",
    "port",
    "database",
    "user",
    "password",
    "charset",
    "connect_timeout",
    "autocommit",
}


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
    }
    kwargs.update(spec.get("options") or {})
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    try:
        pymysql = importlib.import_module("pymysql")
        return pymysql.connect(**kwargs)
    except ImportError:
        fallback_kwargs = {k: v for k, v in kwargs.items() if k in MYSQL_CONNECTOR_KWARGS}
        dropped = sorted(set(kwargs) - set(fallback_kwargs))
        message = "pymysql is not installed; falling back to mysql.connector."
        if dropped:
            message += f" Dropped pymysql-only options: {', '.join(dropped)}."
        message += f" To use pymysql, run: {driver_install_hint()}"
        print(message, file=sys.stderr)
        mysql_connector = require_module("mysql.connector", "mysql-connector-python")
        return mysql_connector.connect(**fallback_kwargs)


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


def sql_for_guard(sql: str) -> tuple[str, bool]:
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
            if idx + 2 < length and sql[idx + 2] == "!":
                return "", True
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
    return "".join(result), False


def is_query_only(sql: str) -> bool:
    guarded, executable_comment = sql_for_guard(sql)
    if executable_comment:
        return False
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


def validate_select_limit(sql: str, maximum: int) -> None:
    guarded, executable_comment = sql_for_guard(sql)
    if executable_comment:
        return
    statement = guarded.strip().rstrip(";").strip()
    first = statement.split(None, 1)[0] if statement else ""
    if first != "select":
        return
    match = SELECT_LIMIT_PATTERN.search(statement)
    if not match:
        raise SystemExit("SELECT queries must end with an explicit LIMIT no larger than --limit.")
    requested_limit = match.group(1)
    if requested_limit.isdigit() and int(requested_limit) > maximum:
        raise SystemExit("SELECT LIMIT must not exceed --limit.")


def extract_sql_limit(sql: str) -> int | None:
    """Return the literal LIMIT value of a SELECT statement, or None when it is
    parameterized (%s) or the statement is not a plain SELECT (SHOW/EXPLAIN)."""
    guarded, executable_comment = sql_for_guard(sql)
    if executable_comment:
        return None
    statement = guarded.strip().rstrip(";").strip()
    first = statement.split(None, 1)[0] if statement else ""
    if first != "select":
        return None
    match = SELECT_LIMIT_PATTERN.search(statement)
    if not match:
        return None
    value = match.group(1)
    if not value.isdigit():
        return None
    return int(value)


def extract_table_refs(sql: str) -> list[str]:
    normalized = normalized_sql(sql)
    first = normalized.split(None, 1)[0].lower() if normalized else ""
    if first == "show":
        return ["<schema-metadata>"]
    result: list[str] = []
    describe_match = DESCRIBE_PATTERN.search(normalized)
    if describe_match:
        result.append(describe_match.group(1).replace("`", ""))
    for match in TABLE_REF_PATTERN.finditer(normalized):
        table = match.group(1).replace("`", "")
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


def query_cursor(conn: Any) -> Any:
    try:
        return conn.cursor(buffered=False)
    except TypeError:
        return conn.cursor()


def rows_to_dicts(cur: Any, rows: list[Any]) -> list[dict[str, Any]]:
    columns = [col[0] for col in cur.description]
    return [
        {
            columns[idx]: value[: MAX_CELL_CHARS - 3] + "..."
            if isinstance(value, str) and len(value) > MAX_CELL_CHARS
            else value
            for idx, value in enumerate(row)
        }
        for row in rows
    ]


def render_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no rows)"
    output = io.StringIO()
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
    output.write(" | ".join(str(col).ljust(widths[col]) for col in columns) + "\n")
    output.write("-+-".join("-" * widths[col] for col in columns) + "\n")
    for row in rendered_rows:
        output.write(" | ".join(row[col].ljust(widths[col]) for col in columns) + "\n")
    return output.getvalue().rstrip()


def render_rows(rows: list[dict[str, Any]], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(rows, ensure_ascii=False, separators=(",", ":"), default=str)
    return render_table(rows)


def fit_rows_to_output_budget(
    rows: list[dict[str, Any]], fmt: str, max_output_bytes: int
) -> tuple[list[dict[str, Any]], bool]:
    lower = 0
    upper = len(rows)
    while lower < upper:
        middle = (lower + upper + 1) // 2
        if len(render_rows(rows[:middle], fmt).encode("utf-8")) <= max_output_bytes:
            lower = middle
        else:
            upper = middle - 1
    return rows[:lower], lower < len(rows)


def print_result_log(
    env_name: str,
    database: str,
    row_count: int,
    limit: int,
    has_more: bool,
    output_truncated: bool,
    sql_limit: int | None,
) -> None:
    payload = {
        "event": "ai-db-result",
        "env": env_name,
        "database": database,
        "rows": row_count,
        "limit": limit,
        "has_more": has_more,
        "output_truncated": output_truncated,
        "sql_limit": sql_limit,
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)


def command_init_store(args: argparse.Namespace) -> None:
    store_dir = Path(args.store_dir)
    with store_write_lock(store_dir):
        index = load_index(store_dir, create=True)
        save_index(store_dir, index)
        (store_dir / "envs").mkdir(parents=True, exist_ok=True)
    print(f"Initialized ai-db store: {store_dir}")


def command_create_env(args: argparse.Namespace) -> None:
    store_dir = Path(args.store_dir)
    with store_write_lock(store_dir):
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
        previous_env = env_path.read_bytes() if env_path.exists() else None
        env_written = False
        try:
            write_json(env_path, spec)
            env_written = True
            index["environments"][args.env] = {"file": str(env_path.relative_to(store_dir)).replace("\\", "/")}
            if args.default or not index.get("default_env"):
                index["default_env"] = args.env
            save_index(store_dir, index)
        except Exception:
            if env_written:
                if previous_env is None:
                    env_path.unlink()
                else:
                    write_bytes(env_path, previous_env)
            raise
    print(json.dumps({"created": args.env, "file": str(env_path), "default": index.get("default_env")}, ensure_ascii=False))


def command_list_envs(args: argparse.Namespace) -> None:
    store_dir = Path(args.store_dir)
    index = load_index(store_dir)
    if args.names:
        rows = [
            {"env": env, "default": env == index.get("default_env")}
            for env in sorted(index["environments"])
        ]
        print(json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
        return
    print(render_rows(env_summary_rows(store_dir, index), args.format))


def command_resolve_env(args: argparse.Namespace) -> None:
    """Decide which environment to use: explicit context preference first, then git branch.

    Emits a compact JSON decision (never guesses): method=prefer|branch|branch-ambiguous|none,
    env when uniquely resolved, matched candidates, and a next-step hint.
    """
    store_dir = Path(args.store_dir)
    index = load_index_optional(store_dir)
    payload: dict[str, Any] = {
        "method": "none",
        "env": None,
        "branch": None,
        "prefer": args.prefer,
        "matches": [],
        "hint": None,
    }
    if index is None:
        payload["hint"] = (
            f"Environment store not initialized at {store_dir}. Run init-store first, "
            "then create-env with the connection info or use --direct-json."
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return
    envs = sorted(index["environments"])
    if args.prefer:
        if args.prefer in index["environments"]:
            payload.update({"method": "prefer", "env": args.prefer})
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            return
        payload["hint"] = f"Preferred environment '{args.prefer}' not found in the store."
    branch = args.branch or git_current_branch()
    payload["branch"] = branch
    if branch:
        matches = match_env_by_branch(branch, envs)
        payload["matches"] = [{"env": env, "score": score} for env, score in matches]
        exact = [(env, score) for env, score in matches if score == 100]
        if len(exact) == 1:
            payload.update({"method": "branch", "env": exact[0][0]})
        elif matches:
            payload["method"] = "branch-ambiguous"
            payload["hint"] = (
                "The git branch did not uniquely match one environment; pick from 'matches' "
                "using session context or ask the user."
            )
    if payload["env"] is None and payload["hint"] is None:
        payload["hint"] = (
            "No environment resolved. Ask the user for connection info "
            "(host/port/database/user/password or a connection JSON), then create-env or use --direct-json."
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def command_show_env(args: argparse.Namespace) -> None:
    env_name, path, spec = load_env_spec(Path(args.store_dir), args.env, resolve_values=False)
    payload = {"env": env_name, "file": str(path), "connection": redact(spec)}
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def command_set_default(args: argparse.Namespace) -> None:
    store_dir = Path(args.store_dir)
    with store_write_lock(store_dir):
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
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1.")
    if args.max_output_bytes < 1:
        raise SystemExit("--max-output-bytes must be at least 1.")
    limit = min(args.limit, MAX_LIMIT)
    max_output_bytes = min(args.max_output_bytes, MAX_OUTPUT_BYTES)
    validate_select_limit(sql, limit)
    spec = ensure_mysql_spec(apply_database_override(spec, args.database))
    tables = resolve_tables(sql, args.tables)
    print_query_log(env_name, spec["database"], tables, sql, args.log_note)
    if args.limit > MAX_LIMIT:
        print(f"warning: --limit {args.limit} exceeds MAX_LIMIT={MAX_LIMIT}; using {limit}", file=sys.stderr)
    if args.max_output_bytes > MAX_OUTPUT_BYTES:
        print(
            f"warning: --max-output-bytes {args.max_output_bytes} exceeds "
            f"MAX_OUTPUT_BYTES={MAX_OUTPUT_BYTES}; using {max_output_bytes}",
            file=sys.stderr,
        )
    conn = None
    try:
        conn = connect_mysql(spec)
        cur = query_cursor(conn)
        cursor_execute(cur, sql, load_params(args.params))
        if cur.description:
            rows = cur.fetchmany(limit + 1)
            has_more = len(rows) > limit
            result = rows_to_dicts(cur, rows)
            result = result[:limit]
            result, output_truncated = fit_rows_to_output_budget(result, args.format, max_output_bytes)
            has_more = has_more or output_truncated
            print(render_rows(result, args.format))
            print_result_log(
                env_name,
                spec["database"],
                len(result),
                limit,
                has_more,
                output_truncated,
                extract_sql_limit(sql),
            )
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
    list_envs.add_argument("--format", choices=["table", "json"], default="table")
    list_envs.add_argument("--names", action="store_true", help="Return only environment names and default markers.")
    list_envs.set_defaults(func=command_list_envs)

    resolve_env = sub.add_parser(
        "resolve-env",
        help="Decide which environment to use: explicit context preference first, then git branch inference.",
    )
    add_store_arg(resolve_env)
    resolve_env.add_argument("--prefer", help="Environment previously used or inferred in this session context.")
    resolve_env.add_argument("--branch", help="Git branch name to infer from; defaults to auto-detection in the current directory.")
    resolve_env.set_defaults(func=command_resolve_env)

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
    query.add_argument(
        "--max-output-bytes",
        type=int,
        default=DEFAULT_MAX_OUTPUT_BYTES,
        help="Maximum UTF-8 bytes emitted to stdout.",
    )
    query.add_argument("--format", choices=["table", "json"], default="table")
    query.set_defaults(func=command_query)

    return parser


def main() -> int:
    if sys.version_info < (3, 7):
        raise SystemExit(
            "Python 3.7+ is required to run the ai-db CLI. Install Python 3.7 or newer "
            "(Windows mirror: https://mirrors.huaweicloud.com/python/, tick 'Add python.exe to PATH'), "
            "then re-run this command."
        )
    parser = build_parser()
    try:
        args = parser.parse_args()
        args.func(args)
        return 0
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(
                json.dumps(
                    {
                        "event": "ai-db-error",
                        "code": "COMMAND_FAILED",
                        "message": exc.code,
                        "action": "Fix the input or follow the command in message, then retry.",
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
