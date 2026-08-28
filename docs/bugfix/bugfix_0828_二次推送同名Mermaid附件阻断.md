# BUG 分析报告：二次推送时被 Wiki 同名 Mermaid 附件限制阻断，页面未更新

- **日期**：2026-08-28
- **状态**：**已实施并实测通过**（代码已落地工程技能 `skills/tianyin-wiki`，未提交 git）
- **严重程度**：高（含图表文档二次推送必现失败；失败后页面停留在旧版本，用户可能误以为已发布）
- **涉及技能**：工程中心仓库 `skills/tianyin-wiki`（`E:\self\project\ai-dev-best-practices\skills\tianyin-wiki`），**修改目标以工程为准，未改动用户目录 `~/.codex/skills/tianyin-wiki` 的副本**

---

## 一、问题描述

### 重现步骤

1. 首次推送含 ` ```mermaid ` 代码块的 Markdown 到 Confluence：本地渲染 PNG（`tianyin-mermaid-{digest}.png`）→ 上传附件 → 更新页面正文，**成功**。
2. 本地修改文档正文（图表未变或仅部分变化）后，再次执行 `publish-md` 推送同一页面。
3. 推送被阻断，报「推送被 Wiki 的同名 Mermaid 附件限制阻断，页面尚未更新」。

### 当前结果

- 二次推送整体失败：所有附件上传循环中的同名附件 POST 被 Confluence 拒绝，脚本抛出异常并中止。
- 页面 **PUT 未执行**，Wiki 页面停留在旧版本；`mermaidAttachments` 计数、正文更新全部未发生。

### 预期结果

- 二次推送应复用页面上已存在的同名 Mermaid 附件（文件名即内容摘要，同名 = 同内容），只上传新增/变更的图表，正常更新正文。
- 未变更的图表不应重复渲染、重复上传；若正文与附件均无变化，应识别为无操作（no-op），不产生无意义的版本递增。

---

## 二、根因分析

### 定位（工程版 `scripts/tianyin_wiki.py`）

| 位置 | 方法/语句 | 说明 |
|---|---|---|
| `tianyin_wiki.py:1057-1062` | `cmd_publish_md` 附件上传循环 | 无条件对**每个**渲染出的图表调用 `upload_attachment`，仅按「本次渲染结果」去重 |
| `tianyin_wiki.py:476-485` | `upload_attachment` | POST `/rest/api/content/{pageId}/child/attachment`（multipart） |
| `tianyin_wiki.py:376-399` | `request_multipart_file` | 实际发送请求；失败抛 `RuntimeError` |
| `tianyin_wiki.py:578/585/616` | `render_mermaid_diagrams` | 附件文件名 = `tianyin-mermaid-{sha256(图表源码)[:16]}.{format}`，**内容摘要即文件名** |
| `tianyin_wiki.py:1073` | `cmd_publish_md` 异常兜底 | 任一上传失败 → `error(...)` 整体中止，页面 PUT（1072 行）不会执行 |
| `references/cli-reference.md:124` | 文档描述 | 错误声称「同名附件由 Confluence 作为新版本处理」 |

### 根本原因

1. **发布脚本不感知页面已有附件**：`cmd_publish_md` 每次发布都把本地渲染出的全部 Mermaid 附件重新 POST 上传一遍，从不查询页面当前已有哪些附件。
2. **文件名 = 内容摘要**：同一图表二次推送时摘要相同 → 文件名相同 → 必然命中「同名附件已存在」。
3. **Confluence Server/DC 语义**：`POST /child/attachment` 是「新建」语义，同名文件不覆盖而是直接拒绝。**实测（pageId=236206234）：HTTP 400，消息 `Cannot add a new attachment with same file name as an existing attachment: tianyin-mermaid-ef44adf787cc2f26.png`**（初版报告按平台通用知识假设为 409，实测为 400，已更正）。只有先取到附件 ID 再 `PUT /child/attachment/{id}/data` 才是「更新」语义。脚本没有跳过逻辑，也没有走更新路径。
4. **失败即整体中止**：上传循环在页面 PUT 之前，任何同名附件报错都会中断整个推送，正文更新落空，且错误信息不含「页面未更新」的明确提示。

### 因果链

二次推送同一文档 → 图表源码未变 → 摘要文件名相同 → `POST /child/attachment` 上传同名附件 → Confluence 返回 HTTP 400 → 异常被捕获 → 推送中止 → 页面 PUT 未执行 → 页面停留在旧版本（即「页面尚未更新」）。

### 附带效率问题（「推送效率」部分）

1. **重复渲染**：每次推送都对全部图表重新执行 mmdc/puppeteer 渲染（每张图数秒起），未变更图表白渲一遍。
2. **重复上传**：同名附件重复 POST（即本 BUG 的直接失败点）。
3. **无操作也发版**：正文与附件均未变化时仍 PUT 递增页面版本。
4. **附件列表未分页**：`~/.codex` 副本中已补的 `fetch_attachment_titles` 用单次 `?limit=1000`，个别实例会截断/钳制 limit；`wiki_attachment_probe.py` 未传 limit（默认 25），附件多时会漏列。

> 注：用户目录 `~/.codex/skills/tianyin-wiki` 在旧会话中补过「同名附件跳过上传」的最小修复（单次 `?limit=1000`，无分页、无缓存、无 no-op）；**工程中心仓库 `skills/tianyin-wiki` 已按本报告方案 A+B+C 落地并实测通过（2026-08-28）**，覆盖其全部能力且更稳健；用户目录副本按用户要求未同步。

---

## 三、修复方案（按推荐优先级排序）

### 方案 A：同名附件跳过上传（先查后传）— 必做，解决阻断

- **修改内容**：`scripts/tianyin_wiki.py`
  1. 新增 `fetch_attachment_titles(config)`：GET `/rest/api/content/{pageId}/child/attachment`，**分页拉全**（`limit=200` + 跟随 `_links.next`，容错：无 next 即止），返回 `set[str]`（附件 title）。
  2. `cmd_publish_md` 在 dry-run 判断之后、上传循环之前调用一次；循环改为：文件名已在页面 → 跳过上传；不在 → 上传并加入已见集合。
- **代码示意**：

```python
def fetch_attachment_titles(config: RuntimeConfig) -> set[str]:
    base = f"{config.base_url.rstrip('/')}/rest/api/content/{config.page_id}/child/attachment"
    titles: set[str] = set()
    url: str | None = f"{base}?limit=200"
    while url:
        response = request_json("GET", url, config.headers)
        results = response.get("results")
        if not isinstance(results, list):
            raise RuntimeError("attachment list returned an invalid response")
        titles.update(
            str(a["title"]) for a in results
            if isinstance(a, dict) and a.get("title")
        )
        url = (response.get("_links") or {}).get("next")
        if url and not url.startswith("http"):
            url = f"{config.base_url.rstrip('/')}{url}"
    return titles
