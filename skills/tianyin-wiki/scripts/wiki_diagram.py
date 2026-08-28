from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from tianyin_wiki import png_dimensions, render_mermaid_diagrams


def markdown_with_mermaid(source: str) -> str:
    if "```mermaid" in source:
        return source
    return f"```mermaid\n{source.rstrip()}\n```\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render one Mermaid diagram locally")
    parser.add_argument("--input", required=True, help="Mermaid .mmd file or Markdown containing one Mermaid block")
    parser.add_argument("--output", required=True, help="PNG output path")
    parser.add_argument("--scale", type=float, default=3.0, help="PNG raster scale")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    if not input_path.is_file():
        print(f"input file not found: {input_path}", file=sys.stderr)
        return 1
    if output_path.suffix.lower() != ".png":
        print("output extension must be .png", file=sys.stderr)
        return 1

    source = markdown_with_mermaid(input_path.read_text(encoding="utf-8"))
    try:
        with tempfile.TemporaryDirectory(prefix="tianyin-diagram-") as temp_dir:
            diagrams = render_mermaid_diagrams(source, Path(temp_dir), args.scale)
            if len(diagrams) != 1:
                raise ValueError("input must contain exactly one Mermaid diagram")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(diagrams[0].image_path, output_path)
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    result = {
        "output": str(output_path),
        "format": "png",
        "bytes": output_path.stat().st_size,
        "dimensions": png_dimensions(output_path),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
