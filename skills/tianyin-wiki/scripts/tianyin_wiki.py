from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import struct
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent.parent
# 个人配置文件统一存于用户配置目录（~/.config/tianyin-wiki），不随 skill 分发、不入版本库
DEFAULT_CONFIG_FILE = Path.home() / ".config" / "tianyin-wiki" / "config.json"
# 本机运行时探测缓存只保存工具路径，不保存 Wiki 地址或凭据
DEFAULT_RUNTIME_CACHE_FILE = Path.home() / ".cache" / "tianyin-wiki" / "runtime.json"
RUNTIME_CACHE_VERSION = 1
TEMPLATE_FILES = {
    "baseline": "tianyin-baseline-design-template.md",
    "1-n": "tianyin-1-n-design-template.md",
}

TEMPLATE_DIR = ROOT / "references" / "templates"

TEMPLATE_ALIASES = {
    "baseline": "baseline",
    "default": "baseline",
    "1-n": "1-n",
    # raw 模式：不校验任何格式，直接发布任意本地 Markdown
    "raw": "raw",
    "direct": "raw",
}

ALLOWED_CLEAR_TARGETS = {
    "1.方案背景": "# 1.方案背景",
    "2.需求评估表": "# 2.需求评估表",
    "4.需求功能点": "# 4.需求功能点",
    "5.业务流程设计": "# 5.业务流程设计",
    "6.业务功能设计": "# 6.业务功能设计",
    "7.数据库设计": "# 7.数据库设计",
    "8.安全设计": "# 8.安全设计",
    "9.交付运维影响": "# 9.交付运维影响",
    "11.1 风险点": "## 11.1 风险点",
    "11.2 回归测试": "## 11.2 回归测试",
}

# 远程 wiki API 调用统一超时，避免网络异常时 CLI 无限挂起
HTTP_TIMEOUT = 60

# Mermaid 渲染背景色（PNG 白底，避免透明图在深色/打印场景显示异常）；
# 背景色同时参与渲染缓存键，变更后会生成新的缓存条目，不会复用旧背景的渲染结果
MERMAID_BACKGROUND = "white"


@dataclass
class RuntimeConfig:
    remote_url: str
    base_url: str
    page_id: str
    headers: dict[str, str]


@dataclass(frozen=True)
class RenderedMermaid:
    attachment_filename: str
    image_path: Path


@dataclass(frozen=True)
class TemplateStructure:
    """Single parsed view of a template file (lint's single source of truth)."""
    headings: list[str]                # required `## `/`### ` headings, in order
    ancestors: dict[str, list[str]]   # heading -> chain of ancestor headings (closest first)
    table_owners: dict[str, str]      # required table header row -> nearest preceding heading


def error(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalize_template_name(template_name: str) -> str:
    try:
        return TEMPLATE_ALIASES[template_name]
    except KeyError as exc:
        raise ValueError(f"unsupported template: {template_name}") from exc


def resolve_template(args: argparse.Namespace, fallback: str = "raw") -> str:
    """Effective template: explicit CLI flag > config file `template` field > fallback (raw).

    Config `template` stores template-generation preferences only (baseline/1-n);
    raw is the built-in default and must not be stored in the config file.
    """
    explicit = getattr(args, "template", None)
    if explicit:
        return normalize_template_name(str(explicit).strip())
    if fallback == "raw" and not config_file_exists():
        return "raw"
    config_data = load_config_file()
    configured = str(config_data.get("template") or "").strip()
    if configured:
        normalized = normalize_template_name(configured)
        if normalized == "raw":
            raise ValueError("config `template` must be baseline or 1-n; raw is the built-in default and cannot be stored in the config file")
        return normalized
    return normalize_template_name(fallback)


def get_template_file(template_name: str) -> Path:
    filename = TEMPLATE_FILES[normalize_template_name(template_name)]
    candidate = TEMPLATE_DIR / filename
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"template file not found: {candidate}")


def is_table_separator(line: str) -> bool:
    """模板结构解析用：判断某行是否为 GFM 表格分隔行（| --- | / | :---: |）。"""
    stripped = line.strip()
    return stripped.startswith("|") and re.fullmatch(r"\|?[\s:\-|\t]+\|?", stripped) is not None


