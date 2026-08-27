from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
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


ROOT = Path(__file__).resolve().parent.parent
# 个人配置文件统一存于用户配置目录（~/.config/tianyin-wiki），不随 skill 分发、不入版本库
DEFAULT_CONFIG_FILE = Path.home() / ".config" / "tianyin-wiki" / "config.json"
# 旧版本曾把个人配置放在用户目录 ~/.tianyin-wiki 或 skill 目录 scripts/ 下；保留兼容读取，仅用于提示迁移
LEGACY_CONFIG_FILES = (
    Path.home() / ".tianyin-wiki" / "config.json",
    ROOT / "scripts" / "tianyin-wiki.config.json",
)

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
    "1.方案背景": "## 1.方案背景",
    "2.需求评估表": "## 2.需求评估表",
    "4.需求功能点": "## 4.需求功能点",
    "5.业务流程设计": "## 5.业务流程设计",
    "6.业务功能设计": "## 6.业务功能设计",
    "7.数据库设计": "## 7.数据库设计",
    "8.安全设计": "## 8.安全设计",
    "9.交付运维影响": "## 9.交付运维影响",
    "11.1 风险点": "### 11.1 风险点",
    "11.2 回归测试": "### 11.2 回归测试",
}


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


def resolve_template(args: argparse.Namespace, fallback: str = "baseline") -> str:
    """Effective template: explicit CLI flag > config file `template` field > fallback."""
    config_data = load_config_file()
    value = getattr(args, "template", None) or config_data.get("template") or fallback
    return normalize_template_name(str(value).strip())


def get_template_file(template_name: str) -> Path:
    filename = TEMPLATE_FILES[normalize_template_name(template_name)]
    candidate = TEMPLATE_DIR / filename
    if candidate.is_file():
        return candidate
    # 兼容旧版：模板曾放在 skill 根目录
    legacy = ROOT / filename
    if legacy.is_file():
        return legacy
    raise FileNotFoundError(f"template file not found: {candidate}")


@lru_cache(maxsize=4)
def template_headings(template_name: str) -> list[str]:
    """Expected `## `/`### ` headings, derived from the template file (single source of truth)."""
    if normalize_template_name(template_name) == "raw":
        return []
    text = read_text(get_template_file(template_name))
    return [
        line.strip()
        for line in normalize_newlines(text).split("\n")
        if re.match(r"^#{2,3}\s+\S", line.strip())
    ]


@lru_cache(maxsize=4)
def template_heading_ancestors(template_name: str) -> dict[str, list[str]]:
    """Map each template heading to the chain of its ancestor headings (closest first)."""
    if normalize_template_name(template_name) == "raw":
        return {}
    lines = normalize_newlines(read_text(get_template_file(template_name))).split("\n")
    stack: list[tuple[int, str]] = []
    ancestors: dict[str, list[str]] = {}
    for line in lines:
        stripped = line.strip()
        if not re.match(r"^#{1,6}\s+\S", stripped):
            continue
        level = len(stripped) - len(stripped.lstrip("#"))
        while stack and stack[-1][0] >= level:
            stack.pop()
        ancestors[stripped] = [heading for _, heading in stack]
        stack.append((level, stripped))
    return ancestors


@lru_cache(maxsize=4)
def template_table_owners(template_name: str) -> dict[str, str]:
    """Map each required table header row to its nearest preceding template heading."""
    if normalize_template_name(template_name) == "raw":
        return {}
    lines = normalize_newlines(read_text(get_template_file(template_name))).split("\n")
    current: str | None = None
    mapping: dict[str, str] = {}
    for index, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+\S", stripped):
            current = stripped
        elif (
            current is not None
            and stripped.startswith("|")
            and index + 1 < len(lines)
            and is_table_separator(lines[index + 1])
        ):
            mapping[stripped] = current
    return mapping


@lru_cache(maxsize=4)
def template_table_headers(template_name: str) -> list[str]:
    """Expected Markdown table header rows, derived from the template file."""
    return list(template_table_owners(template_name))


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


