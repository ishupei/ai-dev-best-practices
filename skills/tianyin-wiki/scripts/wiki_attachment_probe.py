from __future__ import annotations

import argparse
import json
import sys

from tianyin_wiki import load_runtime_config, request_json


def main() -> int:
    parser = argparse.ArgumentParser(description="List Confluence page attachments without modifying the page")
    parser.add_argument("--remote-url")
    parser.add_argument("--filename")
    parser.add_argument("--auth-type", choices=("basic", "bearer", "none"))
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--token")
    args = parser.parse_args()

    try:
        config = load_runtime_config(args)
        endpoint = (
            f"{config.base_url.rstrip('/')}/rest/api/content/{config.page_id}"
            "/child/attachment?expand=metadata,version"
        )
        response = request_json("GET", endpoint, config.headers)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    filename = (args.filename or "").strip()
    attachments = []
    for attachment in response.get("results", []):
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
    print(json.dumps({"pageId": config.page_id, "attachments": attachments}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
