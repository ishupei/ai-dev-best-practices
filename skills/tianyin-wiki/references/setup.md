# 环境与配置（Setup）

首次使用或团队接入时阅读；完整 CLI 参数见 `cli-reference.md`。

## 运行依赖（不随 skill 内置，需各自安装）

| 用途 | 依赖 | 安装/探测方式 |
|---|---|---|
| Python 启动 | Python 3.9+ | 必须前置安装；Windows 上若 `python` 指向 Microsoft Store 占位程序且无输出失败，改用 `py -3`、真实 `python.exe` 路径，或 `.\scripts\tianyin_wiki.ps1` 自动选择 |
| Markdown 解析 | `markdown-it-py`（>= 3） | 渲染层基于 CommonMark/GFM AST 解析，必须安装：`pip install markdown-it-py` |
| Mermaid 渲染 | `mmdc` 或 `npx` + Chrome/Edge | 推荐 `npm i -g @mermaid-js/mermaid-cli`；脚本按 `PATH` 自动探测 `mmdc`，没有全局 `mmdc` 时回退到 `npx --yes @mermaid-js/mermaid-cli` |
| Mermaid 浏览器 | Chrome/Edge | 脚本会自动探测常见 Chrome/Edge 安装路径并注入 `PUPPETEER_EXECUTABLE_PATH`；未装或非标准路径时手动设置该环境变量 |

Windows 推荐通过启动器执行，它会跳过 Microsoft Store 占位程序；若未发现 Python 3.9+，会直接要求先安装：

```powershell
.\scripts\tianyin_wiki.ps1 doctor --input .\outputs\detail-design.md
```

新机器建议先执行一次环境诊断，确认 Python、Mermaid CLI、浏览器路径和文档中的 Mermaid 数量：

```powershell
python .\scripts\tianyin_wiki.py doctor --input .\outputs\detail-design.md
```

若 `doctor` 显示 `viaNpx: true`，首次渲染可能需要下载 Mermaid CLI 包；后续会使用 `npx` 缓存。频繁发布建议全局安装 `mmdc`，可避免每次通过 `npx` 启动带来的额外耗时。

`doctor` 和首次 Mermaid 渲染会把本机运行时探测结果写入 `~/.cache/tianyin-wiki/runtime.json`。后续执行会优先复用缓存中的 `mmdc`/`npx` 与浏览器路径，减少每次发布前的环境探测；安装新工具或移动浏览器后，用 `doctor --refresh-runtime` 强制重探测。

## 配置文件（严禁入库）

- 个人配置统一存放：`%USERPROFILE%\.config\tianyin-wiki\config.json`（macOS/Linux 为 `~/.config/tianyin-wiki/config.json`）。
- 配置字段：`template`、`remoteUrl`、`baseUrl`、`pageId`、`username`、`password`。
- `template`：默认模板模式，**仅允许 `baseline` 或 `1-n`**（`raw` 为内置默认，不允许写入配置，写入会报错）。所有命令未显式传 `--template` 时默认读取该字段，未配置时缺省 `raw`（`init-template` 需显式指定 `baseline`/`1-n`）。
- **不随 skill 分发、不提交版本库**；分发物只含 `scripts/tianyin-wiki.config.sample.json` 样例，复制后填写自己的值。

## 凭据注入

三种方式，优先级：**命令行显式参数 > 配置文件 > 环境变量**。

- 环境变量：`CONFLUENCE_USERNAME`、`CONFLUENCE_PASSWORD`。
- 配置文件：`CONFLUENCE_CONFIG=<path>` 指向任意位置（支持 `~` 展开），优先于默认路径。
- 配置文件中已提供 `baseUrl` 与 `pageId` 时，`check-page`、`publish-md` 可省略 `--remote-url`。
- 首次使用或配置文件未提供 `username`/`password` 时，先补充配置、命令行参数或环境变量，再执行远程发布/检查。

## 安全约束

- 不在终端、对话、日志或文档中回显认证值（密码、Authorization 头）。
- 目标 Wiki 地址通过 `--remote-url` 或配置 `baseUrl`/`pageId` 指定，skill 内不写死任何实例地址。
