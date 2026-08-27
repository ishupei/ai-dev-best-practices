---
name: tianyin-wiki
description: 生成或更新天印基线详设/1-N 详设 Markdown（基于 PRD、需求上下文或澄清结果）；也支持任意本地 Markdown 直推 Confluence（raw 模式，不校验格式）；仅在用户明确要求时发布。
---

# Tianyin Wiki

主入口：`scripts/tianyin_wiki.py`。发布、附件上传、认证诊断统一使用该 CLI，不新增第二套写入 Wiki 的脚本。

## 何时使用

- 用户要求生成/更新基线详设或 1-N 详设（触发词：`基线`、`1-N`、`详设`、`wiki`）。
- 用户要求将本地任意 Markdown 文档直接发布/同步到 Confluence（`raw` 模式，不校验格式）。
- 用户明确要求将本地详设发布/同步到 Confluence。

## 三种模式

| 模式 | CLI 标识 | 说明 |
|---|---|---|
| 基线详设 | `baseline`（默认） | 按基线模板生成并校验结构 |
| 1-N 详设 | `1-n` | 按 1-N 模板生成并校验结构 |
| 直推本地 md | `raw`（别名 `direct`） | 不校验任何格式，直接把本地 Markdown 转为 wiki 页面 |

默认模式取自个人配置文件 `template` 字段（`baseline`/`1-n`/`raw`）；未配置时缺省 `baseline`。命令行显式传 `--template` 优先于配置文件。

## 输出约定（生成本地详设时）

- **输出路径**：优先使用文档约定路径（如 `docs/<功能目录名>/`）；无约定时输出到工作目录 `docs/` 下。
- **输出文件名**：`DESIGN-<功能名>.md`（功能名按上下文确定，如 `DESIGN-电子签章.md`）。
- **非必填章节**：所有章节均为非必填；生成文档时如某章节确实不涉及（如无接口新增/变更），保留标题并填写「未涉及」，不要编造内容。模板内 `<!-- ... -->` 注释为填写指引，只存在于模板源文件：`init-template` 复制时自动剔除、`lint-doc` 校验交付文档不得含注释行、发布/粘贴转换兜底剔除，**生成文档一律不携带注释**。

## 最小流程

1. 初始化模板：`python .\scripts\tianyin_wiki.py init-template [--template 1-n] --output <file>.md`（不传 `--template` 时默认读取配置 `template` 字段）。
2. 填充内容后用 `lint-doc` 本地自查；发布时结构差异（缺项/多项）仅提示、不阻断推送。
3. 直推任意本地文档（不校验格式）：`python .\scripts\tianyin_wiki.py publish-md --template raw --input <file>.md`。
4. 仅当用户**明确确认**（且上下文中已提供目标地址）时发布：`publish-md --remote-url "<wiki-url>"`。

## 执行边界（必须遵守）

1. **本地 md 是唯一事实源**：改动必须**先落地到本地 md 文件**，禁止跳过本地文件直接修改远程 wiki。
2. **不自动推送**：更新本地 md 后不立即推送；仅当用户**明确确认**（且上下文中已提供目标地址）时，才用当前本地 md 内容更新 wiki。
3. 未明确要求发布/未提供目标地址时只处理本地文件；远程发布优先 REST `publish-md`，认证/网关异常先 `diagnose-auth`；浏览器登录态发布仅限用户明确要求。
4. 不读取、导出或回显密码、token、Cookie、LocalStorage、会话文件、Authorization 头或扫码信息。

## 按需参考（渐进式披露，需要时再读取）

- 完整 CLI 参数、Mermaid 与图片细节：`references/cli-reference.md`
- 模板结构与填写指引：`references/templates/`（模板内 `<!-- ... -->` 注释为唯一指引源，生成文档时不得保留）
- 发布与认证（ZeroTrust、浏览器兜底）：`references/remote-publish.md`
- 环境依赖与凭据配置：`references/setup.md`
