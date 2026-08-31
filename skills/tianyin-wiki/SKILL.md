---
name: tianyin-wiki
description: 生成/更新天印基线或 1-N 详设 Markdown；也可在用户明确确认时将本地 Markdown 直推 Confluence。
---

# Tianyin Wiki

主入口：`scripts/tianyin_wiki.py`。Windows 优先用 `scripts/tianyin_wiki.ps1` 选择可用 Python。

## 路由

- 已给本地 Markdown 并要求推送/发布/同步 Wiki：走 `publish-md` raw 直推；发布前先 `--dry-run` 预检（只读）。
- 要生成详设：先确认 `baseline` 还是 `1-n`，再 `init-template` → 填充 → `lint-doc`。
- 只读确认远程页：用 `check-page`。
- 新机器或 Mermaid 渲染异常/缓慢：用 `doctor` 诊断；工具路径缓存异常时加 `--refresh-runtime`。

## 常用命令（免查参考文档）

`<wiki-url>` 形如 `http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=<id>`；本机已配置 `baseUrl`/`pageId`/凭据时省略 `--remote-url`。Windows 下用 `.\scripts\tianyin_wiki.ps1` 代替 `python .\scripts\tianyin_wiki.py`。

```powershell
# 发布预检（只读，不传附件不更新页面）
python .\scripts\tianyin_wiki.py publish-md --dry-run --input <md> --remote-url "<wiki-url>"
# 正式发布（raw 默认不校验结构；发布前先 lint-doc）
python .\scripts\tianyin_wiki.py publish-md --input <md> --remote-url "<wiki-url>"
# 只读检查目标页面
python .\scripts\tianyin_wiki.py check-page --remote-url "<wiki-url>"
# 环境诊断（Python/Mermaid/浏览器/图块数量）
python .\scripts\tianyin_wiki.py doctor [--refresh-runtime]
# 结构校验（发布前自查）
python .\scripts\tianyin_wiki.py lint-doc [--template baseline|1-n] --input <md>
```

## 必守

- 远程写入必须有用户明确确认和目标 `remote-url`/配置；本地 md 是唯一事实源。
- 远程操作前必须有 Python 3.9+ 和 Wiki `username/password`；缺失时要求用户补齐，不继续发布。
- 不读取、导出或回显密码、Authorization 头或其他认证凭据。
- 默认 `raw` 不校验结构；只有用户明确基线/1-N 时才读模板并校验。

## 按需读取

- 非常用参数（`--image-width`/`--mermaid-scale`/附件/`merge-clear`）或转换兼容性细节：`references/cli-reference.md`
- 发布与账号配置：`references/remote-publish.md`
- 新机器环境：`references/setup.md`
- 生成模板细节：`references/templates/`（只读选定模板）
