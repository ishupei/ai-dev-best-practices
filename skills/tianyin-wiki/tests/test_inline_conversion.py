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

    def test_span_annotation_preserved(self) -> None:
        converted = tianyin_wiki.convert_inline('<span style="color:#16a34a">`fdaEnable`</span>')
        self.assertEqual(
            converted,
            '<span style="color:#16a34a"><code>fdaEnable</code></span>',
        )

    def test_span_annotation_in_table_cell(self) -> None:
        markdown = (
            "# 标题\n\n"
            "| 字段 | 说明 |\n"
            "| --- | --- |\n"
            '| <span style="color:#16a34a">`fdaReasonList`</span> | 原因列表 |\n'
        )
        storage = tianyin_wiki.markdown_to_storage(markdown)
        self.assertIn(
            '<td><p><span style="color:#16a34a"><code>fdaReasonList</code></span></p></td>',
            storage,
        )
        self.assertNotIn("&lt;span", storage)

    def test_html_tag_inside_code_stays_text(self) -> None:
        converted = tianyin_wiki.convert_inline("`<span>` 是标签")
        self.assertEqual(converted, "<code>&lt;span&gt;</code> 是标签")

    def test_plain_text_without_url_unchanged(self) -> None:
        self.assertEqual(tianyin_wiki.convert_inline("普通文本 `code` **加粗**"), "普通文本 <code>code</code> <strong>加粗</strong>")


class StorageCompareTest(unittest.TestCase):
    def test_escaped_tag_text_not_equal_to_real_tag(self) -> None:
        old = '&lt;span style="color:#16a34a"&gt;fdaReasonList&lt;/span&gt;'
        new = '<span style="color:#16a34a">fdaReasonList</span>'
        self.assertNotEqual(
            tianyin_wiki.normalize_storage_for_compare(old),
            tianyin_wiki.normalize_storage_for_compare(new),
        )

    def test_punctuation_entities_equivalent(self) -> None:
        self.assertEqual(
            tianyin_wiki.normalize_storage_for_compare("说明：字段“新增”"),
            tianyin_wiki.normalize_storage_for_compare("说明：字段&ldquo;新增&rdquo;"),
        )

    def test_span_hex_color_equivalent_to_rgb(self) -> None:
        submitted = '<span style="color:#16a34a">绿色</span>'
        stored = '<span style="color: rgb(22,163,74);">绿色</span>'
        self.assertEqual(
            tianyin_wiki.normalize_storage_for_compare(submitted),
            tianyin_wiki.normalize_storage_for_compare(stored),
        )

    def test_macro_injected_attrs_ignored(self) -> None:
        submitted = '<ac:structured-macro ac:name="code">'
        stored = '<ac:structured-macro ac:name="code" ac:macro-id="abc" ac:schema-version="1">'
        self.assertEqual(
            tianyin_wiki.normalize_storage_for_compare(submitted),
            tianyin_wiki.normalize_storage_for_compare(stored),
        )


class BlockRenderingTest(unittest.TestCase):
    def test_external_image_becomes_image_macro(self) -> None:
        converted = tianyin_wiki.convert_inline(
            "![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/eYV)"
        )
        self.assertEqual(
            converted,
            '<ac:image><ri:url ri:value="https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/eYV"/></ac:image>',
        )

    def test_relative_image_falls_back_to_link(self) -> None:
        converted = tianyin_wiki.convert_inline("![图](./images/a.png)")
        self.assertEqual(converted, '<a href="./images/a.png">图</a>')

    def test_blockquote_rendering(self) -> None:
        markdown = (
            "# 标题\n\n"
            "> 复用关联需求单 [20888](https://x/y?id=1) 已冻结\n"
            "> 第二行继续\n\n"
            "普通段落\n"
        )
        storage = tianyin_wiki.markdown_to_storage(markdown)
        self.assertEqual(
            storage,
            '<blockquote><p>复用关联需求单 <a href="https://x/y?id=1">20888</a> 已冻结 第二行继续</p></blockquote><p>普通段落</p>',
        )

    def test_table_cell_code_with_pipe_kept(self) -> None:
        markdown = (
            "# 标题\n\n"
            "| 术语 | 说明 |\n"
            "| --- | --- |\n"
            "| 骑缝签 | 内部签署区模型 `signType=EDGE/EDGE-SIGN`；epaas 模板控件 `type=QF_SIGN` |\n"
        )
        storage = tianyin_wiki.markdown_to_storage(markdown)
        self.assertIn("<td><p>骑缝签</p></td>", storage)
        self.assertIn(
            '<td><p>内部签署区模型 <code>signType=EDGE/EDGE-SIGN</code>；epaas 模板控件 <code>type=QF_SIGN</code></p></td>',
            storage,
        )

    def test_code_cdata_terminator_escaped(self) -> None:
        markdown = '# 标题\n\n```xml\n<r>a]]>b</r>\n```\n'
        storage = tianyin_wiki.markdown_to_storage(markdown)
        self.assertIn("a]]]]><![CDATA[>b", storage)
        self.assertIn("<ac:structured-macro ac:name=\"code\">", storage)

    def test_nested_list_rendering(self) -> None:
        markdown = (
            "# 标题\n\n"
            "- 一级项\n"
            "  - 二级项 A\n"
            "  - 二级项 B\n"
            "- 一级项 2\n"
        )
        storage = tianyin_wiki.markdown_to_storage(markdown)
        self.assertEqual(
            storage,
            "<ul><li>一级项<ul><li>二级项 A</li><li>二级项 B</li></ul></li>"
            "<li>一级项 2</li></ul>",
        )


