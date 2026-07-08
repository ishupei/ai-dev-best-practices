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

## 安全硬约束

- **禁止盲目暂存**：**MUST NOT** 使用无审计的 `git add .` 或 `git add -A` 直接暂存全部变更；必须先列出变更文件并判断是否属于本次提交范围。
- **敏感文件零容忍**：若发现 `.env`、密钥、证书、凭据、token、密码配置、大型二进制或明显不应提交的本地文件，**MUST** 停止流程并提示用户处理，**MUST NOT** 暂存或提交。
- **保护分支确认**：当前分支为 `main`、`master`、`develop`、`release/*`、`hotfix/*` 或团队保护分支时，**MUST** 明确提醒风险，并获得用户二次确认后才可继续。
- **暂存后必须复核**：提交前 **MUST** 执行 `git diff --cached --stat` 和 `git diff --cached --name-only` 复核暂存范围；若暂存内容与本次目标不一致，**MUST** 停止并调整。
- **失败即停止**：`pull`、暂存、提交、推送任一步失败，**MUST** 停止后续步骤并说明失败原因，**MUST NOT** 继续执行下一步。

## 工作流程

### Step 1：环境检查

- 执行 `git status` 确认当前分支名称和工作区状态。
- **MUST** 向用户确认当前分支是否为预期推送的目标分支。
- 如果当前分支是保护分支或疑似长期分支，**MUST** 进行二次确认。
- 如果工作区无任何变更（无修改、无新文件），**MUST** 告知用户并终止流程。
- 执行 `git status --porcelain` 获取机器可读变更清单，区分已暂存、未暂存、未跟踪文件。

### Step 2：变更审计

- 审计所有变更文件，按以下类别输出：
  - **本次相关**：与当前任务/对话/用户指定提交目标一致。
  - **疑似无关**：IDE 配置、临时文件、调试输出、格式化噪音、其他任务改动。
  - **禁止提交**：敏感文件、密钥凭据、大文件、构建产物、依赖目录。
- 若存在疑似无关文件，**MUST** 向用户确认是否纳入本次提交。
- 若存在禁止提交文件，**MUST** 停止流程，提示用户先移除、忽略或拆分处理。

### Step 3：拉取最新代码

- 执行 `git pull` 拉取远程最新代码。
- 如果出现合并冲突：
  - **MUST** 立即告知用户冲突文件列表。
  - **MUST** 暂停流程，等待用户解决冲突后再继续。
  - **MUST NOT** 自动解决冲突。

### Step 4：确定 commit message

- 按 Usage 中的优先级规则确定 commit message。
- 如果需要自动生成，**MUST** 遵循以下格式：
  - Subject line：`<type>: <summary>`，标准 type（`feat`/`fix`/`chore`/`docs`/`refactor`/`style`/`test` 等），中文摘要至多 30 字。
  - Body（可选）：使用 `//1.` `//2.` … 编号，最多 5 条，不列文件路径。
- **MUST** 向用户展示最终 commit message 并确认后再执行提交。

### Step 5：暂存与提交

- 执行 `git add <file...>` 暂存已确认属于本次提交的具体文件。
  - 优先暂存用户本次工作相关的文件，避免意外暂存无关文件。
  - 如果存在 `.gitignore` 未覆盖的敏感文件，**MUST** 停止流程并警告用户。
- 执行 `git diff --cached --stat` 和 `git diff --cached --name-only`，向用户展示暂存范围并确认。
- 若暂存区为空，**MUST** 终止流程。
- 执行 `git commit` 提交。

### Step 6：推送

- 执行 `git push` 推送到远程。
- 如果当前分支没有上游追踪分支，使用 `git push -u origin <branch>` 设置。
- 推送完成后输出结果摘要。

### Step 7：完成报告

- 输出推送结果：
  ```
  ✅ 推送完成

  📌 分支：<branch-name>
  📝 Commit：<commit message subject line>
  📊 变更：X 个文件，+Y/-Z 行
  ```

## 完成自检

- 已确认目标分支；保护分支已二次确认（如适用）。
- 已用 `git status --porcelain` 审计并排除无关/禁止提交文件。
- `git pull` 无冲突；commit message 已确认。
- 已按具体文件暂存，并用 `git diff --cached --stat/name-only` 复核。
- 已执行 `git commit`、`git push` 并输出结果。
