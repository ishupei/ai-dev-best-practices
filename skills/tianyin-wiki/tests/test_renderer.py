from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tianyin_wiki.py"
SPEC = importlib.util.spec_from_file_location("tianyin_wiki", MODULE_PATH)
assert SPEC and SPEC.loader
wiki = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wiki
SPEC.loader.exec_module(wiki)

MD = "# 主标题\n\n%s\n"


def storage(fragment: str) -> str:
    return wiki.markdown_to_storage(MD % fragment)


class HeadingTest(unittest.TestCase):
    def test_atx_headings(self) -> None:
        self.assertEqual(storage("## 二级\n### 三级\n###### 六级"), "<h2>二级</h2><h3>三级</h3><h6>六级</h6>")

    def test_setext_heading(self) -> None:
        self.assertEqual(storage("章节\n=====\n"), "<h1>章节</h1>")

    def test_main_title_stripped(self) -> None:
        self.assertEqual(wiki.markdown_to_storage("# 主标题\n\n正文"), "<p>正文</p>")


class InlineStyleTest(unittest.TestCase):
    def test_bold_italic_variants(self) -> None:
        self.assertEqual(
            storage("**粗** *斜* ___粗斜___ _下斜_"),
            "<p><strong>粗</strong> <em>斜</em> <em><strong>粗斜</strong></em> <em>下斜</em></p>",
        )

    def test_underscore_intraword_not_mangled(self) -> None:
        self.assertEqual(storage("变量 fda_config 和 my_var"), "<p>变量 fda_config 和 my_var</p>")

    def test_strikethrough(self) -> None:
        self.assertEqual(
            storage("已废弃 ~~旧内容~~"),
            '<p>已废弃 <span style="text-decoration: line-through;">旧内容</span></p>',
        )

    def test_inline_code_escaped(self) -> None:
        self.assertEqual(storage("`a<b` 与 `x|y`"), "<p><code>a&lt;b</code> 与 <code>x|y</code></p>")


class LinkTest(unittest.TestCase):
    def test_nested_parentheses_url(self) -> None:
        self.assertEqual(
            storage("[x](https://example.com/a_(b)c)"),
            '<p><a href="https://example.com/a_(b)c">x</a></p>',
        )

    def test_reference_links(self) -> None:
        self.assertEqual(
            storage("详见 [需求][r]。\n\n[r]: https://x/y?id=1"),
            '<p>详见 <a href="https://x/y?id=1">需求</a>。</p>',
        )

    def test_link_title(self) -> None:
        self.assertEqual(storage('[x](https://a.b "标题")'), '<p><a href="https://a.b" title="标题">x</a></p>')

    def test_angle_autolink_and_email(self) -> None:
        self.assertEqual(
            storage("见 <https://example.com/a> 和 <a@b.com>"),
            '<p>见 <a href="https://example.com/a">https://example.com/a</a> 和 <a href="mailto:a@b.com">a@b.com</a></p>',
        )

    def test_bare_url(self) -> None:
        self.assertEqual(
            storage("地址 https://example.com/foo。继续"),
            '<p>地址 <a href="https://example.com/foo">https://example.com/foo</a>。继续</p>',
        )

    def test_unsafe_protocol_stays_literal(self) -> None:
        self.assertEqual(storage("[x](javascript:alert(1))"), "<p>[x](javascript:alert(1))</p>")


class ListTest(unittest.TestCase):
    def test_all_bullet_markers_are_separate_lists(self) -> None:
        self.assertEqual(storage("- a\n+ b\n* c"), "<ul><li>a</li></ul><ul><li>b</li></ul><ul><li>c</li></ul>")

    def test_ordered_start(self) -> None:
        self.assertEqual(storage("3. 三\n4. 四"), '<ol start="3"><li>三</li><li>四</li></ol>')

    def test_nested_list(self) -> None:
        self.assertEqual(
            storage("- 父\n  - 子A\n  - 子B\n- 兄"),
            "<ul><li>父<ul><li>子A</li><li>子B</li></ul></li><li>兄</li></ul>",
        )

    def test_task_list_literal(self) -> None:
        self.assertEqual(storage("- [ ] 待办\n- [x] 完成"), "<ul><li>[ ] 待办</li><li>[x] 完成</li></ul>")


class BlockTest(unittest.TestCase):
    def test_blockquote_nested(self) -> None:
        self.assertEqual(
            storage("> 外层\n> 继续\n>\n> > 内层"),
            "<blockquote><p>外层\n继续</p><blockquote><p>内层</p></blockquote></blockquote>",
        )

    def test_code_fence_language(self) -> None:
        self.assertIn('<ac:parameter ac:name="language">python</ac:parameter>', storage("```python\nprint(1)\n```"))
        self.assertNotIn("language", storage("```\nplain\n```"))

    def test_tilde_fence(self) -> None:
        self.assertIn("language\">javascript", storage("~~~javascript\nlet x = 1;\n~~~"))

    def test_code_cdata_terminator(self) -> None:
        self.assertIn("a]]]]><![CDATA[>b", storage("```xml\n<r>a]]>b</r>\n```"))

    def test_table_alignment_and_escaped_pipe(self) -> None:
        s = storage("| 左 | 中 | 右 |\n| :--- | :---: | ---: |\n| a\\|b | c | d |")
        self.assertIn('<th style="text-align:left"><p>左</p></th>', s)
        self.assertIn('<td style="text-align:center"><p>c</p></td>', s)
        self.assertIn("<p>a|b</p>", s)

    def test_table_mismatched_separator_falls_back_to_paragraph(self) -> None:
        self.assertIn("<p>| A | B | C |", storage("| A | B | C |\n| --- |\n| 1 | 2 | 3 |"))

    def test_table_without_outer_pipes(self) -> None:
        self.assertIn("<th><p>Name</p></th>", storage("Name | Value\n--- | ---\nA | B"))

    def test_hr_variants(self) -> None:
        self.assertEqual(storage("---\n\n***\n\n___"), "<hr /><hr /><hr />")

    def test_hardbreak(self) -> None:
        self.assertEqual(storage("第一行  \n第二行"), "<p>第一行<br />第二行</p>")