@lru_cache(maxsize=4)
def parse_template(template_name: str) -> TemplateStructure:
    """Parse a template file once into headings, ancestor chains and table owners."""
    if normalize_template_name(template_name) == "raw":
        return TemplateStructure([], {}, {})
    lines = normalize_newlines(read_text(get_template_file(template_name))).split("\n")
    headings: list[str] = []
    ancestors: dict[str, list[str]] = {}
    table_owners: dict[str, str] = {}
    stack: list[tuple[int, str]] = []
    current: str | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        match = re.match(r"^(#{1,6})\s+(\S.*)$", stripped)
        if match:
            level = len(match.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            ancestors[stripped] = [heading for _, heading in stack]
            stack.append((level, stripped))
            current = stripped
            if 1 <= level <= 3:
                headings.append(stripped)
        elif (
            current is not None
            and stripped.startswith("|")
            and index + 1 < len(lines)
            and is_table_separator(lines[index + 1])
        ):
            table_owners[stripped] = current
    return TemplateStructure(headings, ancestors, table_owners)


def template_headings(template_name: str) -> list[str]:
    """Expected `## `/`### ` headings, derived from the template file (single source of truth)."""
    return parse_template(template_name).headings


def template_heading_ancestors(template_name: str) -> dict[str, list[str]]:
    """Map each template heading to the chain of its ancestor headings (closest first)."""
    return parse_template(template_name).ancestors


def template_table_owners(template_name: str) -> dict[str, str]:
    """Map each required table header row to its nearest preceding template heading."""
    return parse_template(template_name).table_owners


def template_table_headers(template_name: str) -> list[str]:
    """Expected Markdown table header rows, derived from the template file."""
    return list(parse_template(template_name).table_owners)


def doc_heading_bodies(markdown_text: str) -> dict[str, str]:
    """Map each document heading to the text directly under it (up to the next heading of any level)."""
    lines = normalize_newlines(markdown_text).split("\n")
    positions = [
        (index, line.strip())
        for index, line in enumerate(lines)
        if re.match(r"^#{1,6}\s+\S", line.strip())
    ]
    bodies: dict[str, str] = {}
    for index, (position, heading) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(lines)
        bodies[heading] = "\n".join(lines[position + 1 : end])
    return bodies


def is_uninvolved_chain(doc_bodies: dict[str, str], chain: list[str]) -> bool:
    """True when any heading in the chain is marked 未涉及/不涉及 in the document."""
    return any(
        "未涉及" in doc_bodies.get(heading, "") or "不涉及" in doc_bodies.get(heading, "")
        for heading in chain
    )


def template_requirement_exempt(
    item: str,
    template_name: str,
    doc_bodies: dict[str, str],
) -> bool:
    """True when a missing required heading/table sits under a chapter marked 未涉及/不涉及."""
    ancestors = template_heading_ancestors(template_name)
    chain = ancestors.get(item)
    if chain is None:
        owner = template_table_owners(template_name).get(item)
        if owner is None:
            return False
        chain = [owner, *ancestors.get(owner, [])]
    return is_uninvolved_chain(doc_bodies, chain)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_storage_for_compare(value: str) -> str:
    """Normalize Confluence storage serialization for equivalence comparison.

    Confluence 返回的 storage 与提交的 HTML 存在两类序列化差异：非 ASCII
    标点以命名实体返回（如 “ -> &ldquo;），结构化宏被注入服务端生成的
    ac:macro-id / ac:schema-version 属性。解实体并剥离注入属性后，比较结果
    只反映可见内容是否变化（实测见 docs/bugfix/bugfix_0828_*）。

    标记性实体（&lt;/&gt;/&amp;/&quot;/&apos; 及数字实体）不能随整体解实体：
    否则"转义成文本的标签"（&lt;span&gt;）会被误判为与真实标签（<span>）等价，
    导致真实内容变更被 noChanges 短路跳过（实测见 wiki 页面 span 标注修复）。
    """
    held: list[str] = []

    def hold_markup_entity(match: re.Match) -> str:
        held.append(match.group(0))
        return f"\x00E{len(held) - 1}\x00"

    value = _MARKUP_ENTITY_RE.sub(hold_markup_entity, value)
    value = html.unescape(value)
    # Confluence 保存 span 标注时会把它十六进制颜色规范化为 rgb() 形式（如
    # color:#16a34a -> color: rgb(22,163,74);），归一化后同一内容重复推送不再误判变更
    value = _RGB_COLOR_RE.sub(
        lambda m: f"color:#{int(m.group(1)):02x}{int(m.group(2)):02x}{int(m.group(3)):02x}",
        value,
    )
    value = re.sub(r'\s*ac:macro-id=["\'][^"\']*["\']', "", value)
    value = re.sub(r'\s*ac:schema-version=["\'][^"\']*["\']', "", value)
    return re.sub(r"\x00E(\d+)\x00", lambda m: held[int(m.group(1))], value)


def strip_html_comments(markdown_text: str) -> str:
    """Remove full-line HTML comments (template fill guidance) outside code fences."""
    lines = normalize_newlines(markdown_text).split("\n")
    in_fence = False
    filtered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            filtered.append(line)
        elif not in_fence and stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        else:
            filtered.append(line)
    return "\n".join(filtered)


def extract_main_title(markdown_text: str) -> str | None:
    """Document main title: the first level-1 heading when it opens the document.

    The local md keeps it as the file title; the wiki page title replaces it, so
    wiki-bound conversions strip it from the body.
    """
    for line in normalize_newlines(markdown_text).split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        return stripped if re.match(r"^#\s+\S", stripped) else None
    return None


def parse_remote_url(remote_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(remote_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"invalid remote url: {remote_url}")
    page_id = urllib.parse.parse_qs(parsed.query).get("pageId", [""])[0].strip()
    if not page_id:
        raise ValueError(f"remote url missing pageId: {remote_url}")
    return f"{parsed.scheme}://{parsed.netloc}", page_id


def build_headers(username: str | None, password: str | None) -> dict[str, str]:
    if not username or not password:
        raise ValueError(
            "Wiki username/password are required. Add `username` and `password` to "
            f"{DEFAULT_CONFIG_FILE}, pass --username/--password, or set "
            "CONFLUENCE_USERNAME/CONFLUENCE_PASSWORD before running remote wiki operations."
        )
    encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Accept": "application/json", "Authorization": f"Basic {encoded}"}


@lru_cache(maxsize=1)
def load_config_file() -> dict:
    """Load the personal config file once per process (cached)."""
    config_file = resolve_config_file()
    if not config_file.exists():
        return {}
    with config_file.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"config file must be a JSON object: {config_file}")
    return data


def resolve_config_file() -> Path:
    config_path = os.environ.get("CONFLUENCE_CONFIG")
    if config_path:
        return Path(config_path).expanduser().resolve()
    return DEFAULT_CONFIG_FILE


def config_file_exists() -> bool:
    return resolve_config_file().exists()


def runtime_cache_file(env: dict[str, str] | None = None) -> Path:
    env = env or os.environ
    configured = str(env.get("TIANYIN_WIKI_RUNTIME_CACHE") or "").strip()
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_RUNTIME_CACHE_FILE


def load_runtime_cache(env: dict[str, str] | None = None) -> dict:
    env = env or os.environ
    if env.get("TIANYIN_WIKI_DISABLE_RUNTIME_CACHE") == "1":
        return {}
    cache_file = runtime_cache_file(env)
    if not cache_file.is_file():
        return {}
    try:
        with cache_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or data.get("version") != RUNTIME_CACHE_VERSION:
        return {}
    return data


def save_runtime_cache(update: dict, env: dict[str, str] | None = None) -> None:
    env = env or os.environ
    if env.get("TIANYIN_WIKI_DISABLE_RUNTIME_CACHE") == "1":
        return
    cache_file = runtime_cache_file(env)
    data = load_runtime_cache(env)
    data.update(update)
    data["version"] = RUNTIME_CACHE_VERSION
    data["platform"] = sys.platform
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = cache_file.with_suffix(cache_file.suffix + ".tmp")
        with temp_file.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temp_file, cache_file)
    except OSError:
        return


def command_path_available(command: list[str]) -> bool:
    if not command:
        return False
    executable = str(command[0])
    if Path(executable).is_file():
        return True
    return shutil.which(executable) is not None


def config_remote_url(config_data: dict) -> str | None:
    remote_url = str(config_data.get("remoteUrl") or config_data.get("remote_url") or "").strip()
    if remote_url:
        return remote_url
    base_url = str(config_data.get("baseUrl") or config_data.get("base_url") or "").strip().rstrip("/")
    page_id = str(config_data.get("pageId") or config_data.get("page_id") or "").strip()
    if base_url and page_id:
        return f"{base_url}/pages/viewpage.action?pageId={page_id}"
    return None


def load_remote_target(args: argparse.Namespace) -> tuple[str, str, str]:
    remote_url = args.remote_url
    if not remote_url:
        remote_url = config_remote_url(load_config_file())
    if not remote_url:
        raise ValueError("remote-url required; remote wiki operations must be explicitly requested")
    base_url, page_id = parse_remote_url(remote_url)
    return remote_url, base_url, page_id


def load_runtime_config(args: argparse.Namespace) -> RuntimeConfig:
    remote_url, base_url, page_id = load_remote_target(args)
    username = getattr(args, "username", None)
    password = getattr(args, "password", None)
    if username and password:
        headers = build_headers(username, password)
        return RuntimeConfig(remote_url=remote_url, base_url=base_url, page_id=page_id, headers=headers)

    config_data = load_config_file()
    if not username:
        username = config_data.get("username") or os.environ.get("CONFLUENCE_USERNAME")
    if not password:
        password = config_data.get("password") or os.environ.get("CONFLUENCE_PASSWORD")
    headers = build_headers(username, password)
    return RuntimeConfig(remote_url=remote_url, base_url=base_url, page_id=page_id, headers=headers)


def http_error_message(exc: urllib.error.HTTPError) -> str:
    """One-line HTTP error detail, including the server body when present."""
    try:
        response_body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        response_body = ""
    detail = f"HTTP {exc.code} {exc.reason}"
    if response_body.strip():
        detail += f": {response_body}"
    return detail


