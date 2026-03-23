## Project Structure

- **根目录**:
  - `.cursor/`：Cursor 相关配置与规则（含 `rules/`、`skills/`）。技能衔接示例：`ai-bug` 在 BUG 上下文不足时 **MUST** 按 `ai-clear` 的 Step 2 澄清提问；`ai-summary` 将需求/进度**精准摘要**写入 `docs/<功能目录名>/SUMMARY-*.md` 供新会话快速对齐。
  - `.claude/`：Claude Code 配置；**技能**位于 **`skills/<name>/SKILL.md`**（目录形式，与官方 Skills 一致）。`commands/` 已弃用扁平 `*.md`，详见 `docs/SKILLS-Claude开发规范.md`。与 `.cursor/skills/` 内容宜保持同步。
  - `.trae/`：Trae 相关配置与规则（含 `rules/`、`skills/`）。
  - `.content/`：工程结构与元信息文档（当前文件）。

### Rules 结构

- **Cursor 规则**（`.cursor/rules`）
  - `global-dev.mdc`：**全局开发规范（global-level）**
    - 定义身份（Java Backend + SpringBoot / Vue Frontend）。
    - 通用推荐实践（Objects/Hutool/Log/BeanUtil/ServiceImpl/MyBatis-Plus/StringPool）。
    - 通用禁止实践（禁止使用完全限定类名等）。
  - `dev-project.mdc`：**项目级规范（project-level）**
    - 文档与 SQL 文件目录约定：`docs/`、`sql/`。
    - **需求类 Markdown**：按功能在 `docs/<功能目录名>/` 下集中存放 SRS、TDD、DESIGN、TASKS、**SUMMARY（上下文摘要，由 `ai-summary` 维护）** 等；**BUG 分析报告**统一在 **`docs/bugfix/`**，**不**放在功能目录（详见 `.cursor/skills/ai-draft`、`ai-bug`）。
    - 工程结构文档维护约定：`.content/project-structure.md`。

- **Trae 规则**（`.trae/rules`）
  - `global-dev.md`：**全局开发规范（global-level）**，内容与 `global-dev.mdc` 对齐。
  - `dev-project.md`：**项目级规范（project-level）**，内容与 `dev-project.mdc` 对齐（文件组织与工程结构约定）。

> 后续如果新增模块（如 `backend/`、`frontend/`、`docs/` 等），应同步在本文件补充说明结构与规则适用范围。

