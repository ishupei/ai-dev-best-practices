## Project Structure

- **根目录**:
  - `.cursor/`：Cursor 相关配置（含 `skills/`）。技能衔接示例：`ai-bug` 在 BUG 上下文不足时 **MUST** 按 `ai-clear` 的 Step 2 澄清提问；`ai-summary` 将需求/进度**精准摘要**写入 `docs/<功能目录名>/SUMMARY-*.md` 供新会话快速对齐。
  - `.claude/`：Claude Code 配置；技能使用 `skills/<name>/SKILL.md` 的目录结构进行同步维护，与 `.cursor/skills/` 内容宜保持同步。
  - `.trae/`：Trae 相关配置（含 `skills/`）。
  - `.content/`：工程结构与元信息文档（当前文件）。
  - `skills/`：技能权威源目录。技能可包含 `references/` 作为附属规范或参考资料；例如 `skills/ai-do/references/code-standards.md` 用于约束 `/ai-do` 的代码生成与验证。

> 后续如果新增模块（如 `backend/`、`frontend/`、`docs/` 等），应同步在本文件补充说明结构与规则适用范围。
