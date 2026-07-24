# AI DB MySQL Environment Store

Read this file only when environment storage details are needed.

## Store Location

Default:

```text
%USERPROFILE%\.codex\ai-db\
```

Override order:

1. `--store-dir <dir>`
2. `AI_DB_DIR`
3. `%USERPROFILE%\.codex\ai-db\`

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

Environment names may contain letters, digits, dots, underscores, and hyphens. Examples:
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

## Commands

`query` only accepts query-oriented SQL such as `SELECT`, `SHOW`, `EXPLAIN`,
`DESCRIBE`, and `DESC`. It has no write override flag.
When the caller has determined the target database and table from code/context/entity
classes, pass `--database`, `--tables`, and `--log-note`; the script prints
`ai-db-query-log` to stderr with database, table names, and a short SQL summary.

Resolve `<db-query>` from the current loaded `ai-db` skill root:
`<ai-db-skill>/scripts/db_query.py`. Do not hard-code a user-specific skill
installation path in reusable prompts or docs.

```powershell
python <db-query> init-store
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
```
