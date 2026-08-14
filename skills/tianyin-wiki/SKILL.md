---
name: tianyin-wiki
description: 生成或更新天印基线详设/1-N 详设 Markdown（基于 PRD、需求上下文或澄清结果）；仅在用户明确要求时发布到 Confluence。
---

# Tianyin Wiki

主入口：`scripts/tianyin_wiki.py`。发布、附件上传、认证诊断统一使用该 CLI，不新增第二套写入 Wiki 的脚本。

## 何时使用

- 用户要求生成/更新基线详设或 1-N 详设（触发词：`基线`、`1-N`、`详设`、`wiki`）。
- 用户明确要求将本地详设发布/同步到 Confluence。

## 输出约定（生成本地详设时）

- **输出路径**：优先使用文档约定路径（如 `docs/<功能目录名>/`）；无约定时输出到工作目录 `docs/` 下。
- **输出文件名**：`DESIGN-<功能名>.md`（功能名按上下文确定，如 `DESIGN-电子签章.md`）。

## 最小流程

1. 初始化模板：`python .\scripts\tianyin_wiki.py init-template [--template 1-n] --output <file>.md`（默认基线模板）。
2. 填充内容后用 `lint-doc` 本地自查；发布时结构差异（缺项/多项）仅提示、不阻断推送。
3. 仅当用户**明确确认**（且上下文中已提供目标地址）时发布：`publish-md --remote-url "<wiki-url>"`。

## 执行边界（必须遵守）

1. **本地 md 是唯一事实源**：改动必须**先落地到本地 md 文件**，禁止跳过本地文件直接修改远程 wiki。
2. **不自动推送**：更新本地 md 后不立即推送；仅当用户**明确确认**（且上下文中已提供目标地址）时，才用当前本地 md 内容更新 wiki。
3. 未明确要求发布/未提供目标地址时只处理本地文件；远程发布优先 REST `publish-md`，认证/网关异常先 `diagnose-auth`；浏览器登录态发布仅限用户明确要求。
4. 不读取、导出或回显密码、token、Cookie、LocalStorage、会话文件、Authorization 头或扫码信息。

## 按需参考（渐进式披露，需要时再读取）

- 完整 CLI 参数、Mermaid 与图片细节：`references/cli-reference.md`
- 模板结构规则：`references/rules/baseline-template-rules.md`、`references/rules/1-n-template-rules.md`
- 发布与认证（ZeroTrust、浏览器兜底）：`references/remote-publish.md`
- 环境依赖与凭据配置：`references/setup.md`
