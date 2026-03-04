---
description: "self-project-rules (project scope)"
globs: ["**/*.java", "**/pom.xml", "**/*.yml", "**/*.yaml", "**/*.properties"]
alwaysApply: true
---

## 1.1 Coding & Utilities

• **MUST** use constants from `io.github.xtemplus.core.constants.StringPool` for delimiters (e.g. `""`, `" "`, `","`, `";"`, `":"`). **MUST NOT** hardcode single-character literals in new code.
• **MUST** use the Log utility class (`io.github.xtemplus.utils.Log`) for logging. If a string literal appears in 2+ places with clear semantics, **MUST** add it to StringPool and reference it project-wide.

## 1.2 File Organization

• **MUST** place Markdown docs in `docs/`. **MUST** place SQL in `sql/`. **MUST** follow this for all new files.

## 1.3 Project Structure Documentation

• When dealing with long context or file structure comprehension, **MUST** read `.content/project-structure.md`. When files are added, modified, or deleted, **MUST** synchronously update `.content/project-structure.md`.

## 1.4 Design Phase

• Input starts with `#design` → **MUST** invoke `design-phase` skill; **MUST** follow `.cursor/skills/design-phase/SKILL.md` (steps 1–4 and Usage checklist).
• **MUST NOT** implement code for that feature until a complete design document exists in `docs/` (Markdown, per template).

## 1.5 Git Commit

• Input starts with `#commit` → **MUST** invoke `git-commit` skill; **MUST** follow `.cursor/skills/git-commit/SKILL.md` format and constraints.
• **MUST NOT** run any git commands or modify working tree/staging; **MUST** output only the Chinese commit message text.
