# AI DB MySQL Environment Store

Read this file only when environment storage details are needed.

> Windows: every `python <db-query>` example below maps to
> `powershell <ai-db-skill>/scripts/python_probe.ps1`, which probes and selects a
> Python 3.7+ interpreter automatically.

## Store Location

Default:

```text
%USERPROFILE%\.config\ai-db\
```

Override order:

1. `--store-dir <dir>`
2. `AI_DB_DIR`
3. `%USERPROFILE%\.config\ai-db\`

## Directory Layout

```text
ai-db/
├── environments.json
└── envs/
    ├── 18beta.1-dev.json
    └── stable.json
```

`environments.json` is only an index. Each environment has a separate JSON connection file.

## environments.json

```json
{
  "default_env": "stable",
  "environments": {
    "18beta.1-dev": {
      "file": "envs/18beta.1-dev.json"
    },
    "stable": {
      "file": "envs/stable.json"
    }
  }
}
```

Environment names must match `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`: letters, digits,
dots, underscores, and hyphens, starting with a letter or digit, at most 128 characters.
Examples: `18beta.1-dev`, `stable`, `uat_2`.

## Single Environment Connection JSON

```json
{
  "driver": "mysql",
  "host": "127.0.0.1",
  "port": 3306,
  "database": "app",
  "user": "app_user",
  "password": "${ENV:AI_DB_STABLE_PASSWORD}",
  "charset": "utf8mb4",
  "connect_timeout": 10,
  "read_timeout": 30,
  "write_timeout": 30,
  "business_databases": [
    "app"
  ],
  "options": {}
}
```

Required fields:

- `driver`: `mysql`
- `host`
- `database`
- `user`

Recommended fields:

- `password`: Prefer `${ENV:NAME}` instead of a literal secret.
- `port`: Defaults to `3306`.
- `charset`: Defaults to `utf8mb4`.
- `connect_timeout`, `read_timeout`, `write_timeout`: Keep calls bounded for AI workflows.
- `business_databases`: Optional allow-list used by calling agents when they must choose a query database from known business databases.
- `options`: Driver-specific MySQL options.

## Direct Connection

Temporary connections must not create an environment. With a password, must use
`--direct-json` (its connection JSON supports `${ENV:NAME}` expansion); `--url`
must only be used for temporary connections without sensitive information.

```powershell
python <db-query> query --direct-json "{\"driver\":\"mysql\",\"host\":\"127.0.0.1\",\"port\":3306,\"database\":\"app\",\"user\":\"root\",\"password\":\"${ENV:MYSQL_PASSWORD}\"}" --database app --tables users --log-note "按实体映射抽样查询用户" --sql "select * from users limit 1"
python <db-query> query --url "mysql://user@127.0.0.1:3306/app" --database app --tables users --log-note "按实体映射抽样查询用户" --sql "select * from users limit 1"
```

## Environment Resolution

The decision order (session context → git branch → ask the user) is defined once in `SKILL.md`
（环境选择优先级）. `resolve-env` reads only the store and git; it never connects to MySQL.
It returns a unique environment or candidate names for the caller to resolve.

## Commands

`query` only accepts query-oriented SQL such as `SELECT`, `SHOW`, `EXPLAIN`,
`DESCRIBE`, and `DESC`. It has no write override flag and prints `ai-db-query-log`
(database, table names, short SQL summary) and `ai-db-result` (returned rows and
truncation metadata) to stderr. The examples pass
`--database`/`--tables`/`--log-note` because SKILL.md（强制快速路由）requires them for every query.
`--file <utf8-sql-file>` reads SQL from a file, `--params <json>` executes it
parameterized (placeholder `%s`), and `--format json|table` selects the output.
Every `SELECT` must end with an explicit `LIMIT` no larger than `--limit` (a
trailing semicolon is accepted). The defaults
are `--limit 20` and `--max-output-bytes 65536`; result metadata tells the caller when
either bound truncates output. `ai-db-result.sql_limit` carries the literal `LIMIT`
value of the SELECT (or `null` for a parameterized `LIMIT %s` / non-SELECT statements):
when `rows` equals `limit`, the server-side `LIMIT` may hide more rows and
`has_more` cannot detect them, so verify with `count(*)` before claiming completeness.
`ai-db-result.duplicate_columns` lists original column names that appeared more than
once and were renamed with a `_1`/`_2` suffix in the output; prefer explicit column
aliases in the SQL to avoid this.

SQL shape limits (conservative by design): the statement must start with
`select`/`show`/`explain`/`describe`/`desc`; CTE (`WITH ...`), parenthesized queries,
and the two-argument `LIMIT <offset>, <count>` form are rejected — rewrite them as a
single trailing `LIMIT <count> [OFFSET <offset>]` on the outermost level without
changing the query semantics. `SHOW` variants that name a table (`show create table`,
`show full columns from`, `show index from`, ...) extract the table name automatically;
plain `show tables` still reports `<schema-metadata>`.

Every failure prints a single `ai-db-error` JSON line on stderr with a stable `code`:
`INPUT_ERROR` (bad arguments/SQL), `CONNECTION_ERROR` (MySQL connect or execute
failure), `SETUP_ERROR` (missing Python/driver/env var), `STORE_ERROR` (environment
store file or lock), `COMMAND_FAILED` (other).

Resolve `<db-query>` from the current loaded `ai-db` skill root:
`<ai-db-skill>/scripts/db_query.py`. Do not hard-code a user-specific skill
installation path in reusable prompts or docs.

```powershell
python <db-query> init-store
python <db-query> resolve-env
python <db-query> resolve-env --prefer stable
python <db-query> resolve-env --branch "feature/18beta1"
python <db-query> create-env --env 18beta.1-dev
python <db-query> create-env --env stable --from-file <connection-json-file> --default --force
python <db-query> create-env --env stable --from-json "{\"driver\":\"mysql\",\"host\":\"127.0.0.1\",\"port\":3306,\"database\":\"app\",\"user\":\"root\",\"password\":\"${ENV:MYSQL_PASSWORD}\"}" --default --force
python <db-query> list-envs --names
python <db-query> list-envs --format json
python <db-query> show-env --env stable
python <db-query> show-env --env @default
python <db-query> set-default --env stable
python <db-query> test --env stable
python <db-query> query --env stable --database app --tables "<schema-metadata>" --log-note "查看主库表清单" --sql "show tables" --limit 50
python <db-query> query --env stable --database app --tables users --log-note "查看用户表结构" --sql "describe users"
python <db-query> query --env stable --database app --tables users --log-note "按实体映射抽样查询用户" --sql "select * from users limit 5" --format json
python <db-query> query --env stable --database app --tables users --log-note "按实体映射参数化查询用户" --sql "select * from users where id = %s limit 1" --params "[1]" --format json
```
