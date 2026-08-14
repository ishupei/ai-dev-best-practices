# /ai-do Java/Spring 专项规范

仅当目标项目识别为 Java、Spring Boot 或微服务项目时 **MUST** 启用；其他技术栈 **MUST NOT** 套用本文件。

## 7. Java/Spring 规则

- 7.1 格式遵循项目既有 Java 风格；若项目已采用 Google Java Format AOSP，则使用 4 空格、注解一行一个、方法 `{` 跟随签名、链式调用断在 `.` 后。
- 7.2 空值判断 **MUST** 优先使用 `Objects`；通用工具 **MUST** 优先复用项目已有工具类，只有项目既有使用 Hutool 时才优先 Hutool。
- 7.3 属性复制 **MUST** 优先沿用项目现有方案；项目既有使用 Hutool `BeanUtil.copyProperties()` 时保持一致。
- 7.4 Controller 保持薄层，只做参数接收、校验和响应适配；业务逻辑放在 Service/ServiceImpl 或项目既有业务层。
- 7.5 MyBatis-Plus 项目中查询优先使用 `LambdaQueryWrapper`，除非现有相邻代码已有更一致的写法。
- 7.6 Controller/Service 新增对外方法按项目既有风格补 Javadoc；ServiceImpl 关键逻辑只注释必要的“为什么”。
- 7.7 不在代码中直接写完全限定类名，如 `java.util.List`；应使用 import。
- 7.8 非 Java/Spring 项目 **MUST** 只应用通用规则和现有风格，**MUST NOT** 强制要求本专项规则。