def parse_remote_url(remote_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(remote_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"invalid remote url: {remote_url}")
    page_id = urllib.parse.parse_qs(parsed.query).get("pageId", [""])[0].strip()
    if not page_id:
        raise ValueError(f"remote url missing pageId: {remote_url}")
    return f"{parsed.scheme}://{parsed.netloc}", page_id


def build_headers(auth_type: str, username: str | None, password: str | None, token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if auth_type == "basic":
        if not username or not password:
            raise ValueError("basic auth requires username and password")
        encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {encoded}"
    elif auth_type == "bearer":
        if not token:
            raise ValueError("bearer auth requires token")
        headers["Authorization"] = f"Bearer {token}"
    return headers


@lru_cache(maxsize=1)
def load_config_file() -> dict:
    """Load the personal config file once per process (cached)."""
    config_path = os.environ.get("CONFLUENCE_CONFIG")
    if config_path:
        config_file = Path(config_path).expanduser().resolve()
    else:
        config_file = DEFAULT_CONFIG_FILE
    if not config_file.exists():
        # 兼容旧版：读取历史位置的个人配置并提示迁移到用户配置目录
        legacy_file = next((p for p in LEGACY_CONFIG_FILES if p.exists()), None)
        if legacy_file is not None:
            print(
                f"WARNING: {legacy_file} is deprecated; move it to {DEFAULT_CONFIG_FILE}",
                file=sys.stderr,
            )
            config_file = legacy_file
        else:
            return {}
    with config_file.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"config file must be a JSON object: {config_file}")
    return data


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
    config_data = load_config_file()
    remote_url = args.remote_url or config_remote_url(config_data)
    if not remote_url:
        raise ValueError("remote-url required; remote wiki operations must be explicitly requested")
    base_url, page_id = parse_remote_url(remote_url)
    return remote_url, base_url, page_id


def load_runtime_config(args: argparse.Namespace) -> RuntimeConfig:
    remote_url, base_url, page_id = load_remote_target(args)
    config_data = load_config_file()
    auth_type = args.auth_type or config_data.get("authType") or config_data.get("auth_type") or os.environ.get("CONFLUENCE_AUTH_TYPE") or "basic"
    username = args.username or config_data.get("username") or os.environ.get("CONFLUENCE_USERNAME")
    password = args.password or config_data.get("password") or os.environ.get("CONFLUENCE_PASSWORD")
    token = args.token or config_data.get("token") or os.environ.get("CONFLUENCE_TOKEN")
    headers = build_headers(auth_type, username, password, token)
    return RuntimeConfig(remote_url=remote_url, base_url=base_url, page_id=page_id, headers=headers)


def request_json(method: str, url: str, headers: dict[str, str], body: dict | None = None) -> dict:
    data = None
    request_headers = dict(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url=url, method=method, headers=request_headers, data=data)
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            response_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            response_body = ""
        detail = f"HTTP {exc.code} {exc.reason}"
        if response_body.strip():
            detail += f": {response_body}"
        raise RuntimeError(detail) from exc


def request_multipart_file(url: str, headers: dict[str, str], file_path: Path) -> dict:
    boundary = f"----TianyinWiki{uuid.uuid4().hex}"
    filename = file_path.name.replace("\\", "\\\\").replace('"', '\\"')
    content_type = "image/svg+xml" if file_path.suffix.lower() == ".svg" else (
        mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    )
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
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            response_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            response_body = ""
        detail = f"HTTP {exc.code} {exc.reason}"
        if response_body.strip():
            detail += f": {response_body}"
        raise RuntimeError(detail) from exc


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe_http(url: str, headers: dict[str, str]) -> dict:
    opener = urllib.request.build_opener(NoRedirectHandler)
    request = urllib.request.Request(url=url, headers=headers)
    try:
        with opener.open(request, timeout=15) as response:
            return {
                "status": response.status,
                "server": response.headers.get("Server", ""),
                "contentType": response.headers.get("Content-Type", ""),
                "location": response.headers.get("Location", ""),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "server": exc.headers.get("Server", ""),
            "contentType": exc.headers.get("Content-Type", ""),
            "location": exc.headers.get("Location", ""),
        }


def cmd_diagnose_auth(args: argparse.Namespace) -> int:
    config = load_runtime_config(args)
    urls = {
        "view": config.remote_url,
        "rest": f"{config.base_url.rstrip('/')}/rest/api/content/{config.page_id}?expand=version",
    }
    dummy_basic = "Basic " + base64.b64encode(b"x:y").decode("ascii")
    header_sets = {
        "no-auth": {"Accept": "application/json"},
        "configured-auth": config.headers,
        "dummy-basic": {"Accept": "application/json", "Authorization": dummy_basic},
        "dummy-bearer": {"Accept": "application/json", "Authorization": "Bearer dummy"},
    }
    result = {
        "remoteUrl": config.remote_url,
        "pageId": config.page_id,
        "checks": {
            url_name: {
                header_name: probe_http(url, headers)
                for header_name, headers in header_sets.items()
            }
            for url_name, url in urls.items()
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_get_login_url(args: argparse.Namespace) -> int:
    remote_url, _, _ = load_remote_target(args)
    result = probe_http(remote_url, {"Accept": "text/html"})
    location = str(result.get("location") or "").strip()
    if result.get("status") not in (301, 302, 303, 307, 308) or not location:
        raise RuntimeError(
            f"no browser login redirect found: HTTP {result.get('status')} "
            f"(Location: {location or 'missing'})"
        )
    print(json.dumps({
        "remoteUrl": remote_url,
        "loginUrl": urllib.parse.urljoin(remote_url, location),
    }, ensure_ascii=False))
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


def mermaid_blocks(markdown_text: str) -> list[str]:
    lines = normalize_newlines(markdown_text).split("\n")
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped.startswith("```") or stripped[3:].strip().lower() != "mermaid":
            i += 1
            continue
        i += 1
        code_lines: list[str] = []
        while i < len(lines) and not lines[i].strip().startswith("```"):
            code_lines.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError("unterminated mermaid code fence")
        blocks.append("\n".join(code_lines).strip())
        i += 1
    return blocks


def resolve_mermaid_command() -> list[str]:
    mmdc = shutil.which("mmdc") or shutil.which("mmdc.cmd")
    if mmdc:
        return [mmdc]
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx:
        return [npx, "--yes", "@mermaid-js/mermaid-cli"]
    raise RuntimeError("Mermaid renderer unavailable: install mmdc or npx")


def png_dimensions(png_path: Path) -> tuple[int, int]:
    data = png_path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("Mermaid renderer did not produce a valid PNG")
    return struct.unpack(">II", data[16:24])


def svg_width(svg_path: Path) -> int:
    """Extract the intrinsic width (px) from an SVG file.

    Returns 0 when the width cannot be resolved (caller then skips auto-sizing).
    """
    head = svg_path.read_text(encoding="utf-8", errors="replace")[:8192]
    match = re.search(r"<svg[^>]*\bwidth=\"(\d+(?:\.\d+)?)\"", head)
    if match:
        return max(1, int(float(match.group(1))))
    match = re.search(r"<svg[^>]*\bviewBox=\"\s*-?\d+\s+-?\d+\s+(\d+(?:\.\d+)?)", head)
    if match:
        return max(1, int(float(match.group(1))))
    return 0


def diagram_image_width(image_path: Path) -> int | None:
    """Auto display width: half the intrinsic width, capped at 500px.

    Returns None when the intrinsic width cannot be determined (no explicit width).
    """
    if image_path.suffix.lower() == ".png":
        original_width = png_dimensions(image_path)[0]
    elif image_path.suffix.lower() == ".svg":
        original_width = svg_width(image_path)
    else:
        original_width = 0
    if original_width <= 0:
        return None
    return min(original_width // 2, 500)


def render_mermaid_diagrams(
    markdown_text: str,
    image_format: str,
    output_dir: Path,
    raster_scale: float = 3.0,
) -> list[RenderedMermaid]:
    sources = mermaid_blocks(markdown_text)
    if not sources:
        return []
    if raster_scale <= 0:
        raise ValueError("mermaid raster scale must be greater than zero")

    command = resolve_mermaid_command()
    env = dict(os.environ)
    env.setdefault("PUPPETEER_SKIP_DOWNLOAD", "true")

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
        image_path = output_dir / f"tianyin-mermaid-{digest}.{image_format}"
        renderer_output = image_path
        write_text(source_path, source + "\n")
        render_command = [
            *command,
            "-i",
            str(source_path),
            "-o",
            str(renderer_output),
            "-b",
            "transparent",
        ]
        if image_format == "png":
            render_command.extend(("--scale", f"{raster_scale:g}"))
        result = subprocess.run(
            render_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=90,
        )
        if result.returncode != 0 or not renderer_output.is_file() or renderer_output.stat().st_size == 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"failed to render mermaid diagram {index}: {detail[:1000] or 'renderer produced no image'}")
        if image_format == "svg":
            svg_prefix = renderer_output.read_text(encoding="utf-8", errors="replace")[:4096]
            if not re.search(r"<svg\b", svg_prefix, flags=re.IGNORECASE):
                raise RuntimeError(f"Mermaid renderer did not produce a valid SVG for diagram {index}")

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

    required_level1 = {h for h in template_headings(template) if h.startswith("## ")}
    present_level1 = {
        line.strip()
        for line in normalized.split("\n")
        if line.strip().startswith("## ") and not line.strip().startswith("### ")
    }
    for heading in sorted(present_level1 - required_level1):
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
    issues = lint_markdown_text(read_text(input_path), resolve_template(args))
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    print("OK")
    return 0


def cmd_init_template(args: argparse.Namespace) -> int:
    template = resolve_template(args)
    if template == "raw":
        return error("raw mode has no template file; create the markdown file directly and publish it with publish-md --template raw")
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
    template = resolve_template(args)
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
    if output_path == input_path:
        print(str(output_path))
    else:
        print(str(output_path))
    return 0


def convert_inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and re.fullmatch(r"\|?[\s:\-|\t]+\|?", stripped) is not None


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def render_table(lines: list[str]) -> str:
    rows = [split_table_row(line) for line in lines if line.strip()]
    if len(rows) < 2:
        return "".join(f"<p>{convert_inline(line.strip())}</p>" for line in lines if line.strip())
    header = rows[0]
    body = rows[2:] if len(lines) > 1 and is_table_separator(lines[1]) else rows[1:]
    out = ["<table><tbody>"]
    out.append("<tr>" + "".join(f"<th><p>{convert_inline(cell)}</p></th>" for cell in header) + "</tr>")
    for row in body:
        padded = row + [""] * (len(header) - len(row))
        out.append("<tr>" + "".join(f"<td><p>{convert_inline(cell)}</p></td>" for cell in padded[: len(header)]) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def render_code(lines: list[str]) -> str:
    code = "\n".join(lines)
    return (
        '<ac:structured-macro ac:name="code">'
        '<ac:parameter ac:name="theme">Emacs</ac:parameter>'
        f'<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>'
        "</ac:structured-macro>"
    )


def render_code_for_paste(lines: list[str]) -> str:
    code = html.escape("\n".join(lines))
    return f"<pre><code>{code}</code></pre>"


def render_attachment_image(filename: str, width: int | None = None) -> str:
    attachment = f'<ri:attachment ri:filename="{html.escape(filename, quote=True)}" />'
    if width and width > 0:
        return f'<ac:image ac:width="{int(width)}">{attachment}</ac:image>'
    return f"<ac:image>{attachment}</ac:image>"


def render_list(lines: list[str]) -> str:
    stack: list[int] = []
    html_parts: list[str] = []
    tags: list[str] = []

    for raw in lines:
        indent = len(raw) - len(raw.lstrip(" "))
        level = indent // 2
        ordered = bool(re.match(r"^\s*\d+\.\s+", raw))
        tag = "ol" if ordered else "ul"
        content = re.sub(r"^\s*(?:-|\d+\.)\s+", "", raw.strip(), count=1)

        while stack and stack[-1] > level:
            html_parts.append("</li></" + tags.pop() + ">")
            stack.pop()
        if not stack or stack[-1] < level:
            html_parts.append(f"<{tag}><li>")
            stack.append(level)
            tags.append(tag)
        else:
            current_tag = tags[-1]
            if current_tag != tag:
                html_parts.append("</li></" + tags.pop() + ">")
                stack.pop()
                html_parts.append(f"<{tag}><li>")
                stack.append(level)
                tags.append(tag)
            else:
                html_parts.append("</li><li>")
        html_parts.append(convert_inline(content))

    while stack:
        html_parts.append("</li></" + tags.pop() + ">")
        stack.pop()
    return "".join(html_parts)


def markdown_to_storage(
    markdown_text: str,
    mermaid_images: list[str] | None = None,
    image_width: int | list[int] | None = None,
) -> str:
    lines = normalize_newlines(strip_html_comments(markdown_text)).split("\n")
    blocks: list[str] = []
    i = 0
    mermaid_index = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped == "---":
            blocks.append("<hr />")
            i += 1
            continue
        if stripped.startswith("```"):
            language = stripped[3:].strip().lower()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            if language == "mermaid" and mermaid_images is not None:
                if mermaid_index >= len(mermaid_images):
                    raise ValueError("missing rendered Mermaid attachment")
                width = image_width[mermaid_index] if isinstance(image_width, list) else image_width
                blocks.append(render_attachment_image(mermaid_images[mermaid_index], width))
                mermaid_index += 1
            else:
                blocks.append(render_code(code_lines))
            continue
        if stripped.startswith("#"):
            level = min(max(len(stripped) - len(stripped.lstrip("#")), 1), 6)
            title = stripped[level:].strip()
            blocks.append(f"<h{level}>{convert_inline(title)}</h{level}>")
            i += 1
            continue
        if stripped.startswith("|"):
            table_lines = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            blocks.append(render_table(table_lines))
            continue
        if re.match(r"^\s*(?:-|\d+\.)\s+", lines[i]):
            list_lines = [lines[i]]
            i += 1
            while i < len(lines) and (not lines[i].strip() or re.match(r"^\s*(?:-|\d+\.)\s+", lines[i])):
                if lines[i].strip():
                    list_lines.append(lines[i])
                i += 1
            blocks.append(render_list(list_lines))
            continue
        paragraph_lines = [lines[i].strip()]
        i += 1
        while i < len(lines):
            candidate = lines[i].strip()
            if not candidate or candidate.startswith("#") or candidate.startswith("|") or candidate == "---" or candidate.startswith("```") or re.match(r"^\s*(?:-|\d+\.)\s+", lines[i]):
                break
            paragraph_lines.append(candidate)
            i += 1
        blocks.append(f"<p>{convert_inline(' '.join(paragraph_lines))}</p>")
    if mermaid_images is not None and mermaid_index != len(mermaid_images):
        raise ValueError("unused rendered Mermaid attachments")
    return "".join(blocks)


def markdown_to_paste_html(markdown_text: str) -> str:
    lines = normalize_newlines(strip_html_comments(markdown_text)).split("\n")
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped == "---":
            blocks.append("<hr />")
            i += 1
            continue
        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            blocks.append(render_code_for_paste(code_lines))
            continue
        if stripped.startswith("#"):
            level = min(max(len(stripped) - len(stripped.lstrip("#")), 1), 6)
            title = stripped[level:].strip()
            blocks.append(f"<h{level}>{convert_inline(title)}</h{level}>")
            i += 1
            continue
        if stripped.startswith("|"):
            table_lines = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            blocks.append(render_table(table_lines))
            continue
        if re.match(r"^\s*(?:-|\d+\.)\s+", lines[i]):
            list_lines = [lines[i]]
            i += 1
            while i < len(lines) and (not lines[i].strip() or re.match(r"^\s*(?:-|\d+\.)\s+", lines[i])):
                if lines[i].strip():
                    list_lines.append(lines[i])
                i += 1
            blocks.append(render_list(list_lines))
            continue
        paragraph_lines = [lines[i].strip()]
        i += 1
        while i < len(lines):
            candidate = lines[i].strip()
            if not candidate or candidate.startswith("#") or candidate.startswith("|") or candidate == "---" or candidate.startswith("```") or re.match(r"^\s*(?:-|\d+\.)\s+", lines[i]):
                break
            paragraph_lines.append(candidate)
            i += 1
        blocks.append(f"<p>{convert_inline(' '.join(paragraph_lines))}</p>")
    return "<html><body>" + "".join(blocks) + "</body></html>"


def cmd_prepare_paste_html(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        return error(f"markdown file not found: {input_path}")

    markdown_text = read_text(input_path)
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


def cmd_publish_md(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        return error(f"markdown file not found: {input_path}")

    template = resolve_template(args)
    markdown_text = read_text(input_path)
    issues = lint_markdown_text(markdown_text, template)
    if issues:
        warn_lint_issues(issues)

    try:
        config = load_runtime_config(args)
        page = fetch_page(config)
        with tempfile.TemporaryDirectory(prefix="tianyin-mermaid-") as temp_dir:
            diagrams = render_mermaid_diagrams(
                markdown_text,
                args.mermaid_format,
                Path(temp_dir),
                args.mermaid_scale,
            )
            uploaded_filenames: set[str] = set()
            for diagram in diagrams:
                if diagram.attachment_filename not in uploaded_filenames:
                    upload_attachment(config, diagram.image_path)
                    uploaded_filenames.add(diagram.attachment_filename)
            if args.image_width is None:
                image_widths: list[int | None] = [diagram_image_width(diagram.image_path) for diagram in diagrams]
            else:
                image_widths = [args.image_width] * len(diagrams)
            storage_html = markdown_to_storage(
                markdown_text,
                [diagram.attachment_filename for diagram in diagrams],
                image_widths,
            )
            endpoint = f"{config.base_url.rstrip('/')}/rest/api/content/{config.page_id}"
            payload = {
                "id": page["id"],
                "type": page["type"],
                "title": args.title or page["title"],
                "version": {"number": int(page["version"]["number"]) + 1},
                "body": {"storage": {"value": storage_html, "representation": "storage"}},
            }
            if page.get("space", {}).get("key"):
                payload["space"] = {"key": page["space"]["key"]}
            response = request_json("PUT", endpoint, config.headers, payload)
    except Exception as exc:
        return error(str(exc))

    print(json.dumps({
        "id": response["id"],
        "title": response["title"],
        "version": response["version"]["number"],
        "template": template,
        "mermaidAttachments": len(uploaded_filenames),
    }, ensure_ascii=False))
    return 0


def add_template_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--template",
        choices=tuple(TEMPLATE_ALIASES),
        default=None,
        help=(
            "template mode: baseline (default), 1-n, or raw (push any markdown "
            "without structure validation); omitted values fall back to the "
            "config file `template` field"
        ),
    )


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
    check_parser.add_argument("--auth-type", choices=("basic", "bearer", "none"))
    check_parser.add_argument("--username")
    check_parser.add_argument("--password")
    check_parser.add_argument("--token")
    check_parser.set_defaults(func=cmd_check_page)

    upload_parser = sub.add_parser("upload-attachment")
    upload_parser.add_argument("--file", required=True)
    upload_parser.add_argument("--remote-url")
    upload_parser.add_argument("--auth-type", choices=("basic", "bearer", "none"))
    upload_parser.add_argument("--username")
    upload_parser.add_argument("--password")
    upload_parser.add_argument("--token")
    upload_parser.set_defaults(func=cmd_upload_attachment)

    diagnose_parser = sub.add_parser("diagnose-auth")
    diagnose_parser.add_argument("--remote-url")
    diagnose_parser.add_argument("--auth-type", choices=("basic", "bearer", "none"))
    diagnose_parser.add_argument("--username")
    diagnose_parser.add_argument("--password")
    diagnose_parser.add_argument("--token")
    diagnose_parser.set_defaults(func=cmd_diagnose_auth)

    login_url_parser = sub.add_parser("get-login-url")
    login_url_parser.add_argument("--remote-url")
    login_url_parser.set_defaults(func=cmd_get_login_url)

    publish_parser = sub.add_parser("publish-md")
    publish_parser.add_argument("--input", required=True)
    publish_parser.add_argument("--remote-url")
    publish_parser.add_argument("--title")
    add_template_argument(publish_parser)
    publish_parser.add_argument("--auth-type", choices=("basic", "bearer", "none"))
    publish_parser.add_argument("--username")
    publish_parser.add_argument("--password")
    publish_parser.add_argument("--token")
    publish_parser.add_argument("--mermaid-format", choices=("svg", "png"), default="png")
    publish_parser.add_argument("--mermaid-scale", type=float, default=3.0)
    publish_parser.add_argument(
        "--image-width",
        type=int,
        default=None,
        help="fixed Confluence image display width in px; default auto = half of intrinsic width, capped at 500; 0 disables explicit width",
    )
    publish_parser.set_defaults(func=cmd_publish_md)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ValueError, RuntimeError, FileNotFoundError, json.JSONDecodeError) as exc:
        return error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