class HtmlCssTest(unittest.TestCase):
    def test_span_css_passthrough(self) -> None:
        self.assertEqual(
            storage('<span style="color:#16a34a">绿</span> <span style="background-color:yellow">黄</span>'),
            '<p><span style="color:#16a34a">绿</span> <span style="background-color:yellow">黄</span></p>',
        )

    def test_u_sub_sup_passthrough(self) -> None:
        self.assertEqual(storage("<u>x</u> H<sub>2</sub> X<sup>2</sup>"), "<p><u>x</u> H<sub>2</sub> X<sup>2</sup></p>")

    def test_non_whitelist_html_escaped(self) -> None:
        self.assertEqual(storage("<kbd>Ctrl</kbd>"), "<p>&lt;kbd&gt;Ctrl&lt;/kbd&gt;</p>")

    def test_comments_stripped(self) -> None:
        self.assertEqual(storage("前文 <!-- 行内 --> 后文"), "<p>前文  后文</p>")
        self.assertEqual(storage("<!-- 整行 -->\n\n正文"), "<p>正文</p>")

    def test_entities_decoded(self) -> None:
        self.assertEqual(storage("A &amp; B &copy;"), "<p>A &amp; B ©</p>")


class ImageMermaidTest(unittest.TestCase):
    def test_external_image(self) -> None:
        self.assertEqual(
            storage("![alt](https://example.com/a.png)"),
            '<p><ac:image><ri:url ri:value="https://example.com/a.png"/></ac:image></p>',
        )

    def test_relative_image_fallback_link(self) -> None:
        self.assertEqual(storage("![图](./images/a.png)"), '<p><a href="./images/a.png">图</a></p>')

    def test_mermaid_fence_mapping(self) -> None:
        md = "# 标题\n\n```mermaid\nflowchart TD\nA-->B\n```\n\n```mermaid\nflowchart LR\nC-->D\n```\n"
        s = wiki.markdown_to_storage(md, ["m1.png", "m2.png"], [400, 500])
        self.assertEqual(s.count("<ac:image"), 2)
        self.assertIn('ri:filename="m1.png"', s)
        self.assertIn('ac:width="500"', s)

    def test_tilde_mermaid_fence_counted(self) -> None:
        md = "# 标题\n\n~~~mermaid\nflowchart TD\nA-->B\n~~~\n"
        self.assertEqual(len(wiki.mermaid_blocks(md)), 1)


class GateAndCompareTest(unittest.TestCase):
    def test_gate_blocks_unsafe_constructs(self) -> None:
        self.assertTrue(wiki.markdown_conversion_issues("[x](javascript:alert(1))"))
        self.assertTrue(wiki.markdown_conversion_issues("<kbd>x</kbd>"))
        self.assertTrue(wiki.markdown_conversion_issues("![图](./a.png)"))
        self.assertTrue(wiki.markdown_conversion_issues("🚀 火箭"))

    def test_gate_passes_supported_content(self) -> None:
        md = "# ok\n\n- [ ] 任务（字面降级）\n\n```python\nx = 1\n```\n\n> 引用\n"
        self.assertEqual([], wiki.markdown_conversion_issues(md))

    def test_compare_escaped_tag_not_equal_real_tag(self) -> None:
        self.assertNotEqual(
            wiki.normalize_storage_for_compare('&lt;span style="color:#16a34a"&gt;x&lt;/span&gt;'),
            wiki.normalize_storage_for_compare('<span style="color:#16a34a">x</span>'),
        )

    def test_compare_rgb_color_equivalent(self) -> None:
        self.assertEqual(
            wiki.normalize_storage_for_compare('<span style="color:#16a34a">x</span>'),
            wiki.normalize_storage_for_compare('<span style="color: rgb(22,163,74);">x</span>'),
        )

    def test_compare_macro_attrs_ignored(self) -> None:
        self.assertEqual(
            wiki.normalize_storage_for_compare('<ac:structured-macro ac:name="code">'),
            wiki.normalize_storage_for_compare('<ac:structured-macro ac:name="code" ac:macro-id="abc" ac:schema-version="1">'),
        )

    def test_paste_html(self) -> None:
        html = wiki.markdown_to_paste_html("# 标题\n\n```python\nprint(1)\n```\n")
        self.assertIn("<pre><code>print(1)", html)
        self.assertNotIn("structured-macro", html)


if __name__ == "__main__":
    unittest.main()
