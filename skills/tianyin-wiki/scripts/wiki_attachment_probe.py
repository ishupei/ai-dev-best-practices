from __future__ import annotations

import argparse
import json
import sys

from tianyin_wiki import load_runtime_config, request_json


def main() -> int:
    parser = argparse.ArgumentParser(description="List Confluence page attachments without modifying the page")
    parser.add_argument("--remote-url")
    parser.add_argument("--filename")
    parser.add_argument("--limit", type=int, default=200, help="attachment API page size (default 200)")
    parser.add_argument("--username")
    parser.add_argument("--password")
    args = parser.parse_args()

    filename = (args.filename or "").strip()
    attachments = []
    try:
        config = load_runtime_config(args)
        limit = max(1, min(args.limit, 1000))
        base = f"{config.base_url.rstrip('/')}/rest/api/content/{config.page_id}/child/attachment"
        url: str | None = f"{base}?limit={limit}&expand=metadata,version"
        while url:
            response = request_json("GET", url, config.headers)
            results = response.get("results")
            if not isinstance(results, list):
                raise RuntimeError("attachment list returned an invalid response")
            for attachment in results:
                if not isinstance(attachment, dict):
                    continue
                title = str(attachment.get("title") or "")
                if filename and title != filename:
                    continue
                metadata = attachment.get("metadata") or {}
                version = attachment.get("version") or {}
                attachments.append({
                    "id": attachment.get("id"),
                    "title": title,
                    "mediaType": metadata.get("mediaType"),
                    "version": version.get("number"),
                })
            next_link = (response.get("_links") or {}).get("next")
            url = next_link if next_link and next_link.startswith("http") else (
                f"{config.base_url.rstrip('/')}{next_link}" if next_link else None
            )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"pageId": config.page_id, "attachments": attachments}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
