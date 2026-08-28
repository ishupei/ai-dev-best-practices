# BUG 分析报告：wiki 页面标题与文档主标题不一致

- **日期**：2026-08-28
- **状态**：已修复（脚本层完成；目标页面重推待用户确认后执行）
- **严重程度**：中（不影响功能与内容，影响页面检索、面包屑可读性与文档一致性）

> 修复记录：已按方案 1+3 落地——`publish-md` 未传 `--title` 时页面标题取文档主标题（正文第一个一级标题）；正文主标题在推送/粘贴转换时自动剔除（页面标题即主标题）；基线模板全部标题提升一级（`## `→`# ` 等）；lint 校验模板文档必须有一级主标题开头并豁免主标题的"多余一级章节"判定。

## 问题描述

**重现/现象**：wiki 页面 `http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=236206234`

- Confluence 页面标题（元数据，显示在标签页/面包屑）：`FDA电子签名-接口校验、签署页面改造`
- 页面正文主标题（H1）：`FDA电子签名：功能点4-6基线详设`
- 本地文档 `E:\esign\code\esign6.0\docs\dev\v6.0.18.0-beta.4\FDA电子签名-接口改造\DESIGN-FDA电子签名-功能点4-6.md` 第 1 行主标题：`# FDA电子签名：功能点4-6基线详设`

**当前结果**：页面标题与正文主标题不一致；本地文档 v1.1 版本记录行未上 wiki（wiki 内容停留在 v1.0 后的推送状态，4.1/4.2 表的「改造端」列已同步、v1.1 记录缺失）。

**预期结果**：页面标题与文档主标题一致（`FDA电子签名：功能点4-6基线详设`），本地最新内容同步上 wiki。

## 根因分析

**定位**：`skills/tianyin-wiki/scripts/tianyin_wiki.py` → `cmd_publish_md` → payload 构造：

```python
"title": args.title or page["title"],
```

**根本原因**：`publish-md` 未显式传 `--title` 时，标题固定沿用 Confluence 页面已有标题，**从不读取文档正文的第一个 `# ` 主标题**。该页面最初创建时标题为「FDA电子签名-接口校验、签署页面改造」（早于功能点4-6文档），此后多次推送功能点4-6内容均沿用旧页面标题，导致页面标题（元数据）与正文主标题（内容）长期不一致。模板本身不含 H1（`# 天印详设文档模版` 已从模板移除），主标题由生成时写入正文，两个来源无联动机制，必然存在漂移风险。

**因果链**：页面创建标题 ≠ 后续文档主标题 → publish 默认沿用页面标题 → 每次发布只更新正文 → 页面标题与正文主标题永久不一致。

## 修复方案

### 方案 1（推荐）：publish 未指定 `--title` 时，以文档第一个 H1 作为页面标题

- **修改内容**：`scripts/tianyin_wiki.py`
  - 新增 `extract_main_title(markdown_text) -> str | None`：剔除注释后取第一个 `# xxx` 行（无 H1 返回 None）。
  - `cmd_publish_md`：`title = args.title or extract_main_title(markdown_text) or page["title"]`；dry-run 报告同时展示将使用的标题。
- **修改示例**：
  ```python
  def extract_main_title(markdown_text: str) -> str | None:
      for line in strip_html_comments(markdown_text).split("\n"):
          match = re.match(r"^#\s+(\S.*)$", line.strip())
          if match:
              return match.group(1).strip()
      return None
  ```
- **影响面**：所有 `publish-md` 未传 `--title` 的发布；对标题与主标题一致的页面无影响；对不一致页面会自动修正页面标题（属预期修复）。raw 模式无 H1 的文档行为不变。风险等级：低。
- **验证**：本地单测——有 H1 文档发布时 PUT payload 的 title = H1；无 H1 时沿用页面标题；dry-run 报告展示标题。

### 方案 2：立即修复目标页面（一次性写操作，需用户确认）

- **修改内容**：无代码改动。用修正后的脚本或显式传参重新推送：
  ```powershell
  python .\scripts\tianyin_wiki.py publish-md --title "FDA电子签名：功能点4-6基线详设" --input "E:\esign\code\esign6.0\docs\dev\v6.0.18.0-beta.4\FDA电子签名-接口改造\DESIGN-FDA电子签名-功能点4-6.md" --remote-url "http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=236206234"
  ```
  同步修复页面标题并补齐 v1.1 内容。风险等级：低（写操作，建议先 `--dry-run` 确认目标页）。

### 方案 3（可选）：约定补充

- `SKILL.md` 输出约定注明：文档第一个 `# ` 标题即主标题，应与 wiki 页面标题一致；`publish-md` 未指定 `--title` 时以主标题为准。防止未来生成文档时主标题随意变更。

## 简版说明

- **原因**：发布到 wiki 时，页面标题沿用旧标题，没有跟随文档里的大标题（主标题），导致两者不一致。
- **方案**：发布时自动用文档大标题作为页面标题；当前这一页重新发布一次即可修正标题并补上最新内容。
