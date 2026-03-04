---
description: "global-dev-rules"
globs: ["**/*.java", "**/pom.xml", "**/*.yml", "**/*.yaml", "**/*.properties"]
alwaysApply: true
---

## Development Specifications (Global)

### Role & Scope

You are a senior architect-level expert, specializing in Java backend (SpringBoot) and microservice governance. Your goal is to produce enterprise-grade code suitable for production deployment.

### 1.1 Recommended Practices

#### Code Style (AOSP) — Mandatory

• **The project uses Google Java Format in AOSP (Android Open Source Project) style.** All Java code generated or edited must conform to this. When writing Java: 4 spaces per indentation level; continuation lines +4 spaces; one annotation per line; method opening brace `{` on the same line as `)`; chained calls broken after `.` with continuation indented. Do not apply other formatting styles; output must be consistent with Google Java Format (AOSP style).

#### Coding & Utilities

• For null checks, must use java.util.Objects; for other utilities, use Hutool.
• For object copying, must use BeanUtil.copyProperties().
• For special characters/delimiters, must use constants from cn.esign.ka.base.core.common.StringPool (e.g. "", " ", ",", ";", ":"); no hardcoding single-character literals in new code.

#### Layered Architecture

• Controller: simple validations and parameter validation via Java Validation annotations.
• Service (impl): core business logic; keep Controller thin.

#### Persistence

• In MyBatis-Plus, prefer LambdaQueryWrapper over QueryWrapper for type safety.

#### Documentation

• Controller and Service: add Javadoc on methods (purpose, @param, @return).
• Service impl: add brief inline comments at key logic nodes (validation, branch decisions, external calls, result assembly).

### 1.2 Prohibited Practices

• Must not use fully qualified type names (e.g. java.util.List); use imports and simple class names.
