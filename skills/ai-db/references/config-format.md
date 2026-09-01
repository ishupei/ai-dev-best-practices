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

Environment names must contain only letters, digits, dots, underscores, and hyphens. Examples:
`18beta.1-dev`, `stable`, `uat_2`.

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
（环境选择优先级）. `status` is a one-shot environment judgment for skill load: store
initialization state, current git branch, branch-inferred candidates, default env, and
secret-free env summaries. Both `status` and `resolve-env` only read the store and git;
they never connect to MySQL.

## Commands

`query` only accepts query-oriented SQL such as `SELECT`, `SHOW`, `EXPLAIN`,
`DESCRIBE`, and `DESC`. It has no write override flag and prints `ai-db-query-log`
(database, table names, short SQL summary) to stderr. The examples pass
`--database`/`--tables`/`--log-note` because SKILL.md（强制快速路由）requires them for every query.
`--file <utf8-sql-file>` reads SQL from a file, `--params <json>` executes it
parameterized (placeholder `%s`), and `--format json|csv|table` selects the output.

Resolve `<db-query>` from the current loaded `ai-db` skill root:
`<ai-db-skill>/scripts/db_query.py`. Do not hard-code a user-specific skill
installation path in reusable prompts or docs.

```powershell
python <db-query> init-store
python <db-query> status
python <db-query> resolve-env
python <db-query> resolve-env --prefer stable
python <db-query> resolve-env --branch "feature/18beta1"
python <db-query> create-env --env 18beta.1-dev
python <db-query> create-env --env stable --from-file <connection-json-file> --default --force
python <db-query> create-env --env stable --from-json "{\"driver\":\"mysql\",\"host\":\"127.0.0.1\",\"port\":3306,\"database\":\"app\",\"user\":\"root\",\"password\":\"${ENV:MYSQL_PASSWORD}\"}" --default --force
python <db-query> list-envs --format json
python <db-query> show-env --env stable
python <db-query> set-default --env stable
python <db-query> test --env stable
python <db-query> query --env stable --database app --tables "<schema-metadata>" --log-note "查看主库表清单" --sql "show tables" --limit 50
python <db-query> query --env stable --database app --tables users --log-note "查看用户表结构" --sql "describe users"
python <db-query> query --env stable --database app --tables users --log-note "按实体映射抽样查询用户" --sql "select * from users limit 5" --format json
python <db-query> query --env stable --database app --tables users --log-note "按实体映射参数化查询用户" --sql "select * from users where id = %s" --params "[1]" --format json
python <db-query> query --env stable --database app --tables users --log-note "按实体映射导出用户数据" --file .\users.sql --format csv
```
