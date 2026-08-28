# 远程发布与认证

## REST 发布

发布前建议执行 `lint-doc` 自查，再使用 `publish-md`（结构校验差异仅提示，不阻断发布）。Mermaid 统一作为高分辨率 PNG 附件上传，默认缩放值为 `3`。

```powershell
python .\scripts\tianyin_wiki.py lint-doc --input .\outputs\detail-design.md
python .\scripts\tianyin_wiki.py publish-md --input .\outputs\detail-design.md --remote-url "<wiki-url>"
```

需要调整图片清晰度时，显式指定 PNG 缩放值：

```powershell
python .\scripts\tianyin_wiki.py publish-md --input .\outputs\detail-design.md --remote-url "<wiki-url>" --mermaid-scale 3
```

## 认证诊断

REST 接口返回 `HTTP 500 openresty`、认证失败或 HTML 而非 JSON 时，先运行：

```powershell
python .\scripts\tianyin_wiki.py diagnose-auth --remote-url "<wiki-url>"
```

- `no-auth` 为 `302` 且跳转到 `zerotrust.esign.cn`：CLI 没有 ZeroTrust 会话。
- `configured-auth` 为 `500` 且 `server=openresty`：认证头被网关异常处理，不是 Markdown 内容问题。
- `dummy-basic` 同样为 `500`：Basic 认证头被网关拒绝，不能据此判断账号密码错误。

不要在输出、日志或文档中回显认证信息。

## ZeroTrust 与浏览器兜底

仅当用户明确要求使用浏览器登录态发布或浏览器兜底时执行：

1. 用 `get-login-url --remote-url "<wiki-url>"` 获取公司登录入口。
2. 用户自行完成扫码、MFA 或 CAPTCHA；不得代替操作或读取会话信息。
3. 确认原 Wiki 页面、登录用户和 `pageId` 正确。
4. 执行 `lint-doc` 与 `prepare-paste-html`。
5. 在编辑器中粘贴 HTML 前确认目标页面；保存前再次确认。
6. 保存后确认正文含有关键标题和文本。

浏览器兜底不会上传 Mermaid 附件，Mermaid 代码会按普通代码块粘贴。
