# Claude Code 项目内 Skills 开发规范

本文档约定本仓库中 **Claude Code** 与 **Cursor** 的技能如何组织、命名与同步，便于目录化管理并与 [Claude Code Skills 官方说明](https://docs.anthropic.com/en/docs/claude-code/slash-commands) 一致。

## 1. 目录形式（推荐、本仓库采用）

| 环境 | 路径 | 说明 |
|------|------|------|
| **Claude Code（项目级）** | `.claude/skills/<skill-name>/SKILL.md` | 每个技能**独立子目录**，入口文件固定为 `SKILL.md`；可在此目录下增加模板、示例、脚本等附属文件。 |
| **Cursor（项目级）** | `.cursor/skills/<skill-name>/SKILL.md` | 同上，与 Claude 对齐，便于双端同源维护。 |

- **斜杠命令名**：由 `SKILL.md` 前置 YAML 中的 `name` 字段决定（如 `name: ai-draft` → `/ai-draft`）。`name` 使用小写字母、数字、连字符，与目录名 `<skill-name>` **保持一致**。
- **扁平 `.claude/commands/*.md`**：官方仍支持，但与「目录型 Skill」并存时 **同名以 `.claude/skills/` 为准**。本仓库**已弃用** `.claude/commands/*.md`，避免重复与混淆。

## 2. 与 Cursor 的同步策略

- **内容权威源**：本仓库以 **`.cursor/skills/<name>/SKILL.md`** 与 **`.claude/skills/<name>/SKILL.md`** 保持**同构同内容**（修改后应两边同步，或仅以一侧为准定期复制）。
- **推荐工作流**：在中心仓库修改 `.cursor/skills` 后，执行同步复制到 `.claude/skills`（或使用项目内 `sync-skills` 脚本将全局/多项目一并更新，见根目录 `README.md`）。

## 3. SKILL.md 必备结构

1. **YAML Frontmatter**（文件开头）  
   - `name`：命令名，与目录名一致。  
   - `description`：一句话说明触发场景与产出，供模型检索与发现。

2. **正文**：`Usage`、`Role & Scope`、分步流程、`Checklist` 等，与现有 `ai-*` 技能风格一致。

3. **跨技能引用**：引用本仓库其他技能时，路径写 **`.cursor/skills/<name>/SKILL.md`** 或 **`.claude/skills/<name>/SKILL.md`** 均可（同一仓库内二者等价）。

## 4. 全局安装（`~/.claude/skills/`）

将本仓库 `.claude/skills/` 下各子目录复制到用户目录 **`~/.claude/skills/`**（保持 `技能名/SKILL.md` 结构），即可在所有项目中使用相同斜杠命令。根目录 **`sync-skills.ps1` / `sync-skills.sh`** 已按**目录结构**同步到全局，不再使用 `~/.claude/commands/*.md` 扁平复制。

## 5. 附属文件（可选）

在 `.claude/skills/<name>/` 下可增加：

- `examples.md`、`reference.md`、片段模板等；  
- 在 `SKILL.md` 正文中说明何时读取这些文件，避免全部塞进上下文。

## 6. 检查清单（新增或修改技能时）

- [ ] 已创建 `.claude/skills/<name>/` 与 `.cursor/skills/<name>/`（若需双端一致）。  
- [ ] `SKILL.md` 含合法 `name` / `description`。  
- [ ] 已更新根目录 `README.md` 中的结构说明（若新增顶层技能）。  
- [ ] 已运行同步脚本或手动复制，避免仅改一侧导致漂移。

---

*文档位置：`docs/SKILLS-Claude开发规范.md`，与项目 `dev-project` 规则中 `docs/` 约定一致。*
