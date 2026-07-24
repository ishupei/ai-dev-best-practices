---
name: ai-db
description: "显式 MySQL 数据库查询与调用链辅助。当用户输入 /ai-db、$ai-db，或其他 skill/AI 调用链明确要求使用 ai-db 时触发；支持本地 JSON 环境存储、自定义环境名如 18beta.1-dev/stable、每个环境独立连接 JSON、MySQL 连通性测试和查询类 SQL 执行；调用链使用时必须先从工程模块、上下文、实体类或明确输入确定主库和表名，无法确定时中断，且以只查询不增删改为第一原则。"
---

# AI DB

此技能给 AI 或其他 skill 的调用链使用，用于在显式授权下查询 MySQL。
默认存储目录为 `%USERPROFILE%\.codex\ai-db\`，可通过 `AI_DB_DIR` 或
`--store-dir` 覆盖。

## 渐进式披露

- 执行普通查询、列环境、建环境时，只需要本文件和 `scripts/db_query.py`。
- 需要了解环境 JSON 结构、目录布局或示例时，再读取 `references/config-format.md`。
- 不要把真实连接配置、密码或大批量查询结果写入对话、文档或仓库。
- 不要在方案或回答中写死本机 skill 安装路径；调用脚本时从当前已加载的 `ai-db` skill 根目录解析 `scripts/db_query.py`。

## 原则与边界

- 只有显式调用 `/ai-db`、`$ai-db` 或调用链明确要求 `ai-db` 时才使用。
- 默认只考虑 MySQL；其他数据库暂不处理，不要主动扩展。
- 不要编造环境、库名、表名、账号或密码；缺失时使用 `create-env` 生成模板，或要求调用方提供连接 JSON。
- 调用链使用时以查询为第一原则，只做查询和元数据查看，不做新增、删除、修改、DDL、锁表、导出文件或批量变更。
- 查询前必须确定主库和表名。优先依据工程模块、上下文、实体类、Mapper/DAO/Repository、SQL XML/注解、配置或用户明确输入；如果无法确定，直接中断并说明缺少哪些依据，拒绝猜测性处理。
- 环境名允许自定义，例如 `18beta.1-dev`、`stable`、`uat_2`；每个环境必须关联一个独立 JSON 连接配置。
- `init-store`、`create-env`、`set-default` 等环境存储写操作必须串行执行，不要在同一个 store 上并行写索引。
- 输出连接信息时必须脱敏；不要输出完整连接 JSON。
- 显式调用后，每次执行 `query` 都必须在 AI 调用日志或脚本日志中打印库名、表名和简要查询日志；`scripts/db_query.py query` 会向 stderr 输出 `ai-db-query-log`。

## 调用链工作流

1. 解析脚本路径：`db_query = <当前 ai-db skill 根目录>/scripts/db_query.py`。下文 `<db-query>` 均指这个运行时解析出的实际路径，不是要照抄的固定字符串。
2. 明确目标：环境管理、连通性测试、查元数据或查业务数据。
3. 确定主库和表名：
   - 先从用户输入、工程模块名、包名、实体类、Mapper/DAO/Repository、SQL XML/注解、配置文件和既有上下文定位业务域。
   - 在环境配置含 `business_databases` 时，主库必须从该列表中选定；不能仅凭名称相似猜测。
   - 表名必须来自实体映射、SQL、表结构查询结果或用户明确输入；不能凭字段名或业务词猜。
   - 如果主库或表名任一无法确认，中断本次数据库查询，输出缺失依据和下一步需要读取的工程文件或用户确认项。
4. 如调用方未指定环境，先执行 `list-envs`；存在默认环境时可使用 `--env @default`。
5. 如果环境不存在，使用 `create-env --env <name>` 创建模板，等待调用方补齐真实连接信息。
6. 查询前优先小步验证：
   - `test --env <name>` 验证连接。
   - `query --env <name> --sql "show tables" --limit 50` 或 `describe <table>` 验证结构。
7. 执行业务查询 SQL，默认限制 `--limit 100`；如果目标库不是环境默认库，必须传 `--database <已确定主库>`；必须传 `--tables <已确定表名>` 和 `--log-note <简要目的>` 以形成调用日志。
8. 失败时先自我优化，再决定是否询问调用方：
   - 环境不存在：列出已有环境，建议创建或切换环境。
   - 连接失败：检查 host、port、database、user、密码环境变量和 MySQL 驱动。
   - 表/字段不存在：用 `show tables`、`describe <table>` 收敛 SQL。
   - 语法失败：按 MySQL 方言重写 SQL，避免跨库函数。
   - 权限不足、需要增删改或语义不确定：停止并说明需要调用方确认，不能用 `query` 命令执行变更。

## 常用命令

```powershell
python <db-query> init-store
python <db-query> create-env --env 18beta.1-dev
python <db-query> list-envs
python <db-query> show-env --env stable
python <db-query> set-default --env stable
python <db-query> test --env stable
python <db-query> query --env stable --database stable_esign6_docs --tables doc_table --log-note "按实体映射查询文档记录" --sql "select * from doc_table limit 1"
```

## 直连

调用链临时连接 MySQL 时可不落环境。有密码时优先用 `--direct-json`，因为连接 JSON 支持 `${ENV:NAME}` 展开；URL 只适合不含敏感信息的临时连接。

```powershell
python <db-query> query --direct-json "{\"driver\":\"mysql\",\"host\":\"127.0.0.1\",\"port\":3306,\"database\":\"app\",\"user\":\"root\",\"password\":\"${ENV:MYSQL_PASSWORD}\"}" --database app --tables users --log-note "按实体映射抽样查询用户" --sql "select * from users limit 1"
python <db-query> query --url "mysql://user@127.0.0.1:3306/app" --database app --tables users --log-note "按实体映射抽样查询用户" --sql "select * from users limit 1"
```

## 输出要求

- 说明环境名、目标库、SQL 目的、行数限制和查询性质。
- 每次 `query` 的日志必须包含：库名、表名、简要查询日志；优先使用脚本输出的 `ai-db-query-log`。
- 查询成功时只给必要字段和少量结果；需要完整导出时让调用方明确范围。
- 查询失败时给错误类型、已尝试的自我优化步骤和下一步最小可执行动作。
