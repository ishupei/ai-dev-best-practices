---
name: ai-db
description: "显式 MySQL 查询辅助。当用户输入 /ai-db、$ai-db，或其他 skill/AI 调用链明确要求使用 ai-db 时触发；只查询不增删改；主库和表名必须从代码、上下文、实体或用户输入确定，无法确定时中断。"
---

# AI DB

给 AI 或其他 skill 调用链在显式授权下查询 MySQL。脚本入口 `<ai-db-skill>/scripts/db_query.py`（下称 `<db-query>`）；Windows 必须用 `scripts/python_probe.ps1` 代替 `python <db-query>`。

## 强制快速路由

多意图并存时按 查询 > 测试 > 环境管理 > 环境修复 处理；任何动作前 MUST 选择且只选择一个路由。必须复用会话已确认的环境/库/表；信息不足只追问当前路由必需项，禁止读参考文档代替澄清、禁止扫描无关内容。

首次使用或上下文无任何环境信息时，必须先运行一次 `status`（只读 store 与 git，不触网不连库）再进入对应路由。

1. **环境判定**（未显式指定连接源时）：按「环境选择优先级」执行，唯一命中前禁止执行查询。
2. **连通性测试**：直接 `test --env <name>`，读取输出 `ok` 字段；上下文已有该环境成功连通/查询记录时跳过，除非调用方明确要求测试。
3. **查询/元数据**：按「主库与表名标定」确定库和表，禁止猜测 → 小步验证仅首次需要（`test` → `show tables`/`describe`），上下文已有该环境成功连通/查询记录时跳过 → `query`（必须传 `--database`/`--tables`/`--log-note`，默认 `--limit 100`）。
4. **环境管理**：`init-store`/`create-env`/`list-envs`/`show-env`/`set-default`；写操作必须串行，禁止并行写索引。
5. **环境修复**：Python/驱动/连接异常时按脚本报错自我优化；无法解决时读 `references/setup.md`。

## 环境选择优先级

未显式指定连接源（`--env`/`--direct-json`/`--url`）时，必须按序判定，唯一命中即停止：

1. 上下文曾指定或推断 → `resolve-env --prefer <env>` 校验。
2. git 分支精确匹配 → `resolve-env`（仅包含关系一律视为候选，禁止自动采用）。
3. 兜底 → 打印 `list-envs`，向用户索要连接信息（`create-env --from-json` 或 `--direct-json`）；多候选必须按业务域上下文收敛，仍无法确定必须询问用户，禁止自行挑选。

## 主库与表名标定

未显式指定库/表时，以会话上下文与当前工作工程为显式标定依据，按下列来源顺序命中，命中即停止，禁止猜测：

- **库名**：工程名/模块名 → 配置文件数据源（`application.yml`/`bootstrap.yml` 的 datasource、jdbc url）→ 环境 JSON 的 `business_databases`（存在时主库必须从中选定）→ 上下文已确认的库。
- **表名**：实体类 DO/entity/PO（类名驼峰转下划线，或 `@TableName`/`@Table` 注解）→ Mapper/DAO/Repository 与 SQL XML/注解中的表引用 → 上下文已确认的表。
- 依据不足时：小步验证（`show tables`/`describe`）收敛；仍无法确定必须中断并说明缺失依据。

## 绝对边界

- 只查询：禁止 DDL/DML/锁表/导出文件/批量变更；`query` 无写覆盖参数。
- 禁止编造环境、库、表、账号、密码；主库/表名无法从代码、上下文、实体或用户输入确定时，必须中断并说明缺失依据。
- 输出连接信息必须脱敏；禁止把密码、完整连接 JSON 或大批量结果写入对话、文档、仓库。
- 禁止在方案中写死本机 skill 安装路径。

## 输出要求

- 必须声明本次实际使用的环境/库/表、SQL 目的与行数限制，引用本次脚本输出（stderr 的 `-- env=... database=... rows=...` 确认行与 `ai-db-query-log`），禁止凭记忆复述。
- 成功只给必要字段与少量结果；需要完整导出时必须让调用方明确范围。
- 失败必须输出错误类型、已执行的自我优化步骤、下一步最小可执行动作。

## 延迟读取

- 环境 JSON 结构、目录布局、命令全集、直连示例：`references/config-format.md`
- Python/驱动安装、国内镜像、`AI_DB_PYTHON`/`AI_DB_DIR` 环境变量：`references/setup.md`
- 常规查询、列环境、建环境时禁止读取以上文件。