```

```python
existing_attachment_titles = fetch_attachment_titles(config)
uploaded_filenames: set[str] = set()
for diagram in diagrams:
    filename = diagram.attachment_filename
    if filename in existing_attachment_titles or filename in uploaded_filenames:
        continue
    upload_attachment(config, diagram.image_path)
    uploaded_filenames.add(filename)
```

- **正确性依据**：附件文件名 = `tianyin-mermaid-{摘要}-png-{缩放}-{背景}.png`（摘要 = 图表源码 sha256[:16]），同名即同内容同渲染参数，跳过上传等价于「已存在且一致」，无需再比对二进制。
- **影响面**：仅 `publish-md` 上传环节；首推行为不变（页面无附件 → 全部上传）；`upload-attachment` 独立命令不受影响。
- **风险等级**：低。
- **推荐理由**：直接消除同名附件 400 阻断（实测），并补上分页稳健性。

### 方案 B：本地渲染缓存，未变更图表跳过 mmdc 重渲染 — 已实施（PNG-only 重构后口径）

- **修改内容**：`scripts/tianyin_wiki.py`
  1. 新增持久缓存目录：`~/.cache/tianyin-wiki/mermaid/`（与既有 `~/.config/tianyin-wiki` 风格一致；可被环境变量 `TIANYIN_WIKI_CACHE_DIR` 覆盖）。
  2. `render_mermaid_diagrams` 增加缓存参数：**最终实现**——附件名/缓存键规范化同构：`tianyin-mermaid-{摘要}-png-{缩放}-{背景}.png`（缓存键省略前缀），摘要、格式、缩放、背景色全部入名，任一渲染参数变化即生成新附件并上传；命中且 PNG 头校验通过 → 直接复用；未命中 → mmdc 渲染 + `png_dimensions` 校验 + 临时文件 `os.replace` 原子写入；坏缓存自愈（删除后按未命中重渲染）。
- **代码示意（与最终实现一致）**：

```python
cache_dir = Path(os.environ.get("TIANYIN_WIKI_CACHE_DIR", Path.home() / ".cache" / "tianyin-wiki" / "mermaid"))
scale_key = f"{raster_scale:g}"
render_suffix = f"png-{scale_key}-{MERMAID_BACKGROUND}"
image_path = output_dir / f"tianyin-mermaid-{digest}-{render_suffix}.png"
cache_path = cache_dir / f"{digest}-{render_suffix}.png"
# 命中：png_dimensions 校验 PNG 头，坏缓存 unlink 后按未命中重渲染
if cache_hit:
    shutil.copyfile(cache_path, image_path)