def is_duplicate_attachment_error(error: Exception) -> bool:
    """Whether Confluence rejected an attachment because another publisher added the same name."""
    detail = str(error).lower()
    return "http 400" in detail and "same file name" in detail


def is_page_version_conflict(error: Exception) -> bool:
    """Whether a page PUT lost a concurrent version update."""
    return "http 409" in str(error).lower()


def request_json(method: str, url: str, headers: dict[str, str], body: dict | None = None) -> dict:
    data = None
    request_headers = dict(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url=url, method=method, headers=request_headers, data=data)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(http_error_message(exc)) from exc


def request_multipart_file(url: str, headers: dict[str, str], file_path: Path) -> dict:
    boundary = f"----TianyinWiki{uuid.uuid4().hex}"
    filename = file_path.name.replace("\\", "\\\\").replace('"', '\\"')
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body = b"".join((
        f"--{boundary}\r\n".encode("ascii"),
        (
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8"),
        file_path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode("ascii"),
    ))
    request_headers = dict(headers)
    request_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    request_headers["X-Atlassian-Token"] = "no-check"
    request = urllib.request.Request(url=url, method="POST", headers=request_headers, data=body)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(http_error_message(exc)) from exc


def cmd_doctor(args: argparse.Namespace) -> int:
    result: dict[str, object] = {
        "python": sys.executable,
        "platform": sys.platform,
        "runtimeCache": str(runtime_cache_file()),
        "refreshRuntime": bool(args.refresh_runtime),
    }
    try:
        command = resolve_mermaid_command(refresh_cache=args.refresh_runtime)
        result["mermaidRenderer"] = {
            "available": True,
            "command": command,
            "viaNpx": Path(command[0]).name.lower().startswith("npx"),
        }
    except RuntimeError as exc:
        result["mermaidRenderer"] = {
            "available": False,
            "error": str(exc),
        }

    env = mermaid_environment(refresh_cache=args.refresh_runtime)
    browser = env.get("PUPPETEER_EXECUTABLE_PATH") or ""
    result["browser"] = {
        "executable": browser,
        "detected": bool(browser),
    }
    result["puppeteer"] = {
        "skipDownload": env.get("PUPPETEER_SKIP_DOWNLOAD", ""),
    }

    if args.input:
        input_path = Path(args.input).resolve()
        if not input_path.is_file():
            return error(f"markdown file not found: {input_path}")
        result["input"] = {
            "path": str(input_path),
            "mermaidBlocks": len(mermaid_blocks(read_text(input_path))),
        }

    hint = mermaid_runtime_hint(env)
    if hint:
        result["hint"] = hint
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def fetch_page(config: RuntimeConfig) -> dict:
    endpoint = f"{config.base_url.rstrip('/')}/rest/api/content/{config.page_id}?expand=body.storage,version,space"
    return request_json("GET", endpoint, config.headers)


def upload_attachment(config: RuntimeConfig, file_path: Path) -> dict:
    endpoint = f"{config.base_url.rstrip('/')}/rest/api/content/{config.page_id}/child/attachment"
    response = request_multipart_file(endpoint, config.headers, file_path)
    results = response.get("results") if isinstance(response, dict) else None
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise RuntimeError("attachment upload returned no attachment result")
    attachment = results[0]
    if not attachment.get("id") or not attachment.get("title"):
        raise RuntimeError("attachment upload returned an incomplete attachment result")
    return attachment


def fetch_attachment_titles(config: RuntimeConfig) -> set[str]:
    """Titles (filenames) of attachments already on the page, paginated.

    `publish-md` 以此判断同名附件是否已存在：附件文件名包含图表源码的
    sha256 摘要、PNG 缩放值与背景色，同名即同渲染参数，直接跳过上传即可（Confluence 对同名
    附件的新建请求返回 HTTP 400，见实测记录）。
    """
    base = f"{config.base_url.rstrip('/')}/rest/api/content/{config.page_id}/child/attachment"
    titles: set[str] = set()
    url: str | None = f"{base}?limit=200"
    while url:
        response = request_json("GET", url, config.headers)
        results = response.get("results")
        if not isinstance(results, list):
            raise RuntimeError("attachment list returned an invalid response")
        titles.update(
            str(attachment["title"])
            for attachment in results
            if isinstance(attachment, dict) and attachment.get("title")
        )
        next_link = (response.get("_links") or {}).get("next")
        if not next_link:
            break
        url = next_link if next_link.startswith("http") else f"{config.base_url.rstrip('/')}{next_link}"
    return titles


def build_markdown_parser():
    """CommonMark + GFM 扩展（表格/删除线）解析器。

    解析正确性（嵌套链接、转义、列表、表格、围栏等）由 markdown-it-py 的
    CommonMark/GFM 实现保证，本模块只负责"节点 → Confluence storage"映射。
    """
    try:
        from markdown_it import MarkdownIt
    except ImportError as exc:
        raise RuntimeError(
            "missing dependency: install markdown-it-py (pip install markdown-it-py)"
        ) from exc
    md = MarkdownIt("commonmark", {"html": True})
    md.enable("table")
    md.enable("strikethrough")
    return md


@lru_cache(maxsize=1)
def _markdown_parser():
    return build_markdown_parser()


def parse_markdown(markdown_text: str) -> list:
    """解析 Markdown 为 token 流；mermaid 提取与 storage 渲染共用同一解析，保证围栏顺序一致。"""
    return _markdown_parser().parse(normalize_newlines(markdown_text))


def mermaid_blocks(markdown_text: str) -> list[str]:
    """按 token 流提取 mermaid 围栏源码（与渲染阶段顺序一致，含 ~~~ 围栏）。"""
    return [
        token.content
        for token in parse_markdown(markdown_text)
        if token.type == "fence" and token.info.strip().lower().startswith("mermaid")
    ]


def resolve_mermaid_command(
    env: dict[str, str] | None = None,
    refresh_cache: bool = False,
) -> list[str]:
    env = env or os.environ
    if not refresh_cache:
        cache = load_runtime_cache(env)
        cached = cache.get("mermaidCommand")
        if (
            isinstance(cached, list)
            and all(isinstance(part, str) for part in cached)
            and command_path_available(cached)
        ):
            return cached
        if cached == [] and cache.get("mermaidProbeComplete") is True:
            raise RuntimeError("Mermaid renderer unavailable: install mmdc or npx, then run doctor --refresh-runtime")
    mmdc = shutil.which("mmdc") or shutil.which("mmdc.cmd")
    if mmdc:
        command = [mmdc]
        save_runtime_cache({"mermaidCommand": command, "mermaidProbeComplete": True}, env)
        return command
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx:
        command = [npx, "--yes", "@mermaid-js/mermaid-cli"]
        save_runtime_cache({"mermaidCommand": command, "mermaidProbeComplete": True}, env)
        return command
    save_runtime_cache({"mermaidCommand": [], "mermaidProbeComplete": True}, env)
    raise RuntimeError("Mermaid renderer unavailable: install mmdc or npx")


def browser_executable_candidates(env: dict[str, str] | None = None) -> list[Path]:
    """Common Chrome/Edge locations used by Puppeteer-based Mermaid rendering."""
    env = env or os.environ
    candidates: list[Path] = []
    explicit = (
        env.get("PUPPETEER_EXECUTABLE_PATH")
        or env.get("CHROME_PATH")
        or env.get("CHROMIUM_PATH")
    )
    if explicit:
        candidates.append(Path(explicit))

    if sys.platform == "win32":
        for root_var in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            root = env.get(root_var)
            if not root:
                continue
            base = Path(root)
            candidates.extend((
                base / "Google" / "Chrome" / "Application" / "chrome.exe",
                base / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            ))
    elif sys.platform == "darwin":
        candidates.extend((
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ))
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "microsoft-edge-stable"):
            executable = shutil.which(name)
            if executable:
                candidates.append(Path(executable))

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.expanduser())
        if key not in seen:
            seen.add(key)
            deduped.append(candidate.expanduser())
    return deduped