class ExtendedMarkdownTest(unittest.TestCase):
    def test_angle_bracket_autolink(self) -> None:
        converted = tianyin_wiki.convert_inline("<https://example.com/auto?a=1&b=2>")
        self.assertEqual(
            converted,
            '<a href="https://example.com/auto?a=1&amp;b=2">https://example.com/auto?a=1&amp;b=2</a>',
        )

    def test_strikethrough(self) -> None:
        converted = tianyin_wiki.convert_inline("已废弃 ~~旧内容~~ 保留")
        self.assertEqual(
            converted,
            '已废弃 <span style="text-decoration: line-through;">旧内容</span> 保留',
        )

    def test_underline_sub_sup_passthrough(self) -> None:
        converted = tianyin_wiki.convert_inline("<u>下划线</u> H<sub>2</sub>O X<sup>2</sup>")
        self.assertEqual(
            converted,
            "<u>下划线</u> H<sub>2</sub>O X<sup>2</sup>",
        )

    def test_table_alignment(self) -> None:
        markdown = (
            "# 标题\n\n"
            "| 左 | 中 | 右 |\n"
            "| :--- | :---: | ---: |\n"
            "| a | b | c |\n"
        )
        storage = tianyin_wiki.markdown_to_storage(markdown)
        self.assertIn('<th style="text-align: left;"><p>左</p></th>', storage)
        self.assertIn('<th style="text-align: center;"><p>中</p></th>', storage)
        self.assertIn('<th style="text-align: right;"><p>右</p></th>', storage)
        self.assertIn('<td style="text-align: right;"><p>c</p></td>', storage)

    def test_inline_html_comment_stripped(self) -> None:
        converted = tianyin_wiki.convert_inline("前文 <!-- 待补充 --> 后文")
        self.assertEqual(converted, "前文  后文")

    def test_reference_links_resolved(self) -> None:
        markdown = (
            "# 标题\n\n"
            "详见 [需求单][req] 和 [旧链接][]。\n\n"
            "[req]: https://forward-v3.timevale.cn/list?id=20888\n"
            "[旧链接]: https://example.com/old\n"
        )
        storage = tianyin_wiki.markdown_to_storage(markdown)
        self.assertIn(
            '<p>详见 <a href="https://forward-v3.timevale.cn/list?id=20888">需求单</a> 和 '
            '<a href="https://example.com/old">旧链接</a>。</p>',
            storage,
        )
        self.assertNotIn("[req]:", storage)

    def test_reference_link_undefined_kept_literal(self) -> None:
        converted = tianyin_wiki.convert_inline("文本 [未知][nope] 保持")
        self.assertEqual(converted, "文本 [未知][nope] 保持")

    def test_reference_link_definition_inside_fence_ignored(self) -> None:
        markdown = (
            "# 标题\n\n"
            "```text\n"
            "[req]: https://inside-fence.example\n"
            "```\n\n"
            "正文 [x][req]\n"
        )
        storage = tianyin_wiki.markdown_to_storage(markdown)
        self.assertIn("[req]: https://inside-fence.example", storage)  # 代码块内原样
        self.assertIn("正文 [x][req]", storage)  # 未定义，保持字面


if __name__ == "__main__":
    unittest.main()
