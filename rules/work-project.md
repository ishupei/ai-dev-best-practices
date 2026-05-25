---
description: "work-project-rules (project scope)"
globs: ["**/*.java", "**/pom.xml", "**/*.yml", "**/*.yaml", "**/*.properties"]
alwaysApply: true
---

## Coding & Utilities

• **MUST** use constants from `cn.esign.ka.base.core.common.StringPool` for delimiters (e.g. `""`, `" "`, `","`, `";"`, `":"`). **MUST NOT** hardcode single-character literals in new code.

## File Organization

• **MUST** place Markdown docs in `docs/`. **MUST** place SQL in `sql/`. **MUST** follow this for all new files.

## Design Phase

• Input starts with `#design` → **MUST** invoke `design-phase` skill; **MUST** follow `skills/design-phase/SKILL.md` (steps 1–4 and Usage checklist).
• **MUST NOT** implement code for that feature until a complete design document exists in `docs/` (Markdown, per template).

## Git Commit

• Input starts with `#commit` → **MUST** invoke `git-commit` skill; **MUST** follow `skills/git-commit/SKILL.md` format and constraints.
• **MUST NOT** run any git commands or modify working tree/staging; **MUST** output only the Chinese commit message text.
