---
name: ai-db
description: "显式 MySQL 查询辅助。当用户输入 /ai-db、$ai-db，或其他 skill/AI 调用链明确要求使用 ai-db 时触发；只执行查询，不执行增删改或 DDL；可按用户要求生成供人工执行的变更 SQL 草案。主库和表名必须从代码、上下文、实体或用户输入确定，无法确定时中断。"
---

# AI DB

给 AI 或其他 skill 调用链在显式授权下查询 MySQL。脚本入口 `<ai-db-skill>/scripts/db_query.py`（下称 `<db-query>`）；Windows 必须用 `scripts/python_probe.ps1` 代替 `python <db-query>`。

## 强制快速路由

多意图并存时按 查询执行 > 变更 SQL 草案 > 测试 > 环境管理 > 环境修复 处理；任何脚本动作前 MUST 选择且只选择一个路由。必须复用会话已确认的环境/库/表；信息不足只追问当前路由必需项，禁止读参考文档代替澄清、禁止扫描无关内容。

首次使用且未显式指定连接源时，先运行一次 `resolve-env`（只读 store 与 git，不触网不连库）；已传 `--env`、`--direct-json` 或 `--url` 时不再重复判定。

**快速路径**：环境、库、表和查询目的均已确认时直接 `query`；仅在连接未知、定位证据不足或用户明确要求时运行 `test`、`show tables` 或 `describe`。

1. **环境判定**（未显式指定连接源时）：按「环境选择优先级」执行，唯一命中前禁止执行查询。
2. **连通性测试**：直接 `test --env <name>`，读取输出 `ok` 字段；上下文已有该环境成功连通/查询记录时跳过，除非调用方明确要求测试。
3. **查询/元数据**：按「主库与表名标定」确定库和表，禁止猜测；仅在证据不足时小步验证 → `query`（必须传 `--database`/`--tables`/`--log-note`，默认 `--limit 20`）。
4. **环境管理**：`init-store`/`create-env`/`list-envs`/`show-env`/`set-default`；写操作必须串行，禁止并行写索引。
5. **环境修复**：Python/驱动/连接异常时按脚本报错自我优化；无法解决时读 `references/setup.md`。

## 变更 SQL 草案

用户明确要求编写 `INSERT`/`UPDATE`/`DELETE`/DDL 等变更语句时，可以输出 SQL 草案，但只能供用户或 DBA 审核后手动执行：

- MUST NOT 将任何变更 SQL 传给 `<db-query>`，也不得使用 `query`、`test` 或其他脚本命令执行它。
- 输出前必须标注“**仅供人工审核和执行，ai-db 未执行**”，并说明预期影响范围；无法判断影响范围时明确写“需确认”。
- 不得把草案描述为已执行、已更新、已建表或执行成功；用户要求执行时，说明该 skill 不执行变更操作。

## 环境选择优先级

未显式指定连接源（`--env`/`--direct-json`/`--url`）时，必须按序判定，唯一命中即停止：

1. 上下文曾指定或推断 → `resolve-env --prefer <env>` 校验。
2. git 分支精确匹配 → `resolve-env`（仅包含关系一律视为候选，禁止自动采用）。
3. 兜底 → 打印 `list-envs --names`，向用户索要连接信息（`create-env --from-json` 或 `--direct-json`）；多候选必须按业务域上下文收敛，仍无法确定必须询问用户，禁止自行挑选。

## 主库与表名标定

未显式指定库/表时，以会话上下文与当前工作工程为显式标定依据，按下列来源顺序命中，命中即停止，禁止猜测：

- **库名**：工程名/模块名 → 配置文件数据源（`application.yml`/`bootstrap.yml` 的 datasource、jdbc url）→ 环境 JSON 的 `business_databases`（存在时主库必须从中选定）→ 上下文已确认的库。
- **表名**：实体类 DO/entity/PO（类名驼峰转下划线，或 `@TableName`/`@Table` 注解）→ Mapper/DAO/Repository 与 SQL XML/注解中的表引用 → 上下文已确认的表。
- 依据不足时：小步验证（`show tables`/`describe`）收敛；仍无法确定必须中断并说明缺失依据。

## 上下文证据包

首次定位后在会话中复用以下最小证据包，避免重复扫描工程：`env`、`database`、`tables`、`intent`、`evidence_paths`（数据源/实体/Mapper 的路径）和 `verified_at`。仅当模块、分支、数据源或表目标变化时重新定位。

定位时每类证据只做当前模块内的精确搜索：先数据源配置，再实体注解，再 Mapper/SQL；任一来源已能确认时停止，禁止全仓库兜底扫描。

## 绝对边界

- 只执行查询：`query` 禁止 DDL/DML、锁表、导出文件、多语句和 MySQL 可执行注释（`/*! ... */`）；无写覆盖参数。
- 允许生成、禁止执行：变更 SQL 只能按「变更 SQL 草案」输出，永远不得通过本 skill 连接数据库执行。
- 为满足校验而补写或改写 SQL 时，`LIMIT` 必须加在语句最外层并保持原查询语义；禁止通过删除或移动排序、去重、分组、锁等子句来通过校验。
- 禁止编造环境、库、表、账号、密码；主库/表名无法从代码、上下文、实体或用户输入确定时，必须中断并说明缺失依据。
- 输出连接信息必须脱敏；禁止把密码、完整连接 JSON 或大批量结果写入对话、文档、仓库。
- 禁止在方案中写死本机 skill 安装路径。

## 输出要求

- 必须声明本次实际使用的环境/库/表、SQL 目的与行数限制，引用本次 stderr 的 `ai-db-query-log` 与 `ai-db-result`，禁止凭记忆复述。
- 成功只给必要字段与少量结果；需要完整导出时必须让调用方明确范围。
- `SELECT` 必须以不超过 `--limit` 的显式 `LIMIT` 结束；`query` 默认最多返回 20 行和 64KiB stdout。`ai-db-result.has_more` 或 `output_truncated` 为 `true` 时，必须说明结果不完整并让调用方缩小范围后重试。
- 返回行数等于 `--limit` 时禁止断言“无更多数据”：SQL 自带的 `LIMIT` 会在服务器端先截断，`fetchmany(limit+1)` 探测因此失效，`has_more` 恒为 `false`。必须核对 `ai-db-result.sql_limit`（`null` 表示参数化 LIMIT 或非 SELECT），必要时执行 `count(*)` 或缩小范围确认实际规模。
- `ai-db-result.duplicate_columns` 非空时，说明结果中同名列已被重命名（如 `id` → `id_1`），输出字段不完整对应原表列；应建议调用方为 join 列显式加别名后再查询。
- 输出变更 SQL 草案时，必须重复“仅供人工审核和执行，ai-db 未执行”的标识，并给出影响范围或“需确认”。
- 失败必须输出错误类型、已执行的自我优化步骤、下一步最小可执行动作；`ai-db-error.code` 取值为 `INPUT_ERROR`（参数/SQL 问题）、`CONNECTION_ERROR`（MySQL 连接或执行失败）、`SETUP_ERROR`（Python/驱动/环境变量缺失）、`STORE_ERROR`（环境存储文件或锁问题）、`COMMAND_FAILED`（其他），按错误码选择自我优化方向。

## 延迟读取

- 环境 JSON 结构、目录布局、命令全集、直连示例：`references/config-format.md`
- Python/驱动安装、国内镜像、`AI_DB_PYTHON`/`AI_DB_DIR` 环境变量：`references/setup.md`
- 常规查询、列环境、建环境时禁止读取以上文件。
