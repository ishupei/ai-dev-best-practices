# CLI Reference

主入口：`scripts/tianyin_wiki.py`（相对本 skill 目录，即 SKILL.md 同目录；Windows 可用 `scripts/tianyin_wiki.ps1` 代替）。下方示例中 `.\scripts\tianyin_wiki.py` 的 `.\` 均指本 skill 目录。

调用约束（安全与推送约束遵循 `SKILL.md` 执行边界，以下为 CLI 特有）：

- 未显式提供 `remote-url` 时，只允许本地模板初始化或本地文档更新；只有显式提供时才允许访问或更新远程 wiki。
- 修改本地 Markdown 时，如果用户没有显式指定 `remote-url`，严禁同时更新远程 wiki。
- 远程发布前先执行 `lint-doc` 自查；发布时模板结构校验差异（缺项/多项）仅提示，不阻断推送。
- 远程发布前可用 `check-page` 做只读验证；认证缺失会直接提示补充账号密码。
- 首次使用或配置缺少 `username`/`password` 时，必须先补充账号密码配置、命令行参数或环境变量。
- `publish-md` 自动识别 ````mermaid` 围栏代码块，统一渲染 PNG 后调用附件接口上传，并写入 Confluence 内联附件图片。
- 模板中的 HTML 注释行（`<!-- 非必填：... -->`）为填写指引，发布与粘贴转换时自动剔除，不进入 wiki 正文；代码围栏内的注释不受影响。

默认配置：

- CLI 默认读取用户配置目录 `%USERPROFILE%\.config\tianyin-wiki\config.json`（macOS/Linux 为 `~/.config/tianyin-wiki/config.json`）；该文件为本地个人配置（含凭据），**不随 skill 分发、不提交版本库**，分发物只含 `tianyin-wiki.config.sample.json`。
- 可用环境变量 `CONFLUENCE_CONFIG=<path>` 指向自己的配置文件（支持 `~` 展开），优先于默认路径。
- 配置字段支持：`template`、`remoteUrl`、`baseUrl`、`pageId`、`username`、`password`。
- `template` 为默认模板模式，**仅允许存储 `baseline` 或 `1-n`**；`raw` 是内置默认（不校验格式直推），不允许写入配置，写入 `raw`/`direct` 会报错。未传 `--template` 时所有命令默认读取该字段。
- 参数优先级：命令行显式参数 > 配置文件 > 环境变量；`--template` 未显式指定时取配置 `template` 字段，再缺省 `raw`（`init-template` 需显式指定 `baseline`/`1-n`；`merge-clear` 固定 `baseline`）。
- 凭据也可经环境变量注入：`CONFLUENCE_USERNAME`、`CONFLUENCE_PASSWORD`。
- 配置文件中已提供 `baseUrl` 和 `pageId` 时，`check-page`、`publish-md` 可省略 `--remote-url`。
- 不要在终端、对话或文档中回显认证值。

## Commands

### `init-template`

复制模板到目标文件（自动剔除模板内的指引注释行，输出为纯净文档）：

```powershell
python .\scripts\tianyin_wiki.py init-template --output .\outputs\detail-design.md
```

初始化 1-N 详设：

```powershell
python .\scripts\tianyin_wiki.py init-template --template 1-n --output .\outputs\1-n-detail-design.md
```

`--template` 支持：

- `raw`（别名 `direct`）：默认模式，不校验任何格式直推本地 Markdown；`init-template` 不支持，未显式指定模板时会报错提示。
- `baseline`：基线详设模板，需显式指定。
- `1-n`：1-N 详设模板，来源页面 `pageId=224905569`，需显式指定。
- `default`：生成详设流程的缺省模板，等同 `baseline`；仅在「上下文未指定文档、需生成天印本地 md 再推送」的场景使用。
- 未显式传 `--template` 时的取值顺序见「默认配置」。

### `publish-md`

将 Markdown 转成 Confluence storage HTML 并更新页面：

```powershell
python .\scripts\tianyin_wiki.py publish-md --input .\outputs\detail-design.md --remote-url "http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=123456"
```

1-N 详设的校验、富文本转换和发布均需指定 `--template 1-n`：

```powershell
python .\scripts\tianyin_wiki.py lint-doc --template 1-n --input .\outputs\1-n-detail-design.md
python .\scripts\tianyin_wiki.py prepare-paste-html --template 1-n --input .\outputs\1-n-detail-design.md
python .\scripts\tianyin_wiki.py publish-md --template 1-n --input .\outputs\1-n-detail-design.md --remote-url "http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=123456"
```

使用默认配置：

```powershell
python .\scripts\tianyin_wiki.py publish-md --input .\outputs\detail-design.md
```

直推任意本地 Markdown（默认即 `raw` 模式，无需指定，不校验任何格式、无结构告警）：

```powershell
python .\scripts\tianyin_wiki.py publish-md --input .\outputs\任意文档.md --remote-url "http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=123456"
```

