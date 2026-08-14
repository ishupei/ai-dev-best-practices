# CLI Reference

主入口：`scripts/tianyin_wiki.py`

调用约束（安全与推送约束遵循 `SKILL.md` 执行边界，以下为 CLI 特有）：

- 未显式提供 `remote-url` 时，只允许本地模板初始化或本地文档更新；只有显式提供时才允许访问或更新远程 wiki。
- 修改本地 Markdown 时，如果用户没有显式指定 `remote-url`，严禁同时更新远程 wiki。
- 远程发布前建议先执行 `lint-doc` 自查；发布时模板结构校验差异（缺项/多项）仅提示，不阻断推送。
- REST 发布失败时先执行 `diagnose-auth` 定位认证/网关问题；不要直接判定为账号密码错误。
- ZeroTrust 扫码登录与浏览器兜底约束见 `remote-publish.md`。
- `publish-md` 自动识别 ````mermaid` 围栏代码块，默认渲染 PNG 后调用附件接口上传，并写入 Confluence 内联附件图片；可显式指定 SVG。

默认配置：

- CLI 默认读取用户配置目录 `%USERPROFILE%\.config\tianyin-wiki\config.json`（macOS/Linux 为 `~/.config/tianyin-wiki/config.json`）；该文件为本地个人配置（含凭据），**不随 skill 分发、不提交版本库**，分发物只含 `tianyin-wiki.config.sample.json`。
- 旧版本曾把个人配置放在 `%USERPROFILE%\.tianyin-wiki\config.json` 或 `scripts\tianyin-wiki.config.json`（skill 目录内）；发现这些历史文件时会读取并提示迁移到用户配置目录，请迁移后删除。
- 可用环境变量 `CONFLUENCE_CONFIG=<path>` 指向自己的配置文件（支持 `~` 展开），优先于默认路径。
- 配置字段支持：`remoteUrl`、`baseUrl`、`pageId`、`authType`、`username`、`password`、`token`。
- 参数优先级：命令行显式参数 > 配置文件 > 环境变量。
- 凭据也可经环境变量注入：`CONFLUENCE_USERNAME`、`CONFLUENCE_PASSWORD`、`CONFLUENCE_TOKEN`、`CONFLUENCE_AUTH_TYPE`。
- 配置文件中已提供 `baseUrl` 和 `pageId` 时，`check-page`、`publish-md` 可省略 `--remote-url`。
- 不要在终端、对话或文档中回显认证值。

## Commands

### `init-template`

复制模板到目标文件：

```powershell
python .\scripts\tianyin_wiki.py init-template --output .\outputs\detail-design.md
```

初始化 1-N 详设：

```powershell
python .\scripts\tianyin_wiki.py init-template --template 1-n --output .\outputs\1-n-detail-design.md
```

`--template` 支持：

- `baseline`：基线详设模板，默认值。
- `1-n`：1-N 详设模板，来源页面 `pageId=224905569`。
- 为兼容已使用的命令，`default` 等同于 `baseline`。

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

支持认证参数：

- `--auth-type basic|bearer|none`
- `--username`
- `--password`
- `--token`
- `--mermaid-format svg|png`，默认 `png`
- `--mermaid-scale <正数>`，默认 `3`，仅对 PNG 生效。
- `--image-width <px>`，默认自适应：展示宽度 = 原始宽度的一半，减半后仍超过 `500` 则固定为 `500`（`min(原始宽度/2, 500)`）；传固定值则按该宽度展示（写入 `<ac:image ac:width="500">`），传 `0` 不设置显式宽度。

处理顺序：

1. 渲染每个 `mermaid` 代码块到临时目录。
2. 通过 `POST /rest/api/content/{pageId}/child/attachment` 上传 SVG/PNG。
3. 使用 `<ac:image><ri:attachment ... /></ac:image>` 写入 storage HTML。
4. 更新页面正文。渲染临时文件会删除，远程附件不会自动删除。

代码块默认使用 Emacs 主题（`<ac:parameter ac:name="theme">Emacs</ac:parameter>`），无需显式配置。

默认发布即高分辨率 PNG（`--mermaid-format png --mermaid-scale 3`），无需内联预览确认；显式选用 SVG 时以 `image/svg+xml` 上传（不经栅格化），首次发布应确认内联预览正常，若实例不支持则由用户显式改回 PNG：

```powershell
python .\scripts\tianyin_wiki.py publish-md --input .\outputs\detail-design.md --remote-url "http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=123456" --mermaid-format png --mermaid-scale 3
```

Mermaid 渲染按 `PATH` 探测 `mmdc`（`npm i -g @mermaid-js/mermaid-cli`）或 `npx`，无需配置。

### `upload-attachment`

只上传一个附件，不更新页面正文。用于验证 Confluence 附件接口：

```powershell
python .\scripts\tianyin_wiki.py upload-attachment --file .\outputs\tianyin-mermaid-example.svg --remote-url "http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=123456"
```

上传使用 `POST /rest/api/content/{pageId}/child/attachment`、`multipart/form-data` 和 `X-Atlassian-Token: no-check`。同名附件由 Confluence 作为新版本处理。

### 辅助脚本

本地渲染单个 Mermaid 文件：

```powershell
python .\scripts\wiki_diagram.py --input .\outputs\flow.mmd --output .\outputs\flow.svg
```

只读检查页面附件；可使用 `--filename` 过滤 SVG 附件：

```powershell
python .\scripts\wiki_attachment_probe.py --remote-url "<wiki-url>" --filename "tianyin-mermaid-example.svg"
```

### `lint-doc`

校验本地详设是否仍符合固定模板规则：

```powershell
python .\scripts\tianyin_wiki.py lint-doc --input .\outputs\detail-design.md
```

### `prepare-paste-html`

将符合模板规则的 Markdown 转成适合 Confluence 编辑器粘贴的富文本 HTML：

```powershell
python .\scripts\tianyin_wiki.py prepare-paste-html --input .\outputs\detail-design.md
```

指定输出路径：

```powershell
python .\scripts\tianyin_wiki.py prepare-paste-html --input .\outputs\detail-design.md --output .\outputs\detail-design.paste.html
```

### `diagnose-auth`

诊断 wiki 认证和网关行为：

```powershell
python .\scripts\tianyin_wiki.py diagnose-auth
```

诊断结果判断：

- `no-auth` 返回 `302` 且 `Location` 指向 `zerotrust.esign.cn`：CLI 无浏览器零信任登录态。
- `configured-auth` 返回 `500` 且 `server=openresty`：当前认证请求被网关异常处理。
- `dummy-basic` 也返回 `500`：任意 Basic Authorization 都会触发网关 500，不是账号密码错误。
- `dummy-bearer` 返回 `302`：问题特指 Basic 认证头，不是所有 Authorization 头都会 500。

### `get-login-url`

当无认证访问被 ZeroTrust 重定向时，输出供浏览器打开的登录链接：

```powershell
python .\scripts\tianyin_wiki.py get-login-url --remote-url "http://wiki.timevale.cn:8081/pages/viewpage.action?pageId=123456"
```

仅在 `302`、`303`、`307` 或 `308` 响应包含 `Location` 时成功。输出链接只用于把用户带到公司登录页，不是可导出的认证凭证。使用 `@电脑` 时，让用户完成扫码、MFA 和 CAPTCHA；禁止读取或导出 Cookie、LocalStorage、会话文件、Authorization 头、密码或 token。

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

## 浏览器兜底

浏览器登录、扫码和保存约束见 `remote-publish.md`。浏览器兜底不上传 Mermaid 附件；需要内联图时使用 REST `publish-md`。
