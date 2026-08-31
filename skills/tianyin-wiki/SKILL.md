---
name: tianyin-wiki
description: 生成或更新天印基线/1-N 详设 Markdown；仅在用户明确确认后发布至 Confluence。
---

# Tianyin Wiki

入口：本 SKILL.md 同目录 `scripts/tianyin_wiki.py`，Windows 用 `scripts/tianyin_wiki.ps1` 代替（自动选择 Python 3.9+）。**所有命令均为该脚本的 CLI 子命令，不在系统 PATH 中查找**；执行形式 `python <本文件所在目录>/scripts/tianyin_wiki.py <command> [args]`。参考文档 `.\scripts\tianyin_wiki.py` 的 `.\` 均指本 skill 目录。

## 强制快速路由

**任何动作前 MUST 选择且只选择一个路由。** 复用会话已确认的输入路径、模板、目标页；信息不足只追问当前路由必需项，不扫描、不跑 `doctor`、不读参考文档代替澄清。

1. **本地生成**：生成/补充/更新本地详设。MUST 确认 `baseline` 或 `1-n`，`init-template` → 填充 → `lint-doc`；只读选定模板。
2. **文档 lint**：校验已有 Markdown。MUST 直接执行 `lint-doc --input <md>`，校验语义见绝对边界；仅兼容性报错后读 CLI 参考。
3. **远程只读**：查看/核对已有 Wiki。MUST 只执行 `check-page`；认证或地址失败后才读发布配置。
4. **远程发布**：仅当用户**明确确认发布/同步**且已提供目标页或配置时执行。MUST `lint-doc` → `publish-md --dry-run` → `publish-md`；lint-doc exit 1 不阻断发布；缺确认时 MUST 停止并请求确认。
5. **环境修复**：仅处理 Python/Mermaid/浏览器缺失或异常。MUST 先执行 `doctor`；仅诊断指向环境问题后读 `references/setup.md`。

多意图优先级：已确认发布 > 远程只读 > 环境修复 > 文档 lint > 本地生成；"生成并发布"必须先完成生成与 lint，未确认前严禁发布。`prepare-paste-html`/`merge-clear`/`upload-attachment` 仅在用户明确请求时执行，参数见 CLI 参考。

## 绝对边界

- 除环境修复外严禁 `doctor`；除远程路由外严禁访问 Confluence。
- 严禁无关工作区/Git 扫描，除非用户明确要求。
- 远程写入须同时具备：用户明确确认、目标 `remote-url`/配置、Python 3.9+、Wiki `username`/`password`；任一缺失即停止。
- 严禁读取、导出或回显密码、Authorization 或其他凭据。
- 本地 Markdown 是唯一事实源。默认 `raw` 不校验结构；配置文件 `template` 为 `baseline`/`1-n` 时按其校验（`lint-doc` 结构缺失 exit 1，发布仅提示）；raw 直推可显式 `--template raw` 关闭。

## 延迟读取

- 非常用参数、附件、`merge-clear`、转换兼容性：`references/cli-reference.md`
- 远程发布配置：`references/remote-publish.md`
- 选定模板：`references/templates/`
