# 统一 Skills / Rules 开发规范

本文档约定本仓库中 Skills 和 Rules 的组织、命名与同步方式。仓库内不再区分 Claude / Cursor / Trae 的多套目录，统一以根目录 `skills/` 与 `rules/` 作为唯一权威源。

## 1. 目录形式

| 类型 | 路径 | 说明 |
|------|------|------|
| 仓库内权威源 | `skills/<skill-name>/SKILL.md` | 每个技能使用独立子目录，入口文件固定为 `SKILL.md`。 |
| Claude Code 全局安装 | `~/.claude/skills/<skill-name>/SKILL.md` | 由同步脚本从仓库 `skills/` 复制。 |
| Cursor 项目安装 | `<project>/.cursor/skills/<skill-name>/SKILL.md` | 由同步脚本从仓库 `skills/` 复制或链接。 |
| 仓库内规则源 | `rules/<rule-name>.md` | 统一规则源文件。 |
| Cursor 项目规则 | `<project>/.cursor/rules/<rule-name>.mdc` | 由同步脚本从仓库 `rules/` 生成或链接。 |

- `name` 字段决定斜杠命令名，例如 `name: ai-draft` 对应 `/ai-draft`。
- `name` 应使用小写字母、数字、连字符，并与目录名保持一致。
- 扁平 `.claude/commands/*.md` 已弃用，本仓库不再维护该形式的技能内容。

## 2. 同步策略

- `skills/` 是唯一内容源，所有技能修改都在这里完成。
- `rules/` 是唯一规则源，所有规则修改都在这里完成。
- `sync-skills.ps1` 和 `sync-skills.sh` 负责把 `skills/` 与 `rules/` 分发到目标环境。

## 3. SKILL.md 必备结构

1. YAML Frontmatter
   `name`：命令名，与目录名一致。
   `description`：一句话描述触发场景和产出。
2. 正文
   建议包含 `Usage`、角色范围、分步流程、检查清单等。
3. 跨技能引用
   统一使用 `skills/<name>/SKILL.md` 路径，不再引用 `.claude/skills/...` 或 `.cursor/skills/...`。

## 4. 附属文件

可在 `skills/<name>/` 下增加示例、模板、参考资料或脚本，并在 `SKILL.md` 中说明何时读取。

## 5. 检查清单

- [ ] 已在 `skills/<name>/` 下创建或修改技能。
- [ ] 已在 `rules/<name>.md` 下创建或修改规则（如适用）。
- [ ] `SKILL.md` 含合法 `name` / `description`。
- [ ] 如有新增顶层技能，已更新 `README.md`。
- [ ] 已运行同步脚本，确认 Claude / Cursor / Trae 分发结果正确。
