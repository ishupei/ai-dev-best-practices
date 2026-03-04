---
name: git-commit
description: "MUST generate standardized Git commit messages in Chinese. Invoke when user input starts with #commit. MUST only output message text; MUST NOT run git add/commit—user performs commit manually."
---

# Git Commit Message Generator

This skill **MUST** generate standardized Git commit messages in Chinese. Prefer **AI context** (conversation, recent edits) to understand changes; you **MAY** use `git status` / `git diff` only to help. You **MUST NOT** perform commit—the user does that manually.

## Usage

- When user input starts with `#commit`, you **MUST** use this skill to generate a Git commit message in Chinese.
- To understand what changed: **prefer AI context** (conversation history, recent edits, open files). If needed, you **MAY** run **read-only** commands `git status` and `git diff` to inspect changes; do **not** use any other git commands.
- You **MUST** output only the commit message text. You **MUST NOT** run `git add`, `git commit`, or any command that modifies the working tree or staging area—**commit is always performed manually by the user**.

## Message Format

1. **Subject line (first line)**  
   `<type>: <summary>`  
   - **MUST** use standard type: `feat`, `fix`, `chore`, `docs`, `refactor`, `style`, `test`, etc.  
   - **MUST** use one short sentence that accurately describes the change, **at most 30 characters**（字）.  
   - **MUST** follow the subject line with a **blank line** if there is a body.

2. **Body (optional)**  
   - **MUST** use `//1.` `//2.` … for up to **5 bullet points**.  
   - Each point **MUST** be one concise line describing what was done or the key change.  
   - You **MUST NOT** list committed file names or paths.

## Example

```
feat: 新增用户登录认证逻辑

//1. 集成后端登录API接口调用
//2. 添加JWT令牌存储与状态管理
```

## Prohibited Practices

- You **MUST NOT** run `git add`, `git commit`, or any tool/command that modifies the working tree or staging area. **Submitting code is strictly a manual action by the user.**
- You **MUST NOT** list specific file names or paths in the commit message body.
- You **MUST** output only the commit message as plain text; the user will run `git add` and `git commit` themselves.