else:
    ...  # mmdc 渲染 + png_dimensions 校验
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_cache = cache_path.with_suffix(cache_path.suffix + ".tmp")
    shutil.copyfile(image_path, temp_cache)
    os.replace(temp_cache, cache_path)
```

- **影响面**：仅影响渲染阶段本地行为；`wiki_diagram.py` 复用 `render_mermaid_diagrams`，已同步改为 PNG-only 三参调用，一并受益。
- **风险等级**：低（键含摘要+缩放，内容一致性有保证；本地缓存可随时删除重建）。
- **推荐理由**：二次推送时未变更图表直接从秒级/十秒级渲染降为 0；文档更新越频繁收益越大。

### 手动修改图表后的自动识别（关键闭环，方案 A/B 交叉说明）

- 用户改动 `mermaid` 源码 → sha256 摘要变化 → 渲染缓存键变化（方案 B 缓存 miss）→ 自动重新 mmdc 渲染；未改动的图仍命中缓存跳过渲染，互不干扰。
- 新摘要 → 新附件名 → 不在页面已有附件清单中（方案 A）→ 自动上传新图；storage HTML 引用新文件名，页面正文随之替换为最新图。
- **结论：手动改图自动触发重渲染+新上传，无需任何人工干预或额外识别逻辑**；「跳过」仅对内容相同的旧图生效，不存在误跳过。
- 遗留：旧附件文件保留在页面附件列表中（既有文档已注明「远程附件不会自动删除」），不影响正确性与推送效率；如需清理，可后续增加可选 `--prune-attachments` 删除页面中未被正文引用的 `tianyin-mermaid-*` 附件（破坏性操作，默认不执行）。

### 方案 C：无变化检测，跳过空 PUT — 推荐，避免无效版本递增

- **修改内容**：`scripts/tianyin_wiki.py` `cmd_publish_md`
  - `fetch_page` 已 `expand=body.storage`，可直接取 `page["body"]["storage"]["value"]`。
  - 若「本次零上传 **且** 标题未变 **且** storage 归一化后一致」→ 输出 `noChanges` 并返回 0，不 PUT。
- **实测发现（必须归一化，已落地）**：Confluence 返回的 storage 与提交值存在两类序列化差异——非 ASCII 标点转命名实体（`“` → `&ldquo;`）、结构化宏被注入服务端生成的 `ac:macro-id` / `ac:schema-version` 属性；直接字符串比较永远不等（实测 19517 vs 19184 字符）。用 `html.unescape` 解实体 + 正则剥离注入属性后比较**完全相等**。标题相等判断为 ai-check 补正项，避免用户显式 `--title` 变更被误判为无变化。
- **代码示意（已实现）**：

```python
def normalize_storage_for_compare(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r'\s*ac:macro-id=["\'][^"\']*["\']', "", value)
    value = re.sub(r'\s*ac:schema-version=["\'][^"\']*["\']', "", value)
    return value

