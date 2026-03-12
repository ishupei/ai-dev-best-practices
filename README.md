# AI Dev Best Practices

AI 辅助开发技能体系 —— 统一管理 Claude Code / Cursor / Trae 的 Skills 和 Rules，一处维护，多项目同步。

## 项目结构

```
ai-dev-best-practices/
├── .claude/commands/       # Claude Code 命令（/ai-xxx 触发）
│   ├── ai-bug.md           #   BUG 定位与修复方案
│   ├── ai-clear.md         #   需求澄清与完善
│   ├── ai-commit.md        #   Git Commit Message 生成
│   ├── ai-design.md        #   技术设计文档生成
│   ├── ai-do.md            #   任务执行引擎
│   ├── ai-draft.md         #   需求规格说明书初稿
│   ├── ai-plan.md          #   技术方案与总体设计
│   ├── ai-push.md          #   Git 提交推送助手
│   └── ai-task.md          #   开发任务拆解
├── .cursor/
│   ├── skills/             # Cursor 技能（/ai-xxx 触发）
│   │   ├── ai-bug/SKILL.md
│   │   ├── ai-clear/SKILL.md
│   │   ├── ai-commit/SKILL.md
│   │   ├── ai-design/SKILL.md
│   │   ├── ai-do/SKILL.md
│   │   ├── ai-draft/SKILL.md
│   │   ├── ai-plan/SKILL.md
│   │   ├── ai-push/SKILL.md
│   │   └── ai-task/SKILL.md
│   └── rules/              # Cursor 规则（自动应用）
│       ├── global-dev.mdc  #   全局开发规范
│       ├── self-project.mdc#   个人项目规范
│       └── work-project.mdc#   工作项目规范
├── .trae/                  # Trae 配置（rules + skills）
├── sync-skills.ps1         # 同步脚本 (Windows PowerShell)
├── sync-skills.sh          # 同步脚本 (macOS/Linux Bash)
└── README.md
```

## 技能一览

| 命令 | 用途 | 触发方式 |
|------|------|----------|
| `/ai-draft` | 根据需求描述生成 SRS 初稿 | 输入需求描述 |
| `/ai-clear` | 多轮问答澄清需求中的歧义和缺失 | 需求初稿就绪后 |
| `/ai-plan` | 生成技术方案与总体设计 | 需求确认后 |
| `/ai-design` | 生成详细技术设计文档 | 技术方案确认后 |
| `/ai-task` | 将设计拆解为可执行的开发任务 | 设计文档就绪后 |
| `/ai-do` | 逐个执行开发任务并验证 | 任务拆解完成后 |
| `/ai-bug` | BUG 定位、根因分析、修复方案 | 发现 BUG 时 |
| `/ai-commit` | 生成标准化中文 commit message | 代码变更后 |
| `/ai-push` | Git 提交推送 | 准备推送时 |

## 同步工具使用

提供 PowerShell (Windows) 和 Bash (macOS/Linux) 两个版本，功能完全一致。

| 环境 | 脚本 |
|------|------|
| Windows | `sync-skills.ps1` (PowerShell) |
| macOS / Linux | `sync-skills.sh` (Bash) |

### 同步原理

```
ai-dev-best-practices/（中心仓库，唯一维护点）
│
├── .claude/commands/*.md ── 复制 ──> ~/.claude/commands/      (Claude Code 全局生效)
├── .cursor/skills/*      ── 链接 ──> 项目/.cursor/skills/     (Cursor symlink)
└── .cursor/rules/*.mdc   ── 链接 ──> 项目/.cursor/rules/*.mdc (Cursor 逐文件 symlink)
```

- **Claude Code**：复制到 `~/.claude/commands/`，所有项目自动生效
- **Cursor**：通过符号链接指向中心仓库，更新即时生效，无需重复复制
- **项目自有规则优先**：目标项目已有同名 rules 文件（非 symlink）不会被覆盖

### 命令参考

#### Windows (PowerShell - 以管理员身份运行)

```powershell
# 1. 仅同步 Claude Code 全局命令
.\sync-skills.ps1

# 2. 注册项目（记录路径，后续可批量同步）
.\sync-skills.ps1 -Register D:\work\my-project

# 3. 同步到指定项目（Claude Code 全局 + 该项目的 Cursor）
.\sync-skills.ps1 -Target D:\work\my-project

# 4. 同步到所有已注册项目
.\sync-skills.ps1 -Target all

# 5. 查看已注册项目列表
.\sync-skills.ps1 -List

# 6. 查看帮助
.\sync-skills.ps1 -Help
```

#### macOS / Linux (Bash)

```bash
# 1. 仅同步 Claude Code 全局命令
bash sync-skills.sh

# 2. 注册项目
bash sync-skills.sh --register ~/work/my-project

# 3. 同步到指定项目
bash sync-skills.sh --target ~/work/my-project

# 4. 同步到所有已注册项目
bash sync-skills.sh --target all

# 5. 查看已注册项目列表
bash sync-skills.sh --list
```

### 典型工作流

**首次设置新项目：**

```powershell
# Windows: 注册 + 同步一步到位
.\sync-skills.ps1 -Register D:\work\new-project -Target D:\work\new-project
```

```bash
# macOS/Linux
bash sync-skills.sh --register ~/work/new-project --target ~/work/new-project
```

**日常更新（在中心仓库修改技能后）：**

```powershell
# Windows
.\sync-skills.ps1 -Target all
```

```bash
# macOS/Linux
bash sync-skills.sh --target all
```

### 注意事项

1. **Windows 符号链接需要管理员权限**：右键 PowerShell → "以管理员身份运行"，然后执行脚本。仅同步 Claude Code 全局命令时不需要管理员权限
2. **备份机制**：如果目标项目已有 `.cursor/skills` 目录（非 symlink），脚本会自动备份为 `.cursor/skills.bak.{时间戳}`
3. **`.sync-targets` 文件**：已注册项目列表存储在仓库根目录的 `.sync-targets` 文件中，建议加入 `.gitignore`（路径因人而异）
4. **首次执行策略**：如果只需要 Claude Code 全局命令，无需管理员权限直接运行即可；需要同步 Cursor 到其他项目时再用管理员权限
