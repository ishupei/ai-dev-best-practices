---
name: ai-push
description: "暂存、提交并推送代码到远程仓库。当用户输入 /ai-push 时触发。自动完成 pull → add → commit → push 全流程。"
---

# Git 提交推送助手

此技能用于将当前工作区的变更**一键完成暂存、提交并推送到远程仓库**，自动处理 pull → add → commit → push 全流程。

## Usage

- 当用户输入以 `/ai-push` 开头时，**MUST** 触发此技能。
- Commit message 来源（按优先级）：
  1. 用户在 `/ai-push` 后附带了文本（如 `/ai-push fix: 修复了若干问题`）→ 直接使用该文本作为 commit message。
  2. 当前对话上下文中已有 `/ai-commit` 生成的 commit message → 使用该消息。
  3. 以上均无 → 按照 `/ai-commit` 的规则自动生成 commit message（参考 ai-commit skill 的格式规范）。

## Role & Scope

你扮演一位**熟练的开发者**，负责安全、规范地将代码变更提交并推送到远程仓库。你需要确保推送前拉取最新代码、确认分支正确、处理可能的冲突。

## 工作流程

### Step 1：环境检查

- 执行 `git status` 确认当前分支名称和工作区状态。
- **MUST** 向用户确认当前分支是否为预期推送的目标分支。
- 如果工作区无任何变更（无修改、无新文件），**MUST** 告知用户并终止流程。

### Step 2：拉取最新代码

- 执行 `git pull` 拉取远程最新代码。
- 如果出现合并冲突：
  - **MUST** 立即告知用户冲突文件列表。
  - **MUST** 暂停流程，等待用户解决冲突后再继续。
  - **MUST NOT** 自动解决冲突。

### Step 3：确定 commit message

- 按 Usage 中的优先级规则确定 commit message。
- 如果需要自动生成，**MUST** 遵循以下格式：
  - Subject line：`<type>: <summary>`，标准 type（`feat`/`fix`/`chore`/`docs`/`refactor`/`style`/`test` 等），中文摘要至多 30 字。
  - Body（可选）：使用 `//1.` `//2.` … 编号，最多 5 条，不列文件路径。
- **MUST** 向用户展示最终 commit message 并确认后再执行提交。

### Step 4：暂存与提交

- 执行 `git add` 暂存变更文件。
  - 优先暂存用户本次工作相关的文件，避免意外暂存无关文件（如 `.env`、IDE 配置等）。
  - 如果存在 `.gitignore` 未覆盖的敏感文件，**MUST** 警告用户。
- 执行 `git commit` 提交。

### Step 5：推送

- 执行 `git push` 推送到远程。
- 如果当前分支没有上游追踪分支，使用 `git push -u origin <branch>` 设置。
- 推送完成后输出结果摘要。

### Step 6：完成报告

- 输出推送结果：
  ```
  ✅ 推送完成

  📌 分支：<branch-name>
  📝 Commit：<commit message subject line>
  📊 变更：X 个文件，+Y/-Z 行
  ```

## 示例

**带 commit message 调用：**
```
/ai-push feat: 新增用户登录认证逻辑
```

**不带 message，使用上下文或自动生成：**
```
/ai-push
```

## Checklist

- [ ] 用户输入以 `/ai-push` 开头，已触发本技能
- [ ] 已确认当前分支为预期目标分支
- [ ] 已执行 `git pull` 拉取最新代码，无冲突
- [ ] Commit message 已确定（用户指定 / 上下文 / 自动生成）
- [ ] Commit message 已向用户展示并获得确认
- [ ] 已暂存变更文件，未包含敏感文件
- [ ] 已执行 `git commit` 和 `git push`
- [ ] 已输出完成报告