def resolve_browser_executable(
    env: dict[str, str] | None = None,
    refresh_cache: bool = False,
) -> Path | None:
    env = env or os.environ
    explicit = (
        env.get("PUPPETEER_EXECUTABLE_PATH")
        or env.get("CHROME_PATH")
        or env.get("CHROMIUM_PATH")
    )
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None
    if not refresh_cache:
        cache = load_runtime_cache(env)
        cached = cache.get("browserExecutable")
        if isinstance(cached, str) and cached:
            path = Path(cached).expanduser()
            if path.is_file():
                return path
        if cached == "" and cache.get("browserProbeComplete") is True:
            return None
    for candidate in browser_executable_candidates(env):
        if candidate.is_file():
            save_runtime_cache({"browserExecutable": str(candidate), "browserProbeComplete": True}, env)
            return candidate
    save_runtime_cache({"browserExecutable": "", "browserProbeComplete": True}, env)
    return None


def mermaid_environment(
    base_env: dict[str, str] | None = None,
    refresh_cache: bool = False,
) -> dict[str, str]:
    env = dict(base_env or os.environ)
    env.setdefault("PUPPETEER_SKIP_DOWNLOAD", "true")
    if not env.get("PUPPETEER_EXECUTABLE_PATH"):
        browser = resolve_browser_executable(env, refresh_cache=refresh_cache)
        if browser is not None:
            env["PUPPETEER_EXECUTABLE_PATH"] = str(browser)
    return env


def mermaid_runtime_hint(env: dict[str, str]) -> str:
    if env.get("PUPPETEER_EXECUTABLE_PATH"):
        return ""
    return (
        "No local Chrome/Edge executable was auto-detected. Install Chrome/Edge or set "
        "PUPPETEER_EXECUTABLE_PATH to the browser executable path; on Windows this often "
        "looks like C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe. "
        "For faster repeated runs, install Mermaid CLI globally with "
        "`npm i -g @mermaid-js/mermaid-cli` so the CLI can use `mmdc` directly."
    )


def png_dimensions(png_path: Path) -> tuple[int, int]:
    data = png_path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("Mermaid renderer did not produce a valid PNG")
    return struct.unpack(">II", data[16:24])



