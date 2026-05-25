# AI Dev Best Practices

统一维护 AI 开发技能定义的仓库。当前以 `skills/` 作为唯一源目录，通过同步脚本分发到 Claude Code、Cursor、Trae。

## 当前结构

```text
ai-dev-best-practices/
├── .content/
│   └── project-structure.md
├── skills/
│   ├── ai-bug/
│   ├── ai-clear/
│   ├── ai-commit/
│   ├── ai-design/
│   ├── ai-do/
│   │   ├── SKILL.md
│   │   └── references/
│   ├── ai-draft/
│   ├── ai-plan/
│   ├── ai-push/
│   ├── ai-summary/
│   └── ai-task/
├── sync-skills.bat
├── sync-skills.ps1
├── sync-skills.sh
└── README.md
```

说明：

- `skills/`：唯一权威源目录，每个技能使用目录结构保存，入口文件为 `SKILL.md`。
- `skills/ai-do/references/`：技能附属规范，供 `/ai-do` 执行实现任务时读取。
- `.content/project-structure.md`：仓库结构说明。
- `.sync-targets`：同步脚本运行后按需生成的注册目标清单，不纳入版本管理。

## 技能列表

| 命令 | 作用 |
|------|------|
| `/ai-draft` | 生成需求初稿 |
| `/ai-clear` | 澄清需求歧义并补全约束 |
| `/ai-plan` | 输出技术方案与总体设计 |
| `/ai-design` | 输出详细技术设计 |
| `/ai-task` | 将设计拆成可执行任务 |
| `/ai-do` | 逐任务实现、验证并更新进度 |
| `/ai-bug` | 定位问题、分析根因与影响面 |
| `/ai-commit` | 生成标准化中文 commit message |
| `/ai-push` | 执行提交与推送 |
| `/ai-summary` | 生成或更新上下文摘要 |

## 同步行为

### PowerShell / Windows

`sync-skills.ps1` 会执行以下同步：

- 复制 `skills/*` 到 `~/.claude/skills/`
- 复制 `skills/*` 到 `~/.cursor/skills/`
- 复制 `skills/` 到目标项目的 `.cursor/skills/`
- 复制 `skills/` 到目标项目的 `.trae/skills/`

常用命令：

```powershell
.\sync-skills.ps1
.\sync-skills.ps1 -Register D:\work\my-project
.\sync-skills.ps1 -Target D:\work\my-project
.\sync-skills.ps1 -Target all
.\sync-skills.ps1 -List
```

`sync-skills.bat` 是 PowerShell 脚本的 Windows 包装入口。

### Shell / macOS / Linux

`sync-skills.sh` 会执行以下同步：

- 复制 `skills/*` 到 `~/.claude/skills/`
- 为目标项目创建 `.cursor/skills -> <repo>/skills` 符号链接
- 复制 `skills/` 到目标项目的 `.trae/skills/`

常用命令：

```bash
bash sync-skills.sh
bash sync-skills.sh --register ~/work/my-project
bash sync-skills.sh --target ~/work/my-project
bash sync-skills.sh --target all
bash sync-skills.sh --list
```
