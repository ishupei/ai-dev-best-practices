---
name: tianyin-wiki
description: 生成或更新天印基线/1-N 详设 Markdown；仅在用户明确确认后发布至 Confluence。
---

# Tianyin Wiki

入口：`scripts/tianyin_wiki.py`；Windows 优先 `scripts/tianyin_wiki.ps1`。

## 强制快速路由

**任何动作前 MUST 选择且只选择一个路由。** 复用当前会话已确认的输入路径、模板和目标页。信息不足时只追问当前路由必需项；不得用扫描、`doctor` 或读取参考文档代替澄清。

1. **本地生成**：生成/补充/更新本地详设。MUST 确认 `baseline` 或 `1-n`，执行 `init-template` → 填充 → `lint-doc`。只读选定模板。
2. **文档 lint**：校验已有 Markdown。MUST 直接执行 `lint-doc --input <md>`；仅在已指定时使用 `--template`。仅在兼容性报错后读取 CLI 参考。
3. **远程只读**：查看/核对已有 Wiki。MUST 只执行 `check-page`。认证或地址失败后才读取发布配置。
4. **远程发布**：仅当用户**明确确认发布/同步**且已提供目标页或配置时执行。MUST `lint-doc` → `publish-md --dry-run` → `publish-md`；缺少确认时 MUST 停止远程动作并请求确认。
5. **环境修复**：仅处理 Python、Mermaid 或浏览器缺失、异常、缓慢。MUST 先执行 `doctor`；仅在诊断指向环境问题后读取 `references/setup.md`。

多意图时：已确认的发布优先；纯远程查看次之；环境错误次之；纯校验走 lint；其余本地请求走生成。“生成并发布”必须先完成本地生成与 lint；未确认前严禁发布。

## 绝对边界

- 除环境修复外，**严禁**执行 `doctor`；除远程路由外，**严禁**访问 Confluence。
- **严禁**无关工作区/Git 扫描；只有用户明确要求时才执行。
- 远程写入必须同时具备用户明确确认、目标 `remote-url`/配置和 Python 3.9+、Wiki `username/password`；任一缺失即停止。
- **严禁**读取、导出或回显密码、Authorization 或其他凭据。
- 本地 Markdown 是唯一事实源。默认 `raw` 不校验结构；仅明确 `baseline`/`1-n` 时读取模板并校验。

## 延迟读取

- 非常用参数、附件、`merge-clear`、转换兼容性：`references/cli-reference.md`
- 远程发布配置：`references/remote-publish.md`
- 选定模板：`references/templates/`
