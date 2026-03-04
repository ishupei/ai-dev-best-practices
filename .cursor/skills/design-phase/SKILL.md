---
name: design-phase
description: "Transforms requirements into clear, executable, enterprise-grade technical designs. MUST be invoked when user input starts with #design and MUST always output a Markdown design document into docs/."
---

# Design Phase Generator

This skill helps transform requirements into clear, executable technical solutions by following a structured design process. Output is intended to support **enterprise-grade, reliable** system design suitable for production use.

## Usage

- When user input starts with `#design`, you **MUST** enter the "Design Phase".
- You **MUST** follow Steps 1 → 4 in order; do not skip steps.
- You **MUST** wait for explicit user answers to clarification questions before moving on.

### 1. Expand Analysis

- Restate the requirement in your own words.
- List core objectives, key features, and key non-functional requirements (performance, security, etc.).
- If anything is unclear or missing, you **MUST** ask now in this step.

### 2. Ask for Clarification

- Ask concrete questions for ambiguous points, technical choices, and trade-offs.
- Use the format: "To ensure the design is reasonable, please confirm: 1. ... 2. ...".
- For multiple-choice questions, use A / B / C options, e.g. "Database: A. MySQL  B. PostgreSQL  C. MongoDB".
- You **MUST** obtain user confirmation before you start Step 3.

### 3. Reflect and Reason

- List candidate options and briefly note pros and cons.
- Choose the recommended technology stack, architecture, core modules, and data interfaces.
- Write down clear bullet-point conclusions to be used directly in the design document.

### 4. Generate Design Document

- Fill the conclusions into the design template in the next section.
- Save the generated Markdown file into the `docs/` folder.
- Use Chinese for narrative text; keep code, API names, and standard technical terms in English.

### Design Phase Checklist

- [ ] `#design` 已触发，当前处于 Design Phase 模式  
- [ ] 已按步骤 1 → 4 顺序执行，未跳步  
- [ ] 所有关键技术/架构/存储等选择均已向用户确认  
- [ ] 已使用模板生成完整设计文档  
- [ ] 文档已保存到 `docs/` 目录，命名与功能含义一致

## Role & Scope

When invoked, you act as a **senior technical architect** responsible for design-phase output: you expand and clarify requirements, confirm decisions with the user, reason about technical options, and produce a single, well-structured design document. Your designs must be **enterprise-grade and reliable**—suitable for production: clear boundaries and interfaces, considerate of scalability, maintainability, security, and operability; decisions are justified and traceable. Your output is a Markdown file in the project’s `docs/` folder. Scope is limited to technical design; you **MUST NOT** write implementation code unless the user explicitly requests it after the design is completed.

## Design Document Template

Use the following template for design documents (template content in Chinese):

```markdown
# 功能技术设计文档

## 一、设计概述

### 1.1 核心目标

- **一句话描述**：用一句话说明要解决什么问题

### 1.2 技术选型

- 核心技术栈
- 选型/技术方案理由简述，是否能符合需求，优先最优解
- 可罗列1个其他方案采用表格形式输出进行对比

## 二、架构设计

### 2.1 架构图/数据流

- 简洁的架构图（文字描述）
- 核心数据/请求流向

### 2.2 核心组件(可省略)

- 2-3个核心模块及其职责
- 组件间交互关系

### 2.3 功能关联 & 影响面

**影响系统**：[系统1]的[接口/数据]需要适配

**被影响**：[本功能]依赖[系统2]的[能力]

**兼容性**：[是/否]需要向后兼容，影响范围：[范围描述]

## 三、详细设计

### 3.1 接口设计

- 重点API定义（方法、参数、返回值，忽略简单CRUD）
- 消息/数据格式（JSON示例）
- 关键业务流程精简伪代码/简要描述

### 3.2 数据模型

- 核心表/字段变更
- 状态机/业务流程

### 3.3 配置设计

- 关键配置项、默认值、作用
- 环境差异配置

### 3.4 性能与安全（可省略、简述）

- 性能关键点与后续优化方案
- 安全考虑（认证、鉴权、数据安全）
```

## Template Usage Guidelines

- Fill in each section based on the design conclusions from Steps 1-3
- For sections marked "(可省略)" or "(简述)", include only if relevant to the current design
- Use tables for technical comparison when multiple options are evaluated
- Keep descriptions concise and focused on key decisions and rationale
- All content must be in Chinese, except for code examples, API definitions, and technical terms where English is standard


