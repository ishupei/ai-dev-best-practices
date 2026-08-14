# 环境与配置（Setup）

首次使用或团队接入时阅读；完整 CLI 参数见 `cli-reference.md`。

## 运行依赖（不随 skill 内置，需各自安装）

| 用途 | 依赖 | 安装/探测方式 |
|---|---|---|
| Mermaid 渲染 | `mmdc` 或 `npx` | `npm i -g @mermaid-js/mermaid-cli`；脚本按 `PATH` 自动探测，无需配置路径 |

## 配置文件（严禁入库）

- 个人配置统一存放：`%USERPROFILE%\.config\tianyin-wiki\config.json`（macOS/Linux 为 `~/.config/tianyin-wiki/config.json`）。
- 配置字段：`remoteUrl`、`baseUrl`、`pageId`、`authType`、`username`、`password`、`token`。
- **不随 skill 分发、不提交版本库**；分发物只含 `scripts/tianyin-wiki.config.sample.json` 样例，复制后填写自己的值。
- 旧版本曾放在 `%USERPROFILE%\.tianyin-wiki\config.json` 或 skill 目录 `scripts\tianyin-wiki.config.json`；CLI 发现历史文件时会提示迁移，迁移后请删除。

## 凭据注入

三种方式，优先级：**命令行显式参数 > 配置文件 > 环境变量**。

- 环境变量：`CONFLUENCE_USERNAME`、`CONFLUENCE_PASSWORD`、`CONFLUENCE_TOKEN`、`CONFLUENCE_AUTH_TYPE`。
- 配置文件：`CONFLUENCE_CONFIG=<path>` 指向任意位置（支持 `~` 展开），优先于默认路径。
- 配置文件中已提供 `baseUrl` 与 `pageId` 时，`check-page`、`publish-md` 可省略 `--remote-url`。

## 安全约束

- 不在终端、对话、日志或文档中回显认证值（密码、token、Authorization 头）。
- 目标 Wiki 地址通过 `--remote-url` 或配置 `baseUrl`/`pageId` 指定，skill 内不写死任何实例地址。