发布前预检（只读：拉取目标页、渲染并构建 storage HTML，**不传附件、不更新页面**，输出 dryRun 报告）：

```powershell
python .\scripts\tianyin_wiki.py publish-md --dry-run --input .\outputs\detail-design.md --remote-url "http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=123456"
```

无论是否 `--dry-run`，实际写入前都会向 stderr 打印目标页与版本变化：`publishing: <标题> (page <id>, version N -> N+1)`，用于确认没有写错页面。

主标题约定：文档正文第一个一级标题（主标题）仅保留在本地 md，推送/粘贴转换时自动剔除，Confluence 页面标题即主标题；未传 `--title` 时页面标题自动取文档主标题，无主标题则沿用页面现有标题。

支持认证参数：

- `--username`
- `--password`

- `--mermaid-scale <有限正数>`，默认 `3`，用于 PNG 渲染。
- `--image-width <px>`，默认自适应：展示宽度 = 原始宽度的一半，减半后仍超过 `500` 则固定为 `500`（`min(原始宽度/2, 500)`）；传固定值则按该宽度展示（写入 `<ac:image ac:width="500">`），传 `0` 不设置显式宽度。

处理顺序：

1. 渲染每个 `mermaid` 代码块（统一渲染为**白底** PNG；默认按源码摘要、格式、PNG 缩放值和背景色缓存到 `~/.cache/tianyin-wiki/mermaid/`，可用环境变量 `TIANYIN_WIKI_CACHE_DIR` 覆盖；参数与源码未变时直接复用缓存图片，不重复调用渲染器）。
2. 拉取页面已有附件清单，同名附件（文件名包含图表源码摘要、格式、PNG 缩放值和背景色）自动跳过上传；若并发发布导致同名上传冲突，重新拉取清单并复用已创建附件。
3. 使用 `<ac:image><ri:attachment ... /></ac:image>` 写入 storage HTML。
4. 更新页面正文；若正文、标题均无变化，跳过页面更新并输出 `noChanges`（不递增版本）。页面 PUT 遇到并发版本冲突时会重读页面并重试一次。渲染临时文件会删除，远程附件不会自动删除（改图后旧附件文件保留在页面附件列表中，正文不再引用）。

代码块默认使用 Emacs 主题（`<ac:parameter ac:name="theme">Emacs</ac:parameter>`），无需显式配置。

附件文件名：`tianyin-mermaid-{摘要}-png-{缩放}-{背景}.png`，`摘要` 为源码 sha256 前 16 位，`缩放` 为 `--mermaid-scale` 值，`背景` 固定白底；本地缓存键同构（省略前缀），参数变化即新文件名。

Mermaid 渲染按 `PATH` 探测 `mmdc`（`npm i -g @mermaid-js/mermaid-cli`）或 `npx`，无需配置。

### `upload-attachment`

只上传一个附件，不更新页面正文。用于验证 Confluence 附件接口：

```powershell
python .\scripts\tianyin_wiki.py upload-attachment --file .\outputs\tianyin-mermaid-example.png --remote-url "http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=123456"
```

上传使用 `POST /rest/api/content/{pageId}/child/attachment`、`multipart/form-data` 和 `X-Atlassian-Token: no-check`。**同名附件会被 Confluence 拒绝（返回 HTTP 400，消息为 Cannot add a new attachment with same file name as an existing attachment），不会作为新版本处理**；`publish-md` 已按附件名去重，仅在上传新增图表时使用本接口。

### 辅助脚本

本地渲染单个 Mermaid 文件：

```powershell
python .\scripts\wiki_diagram.py --input .\outputs\flow.mmd --output .\outputs\flow.png
```

只读检查页面全部附件（自动跟随分页）；可使用 `--filename` 过滤指定附件，`--limit` 设置每页大小：

```powershell
python .\scripts\wiki_attachment_probe.py --remote-url "<wiki-url>" --filename "tianyin-mermaid-example.png"
```

### `lint-doc`

校验本地详设是否仍符合固定模板规则：

```powershell
python .\scripts\tianyin_wiki.py lint-doc --input .\outputs\detail-design.md
```

所有章节均为非必填：章节下标注「未涉及/不涉及」时，自动豁免该章节（含其子章节）的子标题与表头校验，例如接口详情仅填写「未涉及」时不要求请求/响应参数表。章节填写指引以模板内 `<!-- ... -->` 注释为唯一指引源（`references/templates/`），本文档仅为摘要。

模板文档必须以一级标题（主标题）开头，缺少时 lint 报错；主标题不参与「多余一级章节」校验（主标题约定见 `publish-md`）。基线模板章节为一级标题（`# 1.方案背景`），1-N 保持二级（`## 一、`）。

`lint-doc` 未传 `--template` 时取配置文件 `template` 字段（`baseline`/`1-n`）按模板校验；配置文件未设置时才为 `raw` 模式（不校验任何格式，恒输出 `OK`）。按模板校验需显式 `--template baseline|1-n`（或配置文件已设置）。

