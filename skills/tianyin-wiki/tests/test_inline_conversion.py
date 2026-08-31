from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tianyin_wiki.py"
SPEC = importlib.util.spec_from_file_location("tianyin_wiki", MODULE_PATH)
assert SPEC and SPEC.loader
tianyin_wiki = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tianyin_wiki
SPEC.loader.exec_module(tianyin_wiki)


class BareUrlAutolinkTest(unittest.TestCase):
    def test_bare_url_becomes_anchor(self) -> None:
        text = "详见 https://alidocs.dingtalk.com/i/nodes/abc 页面"
        self.assertEqual(
            tianyin_wiki.convert_inline(text),
            '详见 <a href="https://alidocs.dingtalk.com/i/nodes/abc">https://alidocs.dingtalk.com/i/nodes/abc</a> 页面',
        )

    def test_bare_url_escaped_ampersand(self) -> None:
        text = "https://www.figma.com/design/abc?node-id=1&p=f"
        self.assertEqual(
            tianyin_wiki.convert_inline(text),
            '<a href="https://www.figma.com/design/abc?node-id=1&amp;p=f">https://www.figma.com/design/abc?node-id=1&amp;p=f</a>',
        )

    def test_bare_url_trailing_punctuation_stripped(self) -> None:
        text = "打开 https://example.com/foo。下一页"
        self.assertEqual(
            tianyin_wiki.convert_inline(text),
            '打开 <a href="https://example.com/foo">https://example.com/foo</a>。下一页',
        )

    def test_markdown_link_kept_and_not_double_wrapped(self) -> None:
        text = "关联需求单：[20888 需求](https://forward-v3.timevale.cn/productManagement/list?id=20888) 已冻结"
        converted = tianyin_wiki.convert_inline(text)
        self.assertEqual(
            converted,
            '关联需求单：<a href="https://forward-v3.timevale.cn/productManagement/list?id=20888">20888 需求</a> 已冻结',
        )
        self.assertEqual(converted.count("<a "), 1)

    def test_url_inside_inline_code_not_linked(self) -> None:
        converted = tianyin_wiki.convert_inline("接口 `POST /esign-signs/anon/preloading` 返回 `https://example.com/x` 地址")
        self.assertEqual(
            converted,
            "接口 <code>POST /esign-signs/anon/preloading</code> 返回 <code>https://example.com/x</code> 地址",
        )
        self.assertNotIn("<a ", converted)

    def test_url_inside_code_fence_not_linked(self) -> None:
        markdown = '# 标题\n\n```json\n{"fdaSealImageUrl": "https://example.com/fda-seal.png"}\n```\n'
        storage = tianyin_wiki.markdown_to_storage(markdown)
        self.assertIn("<ac:structured-macro", storage)
        self.assertIn("https://example.com/fda-seal.png", storage)
        self.assertNotIn("<a ", storage)

    def test_mixed_inline_styles(self) -> None:
        text = "**PRD：**https://alidocs.dingtalk.com/i/nodes/abc 与 `code` 并存"
        converted = tianyin_wiki.convert_inline(text)
        self.assertIn("<strong>PRD：</strong>", converted)
        self.assertIn('<a href="https://alidocs.dingtalk.com/i/nodes/abc">', converted)
        self.assertIn("<code>code</code>", converted)

    def test_table_cell_bare_url_linked(self) -> None:
        markdown = "# 标题\n\n| 字段 | 说明 |\n| --- | --- |\n| prd | https://alidocs.dingtalk.com/i/nodes/abc |\n"
        storage = tianyin_wiki.markdown_to_storage(markdown)
        self.assertIn('<a href="https://alidocs.dingtalk.com/i/nodes/abc">https://alidocs.dingtalk.com/i/nodes/abc</a>', storage)

    def test_plain_text_without_url_unchanged(self) -> None:
        self.assertEqual(tianyin_wiki.convert_inline("普通文本 `code` **加粗**"), "普通文本 <code>code</code> <strong>加粗</strong>")


if __name__ == "__main__":
    unittest.main()
