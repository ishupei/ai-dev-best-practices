# 基线详设模板规则

- 默认模板为基线详设，正文来源：`references/templates/tianyin-baseline-design-template.md`，CLI 模板标识为 `baseline`。
- 明确指定 `1-N`、`1-N详设` 时，使用 1-N 详设模板 `references/templates/tianyin-1-n-design-template.md`，规则见 `1-n-template-rules.md`，CLI 模板标识为 `1-n`。
- 标题结构（一级章节与固定二级骨架）**以模板文件为唯一真源**，文档必须保留模板中的全部标题，不得删改；校验由 `lint-doc` 从模板动态解析。
- `4.需求功能点` 固定拆分为 `4.1 需求功能点`、`4.2 影响功能点`
- `5.1.x` 固定优先使用：`需求概述`、`现状代码分析`、`落地方案`
- `6.业务功能设计` 固定优先包含：`6.1 API接口设计`、`6.2 RPC接口设计`、`6.2.3 伪代码`、`6.3 技术配置(ecos)`
- 无法确认的信息优先写入 `11.1 风险点`
- 不在模板正文中写 `section_key`、元信息块、机器字段
- 发布前建议通过 `lint-doc` 自查；发布时结构差异仅提示，不阻断推送
- 回填（`merge-clear`）只允许修改白名单章节（`ALLOWED_CLEAR_TARGETS`），不允许改一级章节和固定二级骨架