# cmd_publish_md 内：
if (
    not uploaded_filenames
    and title == page.get("title")
    and normalize_storage_for_compare(storage_html) == normalize_storage_for_compare(current_storage)
):
    # 输出 {"noChanges": true, ...}，不 PUT
```

- **影响面**：仅对「归一化后全等」场景生效；不等则走原 PUT 路径，行为不变。误判面仅限实体等价（如代码块 `&` 与 `&amp;` 互改），此类改动页面显示完全相同，可接受。
- **风险等级**：低。
- **推荐理由**：消除无操作推送的无效版本递增；实测已触发（见验证记录）。

### 方案 D：文档与探测脚本联动修正 — 必做（文档），可选（脚本）

- `references/cli-reference.md`：
  - 修正第 124 行错误表述「同名附件由 Confluence 作为新版本处理」→ 改为「同名附件会被 Confluence 拒绝（实测 HTTP 400）；`publish-md` 会复用页面已有同名附件（文件名即内容摘要+缩放），仅上传新增/变更的图表」。
  - 第 101-104 行发布流程补一句：二次推送时已存在附件跳过上传、未变更图表命中本地渲染缓存。
- `scripts/wiki_attachment_probe.py`：加 `--limit`（默认 200）并跟随分页，避免漏列。
- `SKILL.md`：可在「最小流程」的发布步骤补一句「二次推送自动复用同名附件，不重复上传」。

### 不推荐方案

- **改为「PUT 更新已有附件」**（取附件 ID 后 `PUT /child/attachment/{id}/data`）：能解决同名阻断（HTTP 400），但每次仍全量重传所有图表，且需额外一次附件详情请求；在「文件名=内容摘要」的设计下，跳过上传与更新等效，PUT 方案徒增请求与复杂度。
- **附件名加时间戳/随机后缀**：会绕过同名限制，但每次推送都产生新附件，页面残留孤儿附件，且与内容摘要设计相悖。

---

## 四、影响面与风险总评

| 维度 | 结论 |
|---|---|
| 改动文件 | `skills/tianyin-wiki/scripts/tianyin_wiki.py`（A/B/C）、`references/cli-reference.md`（D）、`scripts/wiki_attachment_probe.py`（D，可选）、`SKILL.md`（D，一句话） |
| 数据迁移 | 旧命名页面首次升级会新增带渲染参数的附件并切换正文引用；旧附件保留，后续可按需手动清理。 |
| 兼容性 | 首推行为不变；旧命名页面完成一次性附件迁移后，后续推送自动去重；缓存目录为新增本地目录，无冲突 |
| 联动修改 | 工程为技能中心仓库，落地后按 `sync-skills.ps1` 分发到各端（Claude/Cursor 等）；`~/.codex` 副本如保留可后续覆盖 |
| 风险等级 | A/C/D 低；B 低（缓存键含 PNG 缩放值与背景色）；并发同名附件和页面版本冲突均有一次恢复机制；整体低 |

**参数兼容**：附件名与缓存键规范化同构——`tianyin-mermaid-{摘要}-png-{缩放}-{背景}.png`（缓存键省略 `tianyin-mermaid-` 前缀），包含图表源码摘要、格式、PNG 缩放值和背景色（统一白底）；调整缩放或背景等任一渲染参数都会生成新附件并上传，不会复用旧参数图片。并发发布发生同名附件冲突时，脚本会重查附件清单；页面版本冲突时会重读页面并重试一次。

---

## 五、实测验证记录（2026-08-28，pageId=236206234，DESIGN-FDA电子签名-功能点4-6.md）

| # | 步骤 | 结果 |
|---|---|---|
| 1 | 只读检查页面与附件 | 页面「FDA电子签名：功能点4-6基线详设」v5；已有附件 `tianyin-mermaid-ef44adf787cc2f26.png`（v1）；本地摘要预测与之一致 → 同名必现 |
| 2 | **复现（修复前脚本）** | `HTTP 400 Cannot add a new attachment with same file name as an existing attachment: tianyin-mermaid-ef44adf787cc2f26.png`，退出码 1；复核页面仍为 v5（PUT 未执行）→ 根因证实 |
| 3 | 修复后二次推送 | `uploadedAttachments: 0`（同名跳过），页面 v5→v6 成功更新 |
| 4 | 修复后再次推送（旧精确比较口径） | v6→v7（未触发 no-op，暴露实体/宏属性序列化差异） |
| 5 | 修复后第三次推送（归一化口径） | `noChanges: true`，版本保持 7，无无效 PUT |
| 6 | 附件状态复核 | 全程 `tianyin-mermaid-ef44adf787cc2f26.png` 保持 version 1，从未重复上传 |
| 7 | 改图自动识别（本地，不发布） | 修改节点标签后摘要 `ef44adf787cc2f26` → `2bba415f7146139e`，缓存 miss 自动重渲染，新缓存文件生成 |
| 8 | 渲染缓存 | `~/.cache/tianyin-wiki/mermaid/` 键格式 `{摘要}-png-{缩放值}-{背景}`，命中直接复用、跳过 mmdc；坏缓存自愈（删除后重渲染） |
| 9 | **PNG-only 重构后推送（旧命名页面过渡）** | 附件名改为 `tianyin-mermaid-{摘要}-png-{缩放值}.png`：旧命名页面过渡推送上传新附件（`uploadedAttachments: 1`），页面 v7→v8 成功，无 400；旧附件 `tianyin-mermaid-ef44adf787cc2f26.png` 保留在附件列表成为孤儿（实测 2 个附件） |
| 10 | 重构后再次推送 | `noChanges: true`，版本保持 8，无无效 PUT；新命名附件未重复上传（probe 复核） |
| 11 | **文件名规范化（摘要-格式-缩放-背景）** | 附件名 `tianyin-mermaid-{摘要}-png-3-white.png` 真实推送：上传白底新附件（`uploadedAttachments: 1`），页面 v8→v9 图片更新为白底；再推 `noChanges` 版本保持 9；旧附件残留（id 236206313/236206270）按「不考虑历史文件」约定不做迁移清理 |

## 六、验收用例（/ai-task、/ai-do 可据此拆分）

| 场景 | 操作 | 预期 |
|---|---|---|
| 首次推送 | 目标页无附件 | 上传全部图表，页面更新 |
| 二次推送（无改动） | 相同 md 再推 | 附件跳过（uploaded=0），页面版本不变（noChanges） |
| 改文 | 修改正文文字 | 附件跳过，页面更新（版本+1） |
| 改图 | 修改 mermaid 源码 | 新摘要 → 缓存 miss → 重渲染 → 新附件上传，页面更新 |
| 改渲染参数 | `--mermaid-scale` | 缓存键变化重新渲染，附件名变化并上传新 PNG，页面更新为新图片引用 |
| 旧命名页面过渡 | 重构前已发布页面再次推送 | 上传一次新命名附件（旧附件成为孤儿保留在附件列表，正文不再引用）；此后推送正常；如需清理可手动删除孤儿附件 |
| 并发同名推送 | 两个进程同时推送同一新图 | 后发进程遇到同名 400 后重查附件并继续；页面 409 时重读页面并重试一次 |
| 标题变更 | `--title` 与页面现有标题不同 | 即使正文未变也执行 PUT 更新标题 |

---

## 七、简版说明

**原因**：第二次推送同一文档时，图表转换成的图片文件名没变，而发布脚本不会识别「页面上已有同名图片」，照旧重复上传，被 Wiki 拦截，导致整篇文档更新失败，页面停在旧版本。

**方案**：发布前先查页面已有图片清单，同名图片自动跳过上传，只传新增或改动的图；未改动的图不再重复本地渲染，内容完全没变化时不再空更新版本。
