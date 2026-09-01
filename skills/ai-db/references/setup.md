# AI DB 环境安装与配置

仅当 Python 缺失、版本过低或 MySQL 驱动未安装时读取本文件。

## 依赖一览

| 用途 | 依赖 | 安装/探测方式 |
|---|---|---|
| Python 启动 | Python 3.7+ | 必须前置安装；Windows 必须使用 `scripts/python_probe.ps1` 探测启动器自动选择（见下） |
| MySQL 驱动 | `pymysql`（首选，纯 Python 无编译）；`mysql-connector-python` 为回退 | 脚本自动探测，缺失时按提示安装（命令见下） |
| 环境存储 | 无（JSON 文件，`~/.config/ai-db/`） | 无需安装 |

## MySQL 驱动版本选择

驱动按 Python 版本自动选择安装命令（脚本的 `driver_install_hint` 已内置该逻辑，缺失驱动时直接给出对应命令）：

| Python 版本 | pymysql 版本 | 安装命令 |
|---|---|---|
| 3.9+ | 2.x（最新） | `pip install pymysql` |
| 3.7 / 3.8 | 1.x（1.1+ 兼容系列） | `pip install "pymysql>=1.1,<2"` |

回退驱动 `mysql-connector-python`：8.4/9.0 需 Python 3.8+，9.5 需 3.10+；选择该驱动时必须按实际 Python 版本匹配。

## 首次安装加速（国内网络）

**1. Python 解释器**：python.org 直连下载缓慢或失败时，从国内镜像下载（文件与官方一致，安装时勾选 *Add python.exe to PATH*）：

- 目录页：华为云 `https://mirrors.huaweicloud.com/python/`、阿里云 `https://mirrors.aliyun.com/python-release/windows/`
- 直链（实测可达）：推荐 `https://mirrors.huaweicloud.com/python/3.12.8/python-3.12.8-amd64.exe`（3.12.8 仍在维护期）；最低要求 3.7+，3.9.13 及以上版本均可（`https://mirrors.huaweicloud.com/python/3.9.13/python-3.9.13-amd64.exe`）；旧版本兜底 `https://mirrors.huaweicloud.com/python/3.7.9/python-3.7.9-amd64.exe`

**2. MySQL 驱动 `pymysql`**：直连 PyPI 缓慢或失败时用镜像源；执行一次持久化配置后，后续所有 pip 安装免 `-i`：

```powershell
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip install pymysql
```

或单次指定镜像源：

```powershell
pip install pymysql -i https://mirrors.aliyun.com/pypi/simple/
```

`pymysql` 为纯 Python 包（无二进制编译），安装即用。技能不自动切换 pip 源，也不内置/打包任何第三方代码（避免版本漂移与安全风险）；CLI 缺少驱动时会直接给出上述镜像安装命令。

## 环境变量

| 变量 | 作用 | 说明 |
|---|---|---|
| `AI_DB_PYTHON` | 指定 Python 解释器路径 | Windows 探测启动器最高优先级；设置后必须为可用的 Python 3.7+ 解释器，否则启动器直接报错（不静默回退） |
| `AI_DB_DIR` | 指定环境存储目录 | 覆盖默认 `~/.config/ai-db/`；也可用 `--store-dir` 临时指定 |

## Windows 启动器

Windows 必须统一通过 `scripts/python_probe.ps1` 探测启动器执行，它会跳过 Microsoft Store 占位程序，自动选择 Python 3.7+：

```powershell
powershell .\scripts\python_probe.ps1 status
```

若 ExecutionPolicy 限制直接执行脚本（如 `Restricted`），用 `-ExecutionPolicy Bypass` 调用：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\python_probe.ps1 status
```

若未发现 Python 3.7+，启动器会直接要求先安装（提示信息含国内镜像地址）。其余平台直接使用：

```powershell
python .\scripts\db_query.py status
```