文档含有 HTML 注释行（模板指引未清理）时报错：`document contains HTML comment lines (template guidance); remove them from the deliverable`。

### `prepare-paste-html`

将符合模板规则的 Markdown 转成适合 Confluence 编辑器粘贴的富文本 HTML：

```powershell
python .\scripts\tianyin_wiki.py prepare-paste-html --input .\outputs\detail-design.md
```

指定输出路径：

```powershell
python .\scripts\tianyin_wiki.py prepare-paste-html --input .\outputs\detail-design.md --output .\outputs\detail-design.paste.html
```

### `doctor`

只做本机环境诊断，不读取远程 Wiki、不读取凭据：

```powershell
python .\scripts\tianyin_wiki.py doctor --input .\outputs\detail-design.md
```

Windows 可优先使用启动器，它会先选择可用 Python 3.9+；未发现时直接要求安装：

```powershell
.\scripts\tianyin_wiki.ps1 doctor --input .\outputs\detail-design.md
```

输出当前 Python 路径、Mermaid 渲染器来源、是否通过 `npx` 回退、自动探测到的 Chrome/Edge 路径，以及可选输入文档中的 Mermaid 图块数量。新机器首次发布前，先用它确认浏览器路径与 Mermaid 渲染器来源（`viaNpx` 是否走 npx）；当输出 `viaNpx: true` 时，`installHint` 会给出全局安装 `mmdc` 的完整命令（含国内镜像与跳过 Chromium 下载），装好后重新运行 `doctor --refresh-runtime` 即可生效。

运行时探测结果会缓存到 `~/.cache/tianyin-wiki/runtime.json`，后续 `publish-md` 优先复用缓存，减少环境探测耗时。安装新工具或调整浏览器路径后，用下面的命令刷新缓存：

```powershell
python .\scripts\tianyin_wiki.py doctor --refresh-runtime --input .\outputs\detail-design.md
```

### `merge-clear`

将结构化澄清结果合并到允许修改的章节：

```powershell
python .\scripts\tianyin_wiki.py merge-clear --input .\outputs\detail-design.md --patch .\outputs\clear-patch.json
```

`merge-clear` 目前只支持基线详设模板；1-N 详设请保持章节结构后手动更新。
`clear-patch.json` 必须是 JSON 对象；允许的键为代码 `scripts/tianyin_wiki.py` 中 `ALLOWED_CLEAR_TARGETS` 定义的基线章节白名单（共 10 项，如 `1.方案背景`、`4.需求功能点`、`11.1 风险点`、`11.2 回归测试`），以该常量为准。

### `check-page`

只读取并校验目标页面：

```powershell
python .\scripts\tianyin_wiki.py check-page --remote-url "http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=123456"
```

使用默认配置：

```powershell
python .\scripts\tianyin_wiki.py check-page
```

### Markdown conversion compatibility

Markdown 渲染基于 CommonMark/GFM AST 解析（`markdown-it-py`），支持 ATX/Setext 标题、`*`/`+`/`-` 无序列表、`1.` 有序列表、`**bold**`/`__bold__`/`*italic*`/`_italic_`/`~~删除线~~`、行内与围栏代码（语言仅在 Confluence 支持枚举内保留，白名单外如 `http`、`json` 省略 `language` 参数降级为无高亮）、引用块（含嵌套）、GFM 表格（对齐/转义竖线/无外侧竖线）、链接（嵌套括号、引用式、尖括号自动链接、邮箱、标题属性、裸 URL）、外链图片、分隔线（`---`/`***`/`___`）、硬换行、HTML 注释与白名单行内 HTML（`span` 样式、`br`、`u`、`sub`、`sup`）、任务列表（降级为字面 `[ ]`）、Mermaid 图。

`prepare-paste-html` 和 `publish-md` 会在访问远程前拒绝以下构造（逐行报错并给出替代写法）：非白名单 raw HTML 标签或属性、`span` 中除 `color` / `background-color`（仅 `#RGB`、`#RRGGBB`、`rgb(r,g,b)`）和 `text-decoration`（仅 `underline`、`line-through`、`none`）外的 CSS、`javascript:` 等不安全链接协议、本地相对路径图片、该 wiki 不支持的补充平面字符（emoji 等 4 字节 UTF-8，保存时返回 HTTP 500）。`br`、`u`、`sub`、`sup` 不接受属性；所有 `on*` 事件属性均被拒绝。使用 `lint-doc` 可在发布前执行同一兼容性检查。

已知平台差异：Confluence 保存时会把 span 的十六进制颜色归一化为 `rgb()` 形式（比较逻辑已兼容）；有序列表的 `start` 属性会被剥离（列表始终从 1 开始）；`<u>`/`<sub>`/`<sup>` 与删除线 span 在编辑器内保留；代码宏 `language` 参数做枚举校验，白名单外（如 `http`、`json`）必须省略，否则整个代码块渲染报错不显示（`InvalidValueException`）。
