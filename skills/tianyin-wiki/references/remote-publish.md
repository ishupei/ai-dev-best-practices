# 远程发布与认证

## REST 发布

发布前先执行 `lint-doc` 自查，再使用 `publish-md`（结构校验差异仅提示，不阻断发布）。Mermaid 统一作为高分辨率 PNG 附件上传，默认缩放值为 `3`。

```powershell
python .\scripts\tianyin_wiki.py lint-doc --input .\outputs\detail-design.md
python .\scripts\tianyin_wiki.py publish-md --input .\outputs\detail-design.md --remote-url "<wiki-url>"
```

需要调整图片清晰度时，显式指定 PNG 缩放值：

```powershell
python .\scripts\tianyin_wiki.py publish-md --input .\outputs\detail-design.md --remote-url "<wiki-url>" --mermaid-scale 3
```

## 发布前检查

发布前可先只读检查目标页面与认证配置：

```powershell
python .\scripts\tianyin_wiki.py check-page --remote-url "<wiki-url>"
```

首次使用或配置文件未提供 `username`/`password` 时，先要求用户补充 `%USERPROFILE%\.config\tianyin-wiki\config.json`、命令行参数或环境变量；不要在输出、日志或文档中回显认证信息。
