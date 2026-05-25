---
name: ai-commit
description: "分析当前变更，生成标准化中文 Git commit message。当用户输入 /ai-commit 时触发。仅输出消息文本，不执行任何 git 命令。"
---

# Git Commit Message 生成器

此技能用于根据当前代码变更，生成一条**标准化的中文 Git commit message**。优先使用 AI 上下文（对话历史、最近编辑）来理解变更内容；如有需要，可辅助使用 `git status` / `git diff` 查看。

## Usage

- 当用户输入以 `/ai-commit` 开头时，**MUST** 触发此技能。
- 你 **MUST** 仅输出 commit message 纯文本。
- 你 **MUST NOT** 执行 `git add`、`git commit` 或任何修改工作区/暂存区的命令——**提交始终由用户手动完成**。

## Role & Scope

你扮演一位**经验丰富的开发者**，擅长从代码变更中提炼核心意图，用简洁准确的中文撰写 commit message。你的职责仅限于生成 commit message 文本，**MUST NOT** 执行任何 git 写操作。

## 工作流程

### Step 1：理解变更内容

- **优先**使用 AI 上下文（对话历史、最近编辑、打开的文件）来理解本次变更。
- 如需补充信息，**MAY** 执行只读命令 `git status` 和 `git diff` 查看变更详情。
- **MUST NOT** 使用其他 git 命令。

### Step 2：撰写 commit message

按照以下格式生成：

1. **Subject line（第一行）**
   `<type>: <summary>`
   - **MUST** 使用标准 type：`feat`、`fix`、`chore`、`docs`、`refactor`、`style`、`test` 等。
   - **MUST** 用一句简短中文准确描述变更，**至多 30 字**。
   - 如有 body，subject line 后 **MUST** 跟一个空行。

2. **Body（可选）**
   - **MUST** 使用 `//1.` `//2.` … 编号，最多 **5 条**。
   - 每条 **MUST** 用一行简洁描述所做的事或关键变更。
   - **MUST NOT** 列出具体文件名或路径。

### Step 3：输出

- 直接输出 commit message 纯文本，不加任何额外说明。

## 示例

```
feat: 新增用户登录认证逻辑

//1. 集成后端登录API接口调用
//2. 添加JWT令牌存储与状态管理
```

## Checklist

- [ ] 用户输入以 `/ai-commit` 开头，已触发本技能
- [ ] 已通过 AI 上下文或 git diff 理解变更内容
- [ ] Subject line 符合 `<type>: <summary>` 格式，至多 30 字
- [ ] Body（如有）使用 `//1.` 编号，最多 5 条，无文件路径
- [ ] 仅输出 commit message 纯文本，未执行任何 git 写操作
