# AI Dev Best Practices

AI 辅助开发技能体系，使用统一 `skills/` 与 `rules/` 目录管理 Claude Code / Cursor / Trae 的能力定义，一处维护，多项目同步。

## 项目结构

```text
ai-dev-best-practices/
├── skills/                 # 唯一技能源目录
│   ├── ai-bug/SKILL.md
│   ├── ai-clear/SKILL.md
│   ├── ai-commit/SKILL.md
│   ├── ai-design/SKILL.md
│   ├── ai-do/SKILL.md
│   ├── ai-draft/SKILL.md
│   ├── ai-plan/SKILL.md
│   ├── ai-push/SKILL.md
│   ├── ai-summary/SKILL.md
│   ├── ai-task/SKILL.md
│   ├── design-phase/SKILL.md
│   └── git-commit/SKILL.md
├── rules/                  # 唯一规则源目录
│   ├── global-dev.md
│   ├── self-project.md
│   └── work-project.md
├── .claude/
│   └── commands/README.md
├── .trae/                  # Trae 配置目录
├── docs/
│   └── SKILLS-Claude开发规范.md
├── sync-skills.ps1
├── sync-skills.sh
└── README.md
```

## 技能一览

| 命令 | 用途 | 触发方式 |
|------|------|----------|
| `/ai-draft` | 根据需求描述生成 DRAFT 初稿 | 输入需求描述 |
| `/ai-clear` | 多轮问答澄清需求中的歧义和缺失 | 需求初稿就绪后 |
| `/ai-plan` | 生成技术方案与总体设计 | 需求确认后 |
| `/ai-design` | 生成详细技术设计文档 | 技术方案确认后 |
| `/ai-task` | 将设计拆解为可执行的开发任务 | 设计文档就绪后 |
| `/ai-do` | 逐个执行开发任务并验证 | 任务拆解完成后 |
| `/ai-bug` | BUG 定位、根因分析、修复方案 | 发现 BUG 时 |
| `/ai-commit` | 生成标准化中文 commit message | 代码变更后 |
| `/ai-push` | Git 提交推送 | 准备推送时 |
| `/ai-summary` | 上下文摘要写入 SUMMARY.md | 长对话或新开窗口前 |

统一约定见 `docs/SKILLS-Claude开发规范.md`。

## 同步工具使用

| 环境 | 脚本 |
|------|------|
| Windows | `sync-skills.ps1` |
| macOS / Linux | `sync-skills.sh` |

### 同步原理

```text
ai-dev-best-practices/（中心仓库，唯一维护点）
│
├── skills/<name>/SKILL.md  ── 复制 ──> ~/.claude/skills/<name>/   (Claude Code 全局生效)
├── skills/*                ── 复制/链接 ──> 项目/.cursor/skills/  (Cursor 项目生效)
└── rules/*.md              ── 转换/链接 ──> 项目/.cursor/rules/*.mdc
```

- `skills/` 是所有技能的唯一源目录
- `rules/` 是所有规则的唯一源目录
- Cursor 项目规则会从 `.md` 统一映射为 `.mdc`

### 命令参考

```powershell
.\sync-skills.ps1
.\sync-skills.ps1 -Register D:\work\my-project
.\sync-skills.ps1 -Target D:\work\my-project
.\sync-skills.ps1 -Target all
.\sync-skills.ps1 -List
```

```bash
bash sync-skills.sh
bash sync-skills.sh --register ~/work/my-project
bash sync-skills.sh --target ~/work/my-project
bash sync-skills.sh --target all
bash sync-skills.sh --list
```

### 注意事项

1. Windows 下如需创建项目级符号链接，通常需要管理员权限。
2. 如果目标项目已有普通目录 `.cursor/skills`，脚本会先备份再处理。
3. 已注册项目保存在根目录 `.sync-targets`。
4. 仓库内不再分别维护 `.cursor/rules`、`.trae/rules`、`.claude/skills`、`.cursor/skills`。
