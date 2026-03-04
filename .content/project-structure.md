## Project Structure

- **根目录**:
  - `.cursor/`：Cursor 相关配置与规则（含 `rules/`、`skills/`）。
  - `.trae/`：Trae 相关配置与规则（含 `rules/`、`skills/`）。
  - `.content/`：工程结构与元信息文档（当前文件）。

### Rules 结构

- **Cursor 规则**（`.cursor/rules`）
  - `global-dev.mdc`：**全局开发规范（global-level）**
    - 定义身份（Java Backend + SpringBoot / Vue Frontend）。
    - 通用推荐实践（Objects/Hutool/Log/BeanUtil/ServiceImpl/MyBatis-Plus/StringPool）。
    - 通用禁止实践（禁止使用完全限定类名等）。
  - `dev-project.mdc`：**项目级规范（project-level）**
    - 文档与 SQL 文件目录约定：`docs/`、`sql/`。
    - 工程结构文档维护约定：`.content/project-structure.md`。

- **Trae 规则**（`.trae/rules`）
  - `global-dev.md`：**全局开发规范（global-level）**，内容与 `global-dev.mdc` 对齐。
  - `dev-project.md`：**项目级规范（project-level）**，内容与 `dev-project.mdc` 对齐（文件组织与工程结构约定）。

> 后续如果新增模块（如 `backend/`、`frontend/`、`docs/` 等），应同步在本文件补充说明结构与规则适用范围。

