# /ai-do 规范索引

`code-standards.md` 是兼容旧提示的索引文件。执行 `/ai-do` 时 **MUST NOT** 只读取本文件代替规则正文，**MUST** 按场景加载：

- `core-standards.md`：通用优先级、上下文预算、执行契约、编码硬约束。
- `verification.md`：验证分级、diff 复核、失败处理、最终报告要求。
- `java-spring.md`：仅 Java/Spring Boot/微服务项目启用的专项规则。

**MUST 加载顺序**：

1. **MUST** 先读 `core-standards.md`。
2. **MUST** 再读 `verification.md`。
3. 仅当技术栈识别为 Java/Spring Boot/微服务时，**MUST** 再读 `java-spring.md`；非 Java/Spring 项目 **MUST NOT** 读取或套用该专项规则。

辅助脚本默认会扫描 `references/*.md` 中的条款编号，因此检查单可引用任意规则正文中的 `§` 编号。