def diagram_image_width(image_path: Path) -> int:
    """Auto display width: half the intrinsic width, capped at 500px."""
    return min(png_dimensions(image_path)[0] // 2, 500)


def render_mermaid_diagrams(
    markdown_text: str,
    output_dir: Path,
    raster_scale: float = 3.0,
    cache_dir: Path | None = None,
) -> list[RenderedMermaid]:
    sources = mermaid_blocks(markdown_text)
    if not sources:
        return []
    if not math.isfinite(raster_scale) or raster_scale <= 0:
        raise ValueError("mermaid raster scale must be a finite number greater than zero")

    env = mermaid_environment()
    command = resolve_mermaid_command(env)

    rendered_by_digest: dict[str, RenderedMermaid] = {}
    rendered: list[RenderedMermaid] = []
    for index, source in enumerate(sources, start=1):
        if not source:
            raise ValueError(f"mermaid diagram {index} is empty")
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
        existing = rendered_by_digest.get(digest)
        if existing:
            rendered.append(existing)
            continue

        source_path = output_dir / f"mermaid-{index}.mmd"
        # 附件名/缓存键规范化：固定顺序 摘要-格式-缩放-背景色，全部渲染参数入名，
        # 任一参数变化即生成新文件名并上传，避免复用不同渲染参数的旧图
        scale_key = f"{raster_scale:g}"
        render_suffix = f"png-{scale_key}-{MERMAID_BACKGROUND}"
        image_path = output_dir / f"tianyin-mermaid-{digest}-{render_suffix}.png"
        write_text(source_path, source + "\n")

        # 附件名与缓存键同构（缓存键省略 tianyin-mermaid- 前缀）：
        # 同参可复用缓存与远端附件；缓存文件异常时删除并按未命中重新渲染
        cache_key = f"{digest}-{render_suffix}"
        cached_path = cache_dir / f"{cache_key}.png" if cache_dir else None
        cache_hit = cached_path is not None and cached_path.is_file() and cached_path.stat().st_size > 0
        if cache_hit:
            try:
                png_dimensions(cached_path)
            except RuntimeError:
                cached_path.unlink(missing_ok=True)
                cache_hit = False
        if cache_hit:
            shutil.copyfile(cached_path, image_path)
        else:
            render_command = [
                *command,
                "-i",
                str(source_path),
                "-o",
                str(image_path),
                "-b",
                MERMAID_BACKGROUND,
            ]
            render_command.extend(("--scale", scale_key))
            result = subprocess.run(
                render_command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=90,
            )
            if result.returncode != 0 or not image_path.is_file() or image_path.stat().st_size == 0:
                detail = (result.stderr or result.stdout).strip()
                hint = mermaid_runtime_hint(env)
                if hint:
                    detail = f"{detail}\n{hint}" if detail else hint
                raise RuntimeError(f"failed to render mermaid diagram {index}: {detail[:1000] or 'renderer produced no image'}")
            png_dimensions(image_path)
            if cached_path is not None:
                cached_path.parent.mkdir(parents=True, exist_ok=True)
                temp_cache = cached_path.with_suffix(cached_path.suffix + ".tmp")
                shutil.copyfile(image_path, temp_cache)
                os.replace(temp_cache, cached_path)

        diagram = RenderedMermaid(attachment_filename=image_path.name, image_path=image_path)
        rendered_by_digest[digest] = diagram
        rendered.append(diagram)
    return rendered


def lint_markdown_text(
    markdown_text: str,
    template_name: str = "baseline",
    check_table_headers: bool = True,
) -> list[str]:
    template = normalize_template_name(template_name)
    if template == "raw":
        # raw 模式不校验任何格式：任意本地 Markdown 直接发布
        return []
    issues: list[str] = []
    normalized = normalize_newlines(markdown_text)

    if "section_key" in normalized or "template_name" in normalized or "authoring_mode" in normalized:
        issues.append("template contains machine-only metadata; remove section_key/template_name/authoring_mode style fields")

    if strip_html_comments(normalized) != normalized:
        issues.append("document contains HTML comment lines (template guidance); remove them from the deliverable")

    # 模板文档必须以一级标题（主标题）开头：本地保留，推送时由页面标题取代
    if extract_main_title(normalized) is None:
        issues.append("missing main title: start the document with a level-1 heading (e.g. `# <文档名>`)")

    # 标注「未涉及/不涉及」的章节（含其子章节）豁免子标题与表头校验
    doc_bodies = doc_heading_bodies(normalized)

    for heading in template_headings(template):
        if heading in normalized:
            continue
        if template_requirement_exempt(heading, template, doc_bodies):
            continue
        issues.append(f"missing required heading: {heading}")

    if check_table_headers:
        for table_header in template_table_headers(template):
            if table_header in normalized:
                continue
            if template_requirement_exempt(table_header, template, doc_bodies):
                continue
            issues.append(f"missing required table header: {table_header}")

    required_level1 = {h for h in template_headings(template) if h.startswith("# ") and not h.startswith("## ")}
    present_level1 = {
        line.strip()
        for line in normalized.split("\n")
        if line.strip().startswith("# ") and not line.strip().startswith("## ")
    }
    unexpected = present_level1 - required_level1
    main_title = extract_main_title(normalized)
    if main_title:
        unexpected.discard(main_title)  # 主标题保留在本地 md，不视为多余章节
    for heading in sorted(unexpected):
        issues.append(f"unexpected top-level heading: {heading}")

    return issues


def warn_lint_issues(issues: list[str]) -> None:
    """Advisory template-structure warnings for publish paths (non-blocking)."""
    print("WARNING: document deviates from template structure; proceeding", file=sys.stderr)
    for issue in issues:
        print(f"  - {issue}", file=sys.stderr)


def cmd_lint_doc(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        return error(f"markdown file not found: {input_path}")
    markdown_text = read_text(input_path)
    issues = lint_markdown_text(markdown_text, resolve_template(args))
    issues.extend(markdown_conversion_issues(markdown_text))
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print("OK")
    return 0


def cmd_init_template(args: argparse.Namespace) -> int:
    template = resolve_template(args)
    if template == "raw":
        return error("raw is the default and has no template file; pass --template baseline or 1-n to generate from a template, or create the markdown file directly")
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.force:
        return error(f"output file exists: {output}")
    # 模板中的指引注释只留在模板源文件，生成文档不允许携带
    write_text(output, strip_html_comments(read_text(get_template_file(template))))
    print(output)
    return 0


def extract_section_bounds(lines: list[str], heading: str) -> tuple[int, int]:
    start = -1
    prefix_level = len(heading) - len(heading.lstrip("#"))
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index
            break
    if start < 0:
        raise ValueError(f"heading not found: {heading}")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index].strip()
        if not line.startswith("#"):
            continue
        level = len(line) - len(line.lstrip("#"))
        if level <= prefix_level:
            end = index
            break
    return start, end


def merge_sections(source_text: str, patch_data: dict) -> str:
    lines = normalize_newlines(source_text).split("\n")
    for logical_name, content in patch_data.items():
        if logical_name not in ALLOWED_CLEAR_TARGETS:
            raise ValueError(f"unsupported merge target: {logical_name}")
        heading = ALLOWED_CLEAR_TARGETS[logical_name]
        start, end = extract_section_bounds(lines, heading)
        replacement = [heading, ""]
        replacement.extend(normalize_newlines(content).strip("\n").split("\n"))
        replacement.append("")
        lines = lines[:start] + replacement + lines[end:]
    merged = "\n".join(lines).strip() + "\n"
    return merged


def cmd_merge_clear(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    patch_path = Path(args.patch).resolve()
    output_path = Path(args.output).resolve() if args.output else input_path

    if not input_path.exists():
        return error(f"markdown file not found: {input_path}")
    if not patch_path.exists():
        return error(f"patch file not found: {patch_path}")
    # merge-clear 只支持基线模板，缺省即 baseline，不随全局默认（raw）变化
    template = resolve_template(args, fallback="baseline")
    if template != "baseline":
        return error("merge-clear only supports the baseline template")

    patch_data = json.loads(read_text(patch_path))
    if not isinstance(patch_data, dict):
        return error("patch json must be an object mapping section names to markdown fragments")

    merged = merge_sections(read_text(input_path), patch_data)
    # merge-clear 为整章替换语义，章节内嵌模板表头可能被 patch 覆盖；只校验标题结构
    issues = lint_markdown_text(merged, template, check_table_headers=False)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1

    write_text(output_path, merged)
    print(str(output_path))
    return 0


# ==== Markdown → Confluence storage（CommonMark/GFM AST 渲染） ====
#
# 以 markdown-it-py 将 Markdown 解析为结构化 token 流，再映射为 Confluence
# storage XHTML。解析正确性（嵌套链接、转义、列表、表格、围栏等）由
# CommonMark/GFM 实现保证；本层只负责"节点 → storage"映射与平台能力边界
# （协议白名单、raw HTML 白名单、Mermaid 附件、代码宏语言）。

# 裸 URL 自动链接（仅 text token，链接内部不二次包裹）；URL 字符类排除空白、
# HTML 特殊符、引号及 CJK/全角标点（中文正文中 URL 后常紧跟中文，防止把正文
# 吞进链接），结尾剩余的 ASCII 句读符号在链接时剥离
_BARE_URL_RE = re.compile(
    r"(?<![\w])https?://[^\s<>\"'`\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+",
    re.IGNORECASE,
)
_BARE_URL_TRAILING = ".,;:!?)]"
# 标记性实体（&lt;/&gt; 等）在比较归一化时保持原样，避免"转义文本"与"真实标签"误判等价
_MARKUP_ENTITY_RE = re.compile(r"&(?:lt|gt|amp|quot|apos|#\d+;|#x[0-9a-fA-F]+;)")
# Confluence 保存 span 标注时把十六进制颜色规范化为 rgb() 形式，比较时归一化回 hex
_RGB_COLOR_RE = re.compile(r"color: rgb\((\d+),\s*(\d+),\s*(\d+)\);?")
_HTML_TAG_NAME_RE = re.compile(r"</?([A-Za-z][\w:-]*)(?:\s[^>]*)?/?>")
# raw HTML 白名单（标注色块 span、换行、下划线/上下标）；白名单外一律转义为可见文本
_SUPPORTED_INLINE_HTML_TAG_NAMES = {"span", "br", "u", "sub", "sup"}
_SAFE_LINK_PROTOCOLS = {"http", "https", "mailto"}
# 文本层兜底识别被解析器拒绝的 [x](scheme:...) 链接形态（scheme 白名单外的协议）
_LINK_SCHEME_TEXT_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([A-Za-z][A-Za-z0-9+.-]*):")
# 该 wiki 底层存储不支持补充平面字符（emoji 等，实测 500），发布前按行阻断
_ASTRAL_CHAR_RE = re.compile(r"[\U00010000-\U0010FFFF]")


def escape_attr_value(value: str) -> str:
    """HTML 属性值转义（双引号包裹场景）。"""
    return html.escape(value, quote=True)


def is_safe_link_url(url: str) -> bool:
    """链接/图片目标协议白名单：http/https/mailto 与相对路径/锚点；javascript: 等拒绝。"""
    stripped = url.strip()
    if not stripped or stripped.startswith("#"):
        return True
    scheme = urllib.parse.urlsplit(stripped).scheme.lower()
    return scheme in _SAFE_LINK_PROTOCOLS or scheme == ""


def render_raw_html(raw: str) -> str:
    """raw HTML：HTML 注释剔除；白名单标签原样透传；其余转义为可见文本。"""
    stripped = raw.strip()
    if stripped.startswith("<!--"):
        return ""
    tag_match = _HTML_TAG_NAME_RE.match(stripped)
    if tag_match and tag_match.group(1).lower() in _SUPPORTED_INLINE_HTML_TAG_NAMES:
        return raw
    return html.escape(raw, quote=False)


def render_code_macro(code: str, language: str | None) -> str:
    """代码宏（保留围栏语言信息）；CDATA 终止符 ]]> 按标准拆分转义。"""
    code = code.replace("]]>", "]]]]><![CDATA[>")
    language_param = (
        f'<ac:parameter ac:name="language">{html.escape(language, quote=True)}</ac:parameter>'
        if language
        else ""
    )
    return (
        '<ac:structured-macro ac:name="code">'
        f"{language_param}"
        '<ac:parameter ac:name="theme">Emacs</ac:parameter>'
        f'<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>'
        "</ac:structured-macro>"
    )


def render_code_for_paste(code: str, language: str | None) -> str:
    del language
    return f"<pre><code>{html.escape(code)}</code></pre>"


def render_attachment_image(filename: str, width: int | None = None) -> str:
    attachment = f'<ri:attachment ri:filename="{html.escape(filename, quote=True)}" />'
    if width and width > 0:
        return f'<ac:image ac:width="{int(width)}">{attachment}</ac:image>'
    return f"<ac:image>{attachment}</ac:image>"


def linkify_text_token(content: str, *, in_link: bool) -> str:
    """text token 内裸 URL 自动链接；链接内部（in_link）不二次包裹。"""
    escaped = html.escape(content, quote=False)
    if in_link:
        return escaped
    parts: list[str] = []
    pos = 0
    for match in _BARE_URL_RE.finditer(escaped):
        parts.append(escaped[pos : match.start()])
        url = match.group(0).rstrip(_BARE_URL_TRAILING)
        parts.append(f'<a href="{escape_attr_value(url)}">{url}</a>')
        pos = match.end()
    parts.append(escaped[pos:])
    return "".join(parts)


def render_inline(tokens: list) -> str:
    """inline token 子节点 → storage 行内 XHTML。"""
    out: list[str] = []
    link_depth = 0
    for token in tokens:
        token_type = token.type
        if token_type == "text":
            out.append(linkify_text_token(token.content, in_link=link_depth > 0))
        elif token_type == "text_special":
            out.append(html.escape(token.content, quote=False))
        elif token_type == "code_inline":
            out.append(f"<code>{html.escape(token.content, quote=False)}</code>")
        elif token_type == "softbreak":
            out.append("\n")
        elif token_type == "hardbreak":
            out.append("<br />")
        elif token_type == "em_open":
            out.append("<em>")
        elif token_type == "em_close":
            out.append("</em>")
        elif token_type == "strong_open":
            out.append("<strong>")
        elif token_type == "strong_close":
            out.append("</strong>")
        elif token_type == "s_open":
            # Confluence 编辑器对删除线的存储表达是 line-through 的 span
            out.append('<span style="text-decoration: line-through;">')
        elif token_type == "s_close":
            out.append("</span>")
        elif token_type == "link_open":
            href = token.attrGet("href") or ""
            if is_safe_link_url(href):
                out.append(f'<a href="{escape_attr_value(href)}"')
                title = token.attrGet("title")
                if title:
                    out.append(f' title="{escape_attr_value(title)}"')
                out.append(">")
                link_depth += 1
            # 不安全协议：链接整体按普通文本输出，不生成锚点（由 gate 另行告警）
        elif token_type == "link_close":
            if link_depth:
                out.append("</a>")
                link_depth -= 1
        elif token_type == "image":
            src = token.attrGet("src") or ""
            if src.startswith(("http://", "https://")):
                out.append(f'<ac:image><ri:url ri:value="{escape_attr_value(src)}"/></ac:image>')
            else:
                out.append(f'<a href="{escape_attr_value(src)}">{html.escape(token.content or "", quote=False)}</a>')
        elif token_type == "html_inline":
            out.append(render_raw_html(token.content))
        else:
            out.append(token.content)
    return "".join(out)


def render_block_tokens(
    tokens: list,
    mermaid_images: list[str] | None = None,
    image_width: int | list[int] | None = None,
    code_renderer=None,
) -> str:
    """token 流 → storage XHTML。

    mermaid 围栏按出现顺序映射附件文件名；文档开头第一个一级标题视为本地
    主标题剔除（wiki 页面标题取代之）。
    """
    out: list[str] = []
    containers: list[str] = []
    mermaid_index = 0
    skip_head = bool(tokens) and tokens[0].type == "heading_open" and tokens[0].tag == "h1"
    block_code_renderer = code_renderer or render_code_macro

    for token in tokens:
        token_type = token.type
        if skip_head:
            if token_type == "heading_close":
                skip_head = False
            continue
        if token_type == "inline":
            rendered = render_inline(token.children or [])
            top = containers[-1] if containers else ""
            if top in ("th", "td"):
                out.append(f"<p>{rendered}</p>")
            elif top in ("li", "p", "h1", "h2", "h3", "h4", "h5", "h6"):
                out.append(rendered)
            else:
                out.append(f"<p>{rendered}</p>")
            continue
        if token_type == "heading_open":
            out.append(f"<{token.tag}>")
            containers.append(token.tag)
            continue
        if token_type == "ordered_list_open":
            start = token.attrGet("start")
            attrs = f' start="{int(start)}"' if start and int(start) != 1 else ""
            out.append(f"<ol{attrs}>")
            containers.append("ol")
            continue
        if token_type == "bullet_list_open":
            out.append("<ul>")
            containers.append("ul")
            continue
        if token_type == "list_item_open":
            out.append("<li>")
            containers.append("li")
            continue
        if token_type in ("paragraph_open", "blockquote_open", "tr_open"):
            if not getattr(token, "hidden", False):
                out.append(f"<{token.tag}>")
            containers.append(token.tag)
            continue
        if token_type in ("th_open", "td_open"):
            tag = "th" if token_type == "th_open" else "td"
            style = token.attrGet("style")
            attrs = f' style="{style}"' if style else ""
            out.append(f"<{tag}{attrs}>")
            containers.append(tag)
            continue
        if token_type == "table_open":
            out.append("<table><tbody>")
            containers.append("table")
            continue
        if token_type in ("thead_open", "tbody_open"):
            containers.append(token_type[:-5])  # thead/tbody 占位对齐，不输出标签
            continue
        if token_type == "hr":
            out.append("<hr />")
            continue
        if token_type == "fence":
            info = token.info.strip().lower()
            if info.startswith("mermaid") and mermaid_images is not None:
                if mermaid_index >= len(mermaid_images):
                    raise ValueError("missing rendered Mermaid attachment")
                width = image_width[mermaid_index] if isinstance(image_width, list) else image_width
                out.append(render_attachment_image(mermaid_images[mermaid_index], width))
                mermaid_index += 1
            else:
                language = token.info.split()[0] if token.info.strip() else None
                out.append(block_code_renderer(token.content, language))
            continue
        if token_type == "code_block":
            out.append(block_code_renderer(token.content, None))
            continue
        if token_type == "html_block":
            rendered = render_raw_html(token.content)
            if rendered:
                out.append(rendered if rendered.startswith("<") else f"<p>{rendered}</p>")
            continue
        if token_type == "image":
            out.append(f"<p>{render_inline([token])}</p>")
            continue
        if token_type.endswith("_close"):
            if token_type == "table_close":
                out.append("</tbody></table>")
            elif token_type in ("thead_close", "tbody_close"):
                pass
            elif token_type == "paragraph_close" and getattr(token, "hidden", False):
                pass
            else:
                out.append(f"</{token.tag}>")
            if containers:
                containers.pop()
            continue
    if mermaid_images is not None and mermaid_index != len(mermaid_images):
        raise ValueError("unused rendered Mermaid attachments")
    return "".join(out)


def encode_supplementary_plane(value: str) -> str:
    """补充平面字符（U+10000 以上）替换为安全占位。

    该 wiki 底层存储不支持 4 字节 UTF-8：实测直接提交或实体形式（&#x...;）都会
    HTTP 500（Confluence 保存时解码实体后仍撞数据库限制）。发布前由 gate 按行
    阻断并提示，此处兜底替换避免任何路径把非法字符提交到远端。
    """
    return re.sub(r"[\U00010000-\U0010FFFF]", "□", value)


def markdown_to_storage(
    markdown_text: str,
    mermaid_images: list[str] | None = None,
    image_width: int | list[int] | None = None,
) -> str:
    tokens = parse_markdown(markdown_text)
    return encode_supplementary_plane(render_block_tokens(tokens, mermaid_images, image_width))


def markdown_to_paste_html(markdown_text: str) -> str:
    tokens = parse_markdown(markdown_text)
    body = render_block_tokens(tokens, code_renderer=render_code_for_paste)
    return "<html><body>" + body + "</body></html>"


def markdown_conversion_issues(markdown_text: str) -> list[str]:
    """返回会被渲染层降级/阻断的构造清单（publish/paste/lint 前调用，含行号）。"""
    issues: list[str] = []

    def add(line_number: int | None, message: str) -> None:
        issue = f"line {line_number}: {message}" if line_number else message
        if issue not in issues:
            issues.append(issue)

    def walk(tokens: list, line_number: int | None = None) -> None:
        for token in tokens:
            token_line = token.map[0] + 1 if token.map else line_number
            token_type = token.type
            if token_type in ("html_inline", "html_block"):
                stripped = token.content.strip()
                if not stripped.startswith("<!--"):
                    tag_match = _HTML_TAG_NAME_RE.match(stripped)
                    tag = tag_match.group(1) if tag_match else None
                    if not (tag and tag.lower() in _SUPPORTED_INLINE_HTML_TAG_NAMES):
                        add(token_line, f"raw HTML tag `{tag or '?'}` is not supported")
            elif token_type == "link_open":
                href = token.attrGet("href") or ""
                if not is_safe_link_url(href):
                    scheme = urllib.parse.urlsplit(href.strip()).scheme.lower()
                    add(token_line, f"link protocol `{scheme}` is not allowed")
            elif token_type == "image":
                src = token.attrGet("src") or ""
                if src.startswith(("http://", "https://")):
                    pass
                elif not is_safe_link_url(src):
                    scheme = urllib.parse.urlsplit(src.strip()).scheme.lower()
                    add(token_line, f"image protocol `{scheme}` is not allowed")
                else:
                    add(token_line, "local images are not supported; use an HTTPS URL")
            elif token_type == "text":
                # markdown-it 原生拒绝不安全协议的链接（不产生 link token），
                # 从文本层兜底识别 [x](javascript:...) 形态
                for scheme_match in _LINK_SCHEME_TEXT_RE.finditer(token.content):
                    scheme = scheme_match.group(1).lower()
                    if scheme not in _SAFE_LINK_PROTOCOLS and scheme != "":
                        add(token_line, f"link protocol `{scheme}` is not allowed")
                        break
                if _ASTRAL_CHAR_RE.search(token.content):
                    add(token_line, "emoji/supplementary-plane characters are not supported by this wiki")
            elif token_type in ("fence", "code_block"):
                if _ASTRAL_CHAR_RE.search(token.content):
                    add(token_line, "emoji/supplementary-plane characters are not supported by this wiki")
            if token_type == "inline" and token.children:
                walk(token.children, token_line)

    walk(parse_markdown(markdown_text))
    return issues


def conversion_error_message(issues: list[str]) -> str:
    return "unsupported Markdown syntax would be rendered incorrectly:\n" + "\n".join(
        f"  - {issue}" for issue in issues
    )


def cmd_prepare_paste_html(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        return error(f"markdown file not found: {input_path}")

    markdown_text = read_text(input_path)
    compatibility_issues = markdown_conversion_issues(markdown_text)
    if compatibility_issues:
        return error(conversion_error_message(compatibility_issues))
    issues = lint_markdown_text(markdown_text, resolve_template(args))
    if issues:
        warn_lint_issues(issues)

    output_path = Path(args.output).resolve() if args.output else input_path.with_suffix(".paste.html")
    write_text(output_path, markdown_to_paste_html(markdown_text))
    print(output_path)
    return 0


def cmd_check_page(args: argparse.Namespace) -> int:
    try:
        config = load_runtime_config(args)
        page = fetch_page(config)
    except Exception as exc:
        return error(str(exc))
    print(json.dumps({"id": page["id"], "title": page["title"], "version": page["version"]["number"]}, ensure_ascii=False))
    return 0


def cmd_upload_attachment(args: argparse.Namespace) -> int:
    file_path = Path(args.file).resolve()
    if not file_path.is_file():
        return error(f"attachment file not found: {file_path}")
    try:
        config = load_runtime_config(args)
        attachment = upload_attachment(config, file_path)
    except Exception as exc:
        return error(str(exc))
    print(json.dumps({"id": attachment["id"], "title": attachment["title"]}, ensure_ascii=False))
    return 0


@dataclass
class _PageUpdate:
    """页面更新结果：response 为 PUT 响应，None 表示内容等价未更新。"""
    response: dict | None
    page: dict
    title: str


def _sync_mermaid_attachments(config: RuntimeConfig, diagrams: list[RenderedMermaid]) -> set[str]:
    """上传页面缺失的同名 Mermaid 附件；并发下重复上传按 HTTP 400 幂等跳过。"""
    if not diagrams:
        return set()
    existing_attachment_titles = fetch_attachment_titles(config)
    uploaded_filenames: set[str] = set()
    for diagram in diagrams:
        filename = diagram.attachment_filename
        if filename in existing_attachment_titles or filename in uploaded_filenames:
            continue
        try:
            upload_attachment(config, diagram.image_path)
        except RuntimeError as exc:
            if not is_duplicate_attachment_error(exc):
                raise
            refreshed_titles = fetch_attachment_titles(config)
            if filename not in refreshed_titles:
                raise
            existing_attachment_titles.update(refreshed_titles)
            continue
        uploaded_filenames.add(filename)
    return uploaded_filenames


def _update_page(
    config: RuntimeConfig,
    page: dict,
    requested_title: str | None,
    storage_html: str,
) -> _PageUpdate:
    """并发安全更新页面：重读最新版本；内容等价时短路不 bump 版本；409 冲突重试一次。"""
    for attempt in range(2):
        fresh = fetch_page(config)
        title = requested_title or fresh["title"]
        next_version = int(fresh["version"]["number"]) + 1
        current_storage = (fresh.get("body", {}).get("storage") or {}).get("value") or ""
        if title == fresh.get("title") and normalize_storage_for_compare(storage_html) == normalize_storage_for_compare(current_storage):
            return _PageUpdate(response=None, page=fresh, title=title)
        endpoint = f"{config.base_url.rstrip('/')}/rest/api/content/{config.page_id}"
        payload = {
            "id": fresh["id"],
            "type": fresh["type"],
            "title": title,
            "version": {"number": next_version},
            "body": {"storage": {"value": storage_html, "representation": "storage"}},
        }
        if fresh.get("space", {}).get("key"):
            payload["space"] = {"key": fresh["space"]["key"]}
        try:
            return _PageUpdate(response=request_json("PUT", endpoint, config.headers, payload), page=fresh, title=title)
        except RuntimeError as exc:
            if attempt == 1 or not is_page_version_conflict(exc):
                raise
    raise AssertionError("unreachable")


def cmd_publish_md(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        return error(f"markdown file not found: {input_path}")

    template = resolve_template(args)
    markdown_text = read_text(input_path)
    compatibility_issues = markdown_conversion_issues(markdown_text)
    if compatibility_issues:
        return error(conversion_error_message(compatibility_issues))
    issues = lint_markdown_text(markdown_text, template)
    if issues:
        warn_lint_issues(issues)

    try:
        config = load_runtime_config(args)
        page = fetch_page(config)
        # 页面标题：--title > 文档主标题（正文第一个一级标题，去掉 # 前缀）> 页面现有标题。
        # 发布过程可能因并发重读页面；未显式指定标题时始终保留最新页面标题。
        main_title = extract_main_title(markdown_text)
        requested_title = args.title or (main_title[2:].strip() if main_title else "")
        title = requested_title or page["title"]
        next_version = int(page["version"]["number"]) + 1
        cache_dir = Path(
            os.environ.get("TIANYIN_WIKI_CACHE_DIR", Path.home() / ".cache" / "tianyin-wiki" / "mermaid")
        )
        with tempfile.TemporaryDirectory(prefix="tianyin-mermaid-") as temp_dir:
            diagrams = render_mermaid_diagrams(
                markdown_text,
                Path(temp_dir),
                args.mermaid_scale,
                cache_dir,
            )
            if args.image_width is None:
                image_widths: list[int | None] = [diagram_image_width(diagram.image_path) for diagram in diagrams]
            else:
                image_widths = [args.image_width] * len(diagrams)
            storage_html = markdown_to_storage(
                markdown_text,
                [diagram.attachment_filename for diagram in diagrams],
                image_widths,
            )
            # 写入前打印目标页与版本变化；--dry-run 只读到这一步，不做任何写入
            print(
                f"publishing: {page.get('title', '')} (page {page['id']}, "
                f"version {page['version']['number']} -> {next_version})",
                file=sys.stderr,
            )
            if args.dry_run:
                print(json.dumps({
                    "dryRun": True,
                    "id": page["id"],
                    "title": title,
                    "version": page["version"]["number"],
                    "nextVersion": next_version,
                    "template": template,
                    "mermaidAttachments": len(diagrams),
                    "storageLength": len(storage_html),
                }, ensure_ascii=False))
                return 0
            uploaded_filenames = _sync_mermaid_attachments(config, diagrams)
            update = _update_page(config, page, requested_title, storage_html)
    except Exception as exc:
        return error(str(exc))

    if update.response is None:
        print(json.dumps({
            "noChanges": True,
            "id": update.page["id"],
            "title": update.title,
            "version": update.page["version"]["number"],
            "template": template,
            "mermaidAttachments": len({d.attachment_filename for d in diagrams}),
            "uploadedAttachments": len(uploaded_filenames),
        }, ensure_ascii=False))
        return 0
    print(json.dumps({
        "id": update.response["id"],
        "title": update.response["title"],
        "version": update.response["version"]["number"],
        "template": template,
        "mermaidAttachments": len({d.attachment_filename for d in diagrams}),
        "uploadedAttachments": len(uploaded_filenames),
    }, ensure_ascii=False))
    return 0


def add_template_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--template",
        choices=tuple(TEMPLATE_ALIASES),
        default=None,
        help=(
            "template mode: raw (default; push any markdown without structure "
            "validation), baseline, 1-n, or default (= baseline, for generating "
            "local design docs only); config `template` accepts baseline/1-n only; "
            "omitted values fall back to config, then raw; init-template requires "
            "an explicit baseline/1-n/default"
        ),
    )


def add_auth_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--username")
    parser.add_argument("--password")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tianyin wiki CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init-template")
    init_parser.add_argument("--output", required=True)
    add_template_argument(init_parser)
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=cmd_init_template)

    lint_parser = sub.add_parser("lint-doc")
    lint_parser.add_argument("--input", required=True)
    add_template_argument(lint_parser)
    lint_parser.set_defaults(func=cmd_lint_doc)

    paste_parser = sub.add_parser("prepare-paste-html")
    paste_parser.add_argument("--input", required=True)
    paste_parser.add_argument("--output")
    add_template_argument(paste_parser)
    paste_parser.set_defaults(func=cmd_prepare_paste_html)

    merge_parser = sub.add_parser("merge-clear")
    merge_parser.add_argument("--input", required=True)
    merge_parser.add_argument("--patch", required=True)
    merge_parser.add_argument("--output")
    add_template_argument(merge_parser)
    merge_parser.set_defaults(func=cmd_merge_clear)

    check_parser = sub.add_parser("check-page")
    check_parser.add_argument("--remote-url")
    add_auth_arguments(check_parser)
    check_parser.set_defaults(func=cmd_check_page)

    upload_parser = sub.add_parser("upload-attachment")
    upload_parser.add_argument("--file", required=True)
    upload_parser.add_argument("--remote-url")
    add_auth_arguments(upload_parser)
    upload_parser.set_defaults(func=cmd_upload_attachment)

    doctor_parser = sub.add_parser("doctor")
    doctor_parser.add_argument("--input", help="optional Markdown file to count Mermaid blocks")
    doctor_parser.add_argument(
        "--refresh-runtime",
        action="store_true",
        help="ignore cached Mermaid/browser probes and rewrite the runtime cache",
    )
    doctor_parser.set_defaults(func=cmd_doctor)

    publish_parser = sub.add_parser("publish-md")
    publish_parser.add_argument("--input", required=True)
    publish_parser.add_argument("--remote-url")
    publish_parser.add_argument("--title")
    add_template_argument(publish_parser)
    add_auth_arguments(publish_parser)

    publish_parser.add_argument("--mermaid-scale", type=float, default=3.0)
    publish_parser.add_argument(
        "--image-width",
        type=int,
        default=None,
        help="fixed Confluence image display width in px; default auto = half of intrinsic width, capped at 500; 0 disables explicit width",
    )
    publish_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read-only pre-check: fetch the target page and build the storage HTML without uploading attachments or updating the page",
    )
    publish_parser.set_defaults(func=cmd_publish_md)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        # ValueError 已覆盖 JSONDecodeError，OSError 已覆盖 FileNotFoundError；
        # KeyError 兜底 API 返回结构异常，统一转成一行错误而非堆栈
        return error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())

