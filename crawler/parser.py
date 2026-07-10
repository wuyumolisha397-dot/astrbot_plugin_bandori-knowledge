"""
AstrBot BanG Dream! 知识库爬虫 —— Wiki Markup → Markdown 转换器

将 MediaWiki 返回的 wikitext 解析为干净可读的 Markdown。
"""

from __future__ import annotations

import re
from typing import Any

from config import SKIP_TEMPLATES


# ============================================================================
# Wiki Markup → Markdown 核心转换
# ============================================================================


def wikitext_to_markdown(wikitext: str, title: str = "") -> str:
    """将 MediaWiki wikitext 转换为 Markdown。

    Args:
        wikitext: 原始 wikitext。
        title: 页面标题（用于生成一级标题）。

    Returns:
        转换后的 Markdown 字符串。
    """
    text = wikitext

    # ---- 预处理 ----
    text = _remove_html_comments(text)
    text = _remove_nowiki_blocks(text)
    text = _remove_redirects(text)

    # ---- 移除不需要的元素 ----
    text = _remove_categories(text)
    text = _remove_templates(text)
    text = _remove_file_embeds(text)
    text = _remove_ref_tags(text)
    text = _remove_gallery_tags(text)
    text = _remove_magic_words(text)

    # ---- 转换元素 ----
    text = _convert_headings(text)
    text = _convert_lists(text)
    text = _convert_tables(text)
    text = _convert_links(text)
    text = _convert_bold_italic(text)
    text = _convert_horizontal_rules(text)
    text = _convert_indents(text)
    text = _convert_poem_tags(text)
    text = _convert_blockquote(text)

    # ---- 后处理 ----
    text = _clean_whitespace(text)
    text = _remove_empty_headings(text)

    # ---- 添加标题 ----
    if title:
        text = f"# {title}\n\n" + text

    return text.strip()


# ============================================================================
# 各类转换函数
# ============================================================================


def _remove_html_comments(text: str) -> str:
    """移除 HTML 注释 <!-- ... -->。"""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _remove_nowiki_blocks(text: str) -> str:
    """移除 <nowiki>...</nowiki> 标签并保留内部文本。"""
    return re.sub(r"<nowiki>(.*?)</nowiki>", r"\1", text, flags=re.DOTALL | re.IGNORECASE)


def _remove_redirects(text: str) -> str:
    """移除重定向指令 #REDIRECT [[...]]。"""
    return re.sub(r"#REDIRECT\s*\[\[.*?\]\]", "", text, flags=re.IGNORECASE)


def _remove_categories(text: str) -> str:
    """移除分类标签 [[Category:...]] 和 [[分类:...]]。

    分类标签不包含正文信息，应当在 Markdown 中移除。
    """
    # 单行中的分类
    text = re.sub(
        r"\[\[(?:Category|分类|cat):[^\[\]]*?\]\]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _remove_templates(text: str) -> str:
    """移除无意义的模板调用 {{...}}。

    注意：部分模板包含正文（如 {{Quote|...}}），需要保留内部文本。
    策略：先移除纯标记性模板，再处理含正文模板。
    """
    # 递归移除嵌套模板（最多 10 层嵌套）
    for _ in range(10):
        old = text
        # 匹配最内层模板（不含嵌套 {{ }} 的模板）
        text = re.sub(
            r"\{\{(?:模板:|Template:)?([^{}|]+?)\}\}",
            r"",
            text,
        )
        # 匹配含有简单参数的模板 {{name|param1|param2=val}}
        text = re.sub(
            r"\{\{(?:模板:|Template:)?([^{}|]+?)(?:\|[^{}]*)+\}\}",
            r"",
            text,
        )
        if old == text:
            break

    # 处理 {{lang|ja|...}} 这类保留内部正文的模板
    text = re.sub(
        r"\{\{(?:lang|语言|ja|en|zh|ruby|注音|color|颜色|font|字体|size|大小)\|.*?\}\}",
        _extract_last_param,
        text,
        flags=re.IGNORECASE,
    )

    return text


def _extract_last_param(match: re.Match[str]) -> str:
    """从模板匹配中提取最后一个参数值（作为可见文本）。"""
    content = match.group(0)
    # 去掉外层的 {{ }}
    inner = content[2:-2]
    # 按 | 分割，取最后一段
    parts = inner.split("|")
    if len(parts) > 1:
        return parts[-1].strip()
    return ""


def _remove_file_embeds(text: str) -> str:
    """移除文件/图片嵌入 [[File:...]] [[Image:...]] [[文件:...]]。"""
    text = re.sub(
        r"\[\[(?:File|Image|文件|图片|Media):[^\[\]]*?\]\]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # 也处理带缩略图参数的
    text = re.sub(
        r"\[\[(?:File|Image|文件|图片):.*?\|.*?\]\]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _remove_ref_tags(text: str) -> str:
    """移除参考文献标签 <ref>...</ref> 和 <references/>。"""
    # 自闭合 <ref name="..." />
    text = re.sub(r"<ref\b[^>]*?/\s*>", "", text, flags=re.IGNORECASE)
    # 带内容的 <ref>...</ref>
    text = re.sub(r"<ref\b[^>]*?>.*?</ref>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # <references/> 和 <references>...</references>
    text = re.sub(r"<references\b[^>]*?/\s*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<references\b[^>]*?>.*?</references>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text


def _remove_gallery_tags(text: str) -> str:
    """移除 <gallery>...</gallery> 块。"""
    return re.sub(r"<gallery\b[^>]*?>.*?</gallery>", "", text, flags=re.DOTALL | re.IGNORECASE)


def _remove_magic_words(text: str) -> str:
    """移除 MediaWiki 魔术字。

    参见 https://www.mediawiki.org/wiki/Help:Magic_words
    """
    # __TOC__, __NOTOC__, __FORCETOC__, __NOEDITSECTION__, 等
    text = re.sub(r"__[A-Z_]+\__", "", text)
    return text


def _convert_headings(text: str) -> str:
    """将 Wiki 标题（== Heading ==）转换为 Markdown 标题。

    Returns:
        转换后的文本。
    """
    lines = text.split("\n")
    result: list[str] = []

    for line in lines:
        # 匹配行首的 wiki 标题
        match = re.match(r"^(={1,6})\s*(.*?)\s*\1\s*$", line)
        if match:
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            # 跳过空的或无意义的标题
            if heading_text and heading_text not in ("参考资料", "外部链接", "注释", "脚注", "参考文献", "相关条目", "参见", "外部连结"):
                result.append(f"{'#' * level} {heading_text}\n")
            continue
        result.append(line)

    return "\n".join(result)


def _convert_lists(text: str) -> str:
    """将 Wiki 列表（* / # / ; :）转换为 Markdown 列表。

    支持：
    - 无序列表：* / ** / ***
    - 有序列表：# / ## / ###
    - 定义列表：; term : definition
    """
    lines = text.split("\n")
    result: list[str] = []

    for line in lines:
        # 无序列表
        ul_match = re.match(r"^(\*+)(.*)", line)
        if ul_match:
            depth = len(ul_match.group(1))
            content = ul_match.group(2).strip()
            indent = "  " * (depth - 1)
            result.append(f"{indent}- {content}")
            continue

        # 有序列表
        ol_match = re.match(r"^(#+)(.*)", line)
        if ol_match:
            depth = len(ol_match.group(1))
            content = ol_match.group(2).strip()
            indent = "  " * (depth - 1)
            result.append(f"{indent}1. {content}")
            continue

        # 定义列表 ; term : definition
        dl_match = re.match(r"^;(.*?):(.*)", line)
        if dl_match:
            term = dl_match.group(1).strip()
            definition = dl_match.group(2).strip()
            result.append(f"**{term}**: {definition}")
            continue

        # 缩进行（:）
        indent_match = re.match(r"^(:+)(.*)", line)
        if indent_match:
            depth = len(indent_match.group(1))
            content = indent_match.group(2).strip()
            result.append(f"{'> ' * depth}{content}")
            continue

        result.append(line)

    return "\n".join(result)


def _convert_tables(text: str) -> str:
    """将 Wiki 表格 {| ... |} 转换为 Markdown 表格。

    Wiki 表格语法：
    {| class="wikitable"
    ! 标题1 !! 标题2
    |-
    | 单元格1 || 单元格2
    |}
    """
    # 找到所有表格块
    def replace_table(match: re.Match[str]) -> str:
        table_content = match.group(1)
        return _wiki_table_to_md(table_content)

    text = re.sub(
        r"\{\|(.*?)\|\}",
        replace_table,
        text,
        flags=re.DOTALL,
    )
    return text


def _wiki_table_to_md(table_wikitext: str) -> str:
    """将单个 Wiki 表格内容转换为 Markdown 表格。

    Args:
        table_wikitext: 表格 wikitext（不含外层的 {| 和 |}）。

    Returns:
        Markdown 表格或原始文本（解析失败时）。
    """
    lines = table_wikitext.strip().split("\n")
    rows: list[list[str]] = []
    current_row: list[str] = []
    is_header: bool = True  # 第一行通常是表头

    # 解析表格属性行（第一行通常是 {| 后面的 class 等属性）
    # 已经在 replace_table 中去掉了 {|，所以第一行是属性/标题

    pending_text: str = ""

    for line in lines:
        line = line.strip()

        # 跳过空行
        if not line:
            continue

        # 表格标题行 ! heading !! heading
        if line.startswith("!"):
            # 去掉开头的 !，按 !! 分割
            cells_text = re.sub(r"^!\s*", "", line)
            cells = re.split(r"\s*!!\s*", cells_text)
            clean_cells = [_clean_cell(c) for c in cells]
            if clean_cells:
                rows.append(clean_cells)
                # 标记为标题行
                if rows:
                    rows[-1] = [f"**{c}**" if not c.startswith("**") else c for c in clean_cells]
            continue

        # 分隔行 |-
        if re.match(r"^\|-?\s*$", line):
            if current_row:
                rows.append(current_row)
                current_row = []
            continue

        # 标题/数据合并行（! heading !! data || data）
        if "!!" in line or line.startswith("|"):
            # 去掉开头的 | 或 !
            line = re.sub(r"^[|!]\s*", "", line)
            # 按 || 或 !! 分割
            if "||" in line:
                cells = re.split(r"\s*\|\|\s*", line)
            elif "!!" in line:
                cells = re.split(r"\s*!!\s*", line)
            else:
                cells = [line]
            clean_cells = [_clean_cell(c) for c in cells]
            current_row.extend(clean_cells)
            continue

        # 普通数据行
        if line.startswith("|"):
            line = re.sub(r"^\|\s*", "", line)
            cells = re.split(r"\s*\|\|\s*", line)
            clean_cells = [_clean_cell(c) for c in cells]
            current_row.extend(clean_cells)
            continue

    # 保存最后一行
    if current_row:
        rows.append(current_row)

    if not rows:
        return ""

    # 过滤掉完全空的行
    rows = [r for r in rows if any(c.strip() for c in r)]

    if not rows:
        return ""

    # 对齐列数：找出最大列数
    max_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < max_cols:
            r.append("")

    # 生成 Markdown 表格
    md_lines: list[str] = []

    for i, row in enumerate(rows):
        md_lines.append("| " + " | ".join(row) + " |")
        if i == 0:
            # 分隔线
            md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")

    return "\n".join(md_lines) + "\n"


def _clean_cell(cell: str) -> str:
    """清理表格单元格内容（去除 wiki 内联格式和 HTML）。"""
    # 去除属性（如 style="..." 等）
    cell = re.sub(r'\b\w+\s*=\s*"[^"]*"', "", cell)
    cell = re.sub(r"\b\w+\s*=\s*'[^']*'", "", cell)
    # 粗体/斜体
    cell = re.sub(r"'''(.*?)'''", r"**\1**", cell)
    cell = re.sub(r"''(.*?)''", r"*\1*", cell)
    # Wiki 链接
    cell = re.sub(r"\[\[([^\]|]+)\]\]", r"\1", cell)
    cell = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", cell)
    # HTML 标签
    cell = re.sub(r"<[^>]+>", "", cell)
    # ref
    cell = re.sub(r"<ref[^>]*?/\s*>", "", cell, flags=re.IGNORECASE)
    cell = re.sub(r"<ref\b[^>]*?>.*?</ref>", "", cell, flags=re.DOTALL | re.IGNORECASE)
    # 换行
    cell = cell.replace("<br/>", " ").replace("<br>", " ").replace("<br />", " ")
    return cell.strip()


def _convert_links(text: str) -> str:
    """将 Wiki 内链 [[Page]] 和 [[Page|Text]] 转换为 Markdown 链接。

    注意：我们生成的是独立 Markdown 文件，所以 Wiki 内链转为纯文本（无法链接到其他文件）。

    外部链接 [http://... text] 转为 Markdown 链接。
    """
    # 外部链接 [http://url text] → [text](url)
    text = re.sub(
        r"\[(https?://[^\]\s]+)\s+([^\]]+?)\]",
        r"[\2](\1)",
        text,
    )

    # 外部链接 [http://url] → <url>
    text = re.sub(
        r"\[(https?://[^\s\]]+)\]",
        r"<\1>",
        text,
    )

    # Wiki 内链 [[Page|Text]] → Text（转为纯文本，保留显示名）
    text = re.sub(
        r"\[\[([^\]|]+)\|([^\]]+?)\]\]",
        lambda m: m.group(2).strip(),
        text,
    )

    # Wiki 内链 [[Page]] → Page
    text = re.sub(
        r"\[\[([^\]]+?)\]\]",
        lambda m: m.group(1).strip(),
        text,
    )

    return text


def _convert_bold_italic(text: str) -> str:
    """将 Wiki 粗体/斜体语法转为 Markdown。

    '''bold'' → **bold**
    ''italic'' → *italic*
    '''''bold italic''''' → ***bold italic***
    """
    # 先处理五引号（粗斜体）
    text = re.sub(r"'''''(.*?)'''''", r"***\1***", text)
    # 再处理三引号（粗体）
    text = re.sub(r"'''(.*?)'''", r"**\1**", text)
    # 最后处理两引号（斜体）
    text = re.sub(r"''(.*?)''", r"*\1*", text)
    return text


def _convert_horizontal_rules(text: str) -> str:
    """将 Wiki 水平线 ---- 转换为 Markdown ---。"""
    return re.sub(r"^----+$", "---", text, flags=re.MULTILINE)


def _convert_indents(text: str) -> str:
    """将 Wiki 缩进 ::: 转换为块引用 >。"""
    # 已经在 _convert_lists 中处理了 : 开头的行
    return text


def _convert_poem_tags(text: str) -> str:
    """处理 <poem>...</poem> 标签，保留内部换行。"""
    def poem_replacer(m: re.Match[str]) -> str:
        content = m.group(1).strip()
        return f"\n```\n{content}\n```\n"

    text = re.sub(
        r"<poem.*?>(.*?)</poem>",
        poem_replacer,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text


def _convert_blockquote(text: str) -> str:
    """将 <blockquote>...</blockquote> 转换为 Markdown 引用。"""
    def bq_replacer(m: re.Match[str]) -> str:
        content = m.group(1).strip()
        lines = content.split("\n")
        return "\n".join(f"> {line}" for line in lines) + "\n"

    text = re.sub(
        r"<blockquote\b[^>]*?>(.*?)</blockquote>",
        bq_replacer,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text


def _clean_whitespace(text: str) -> str:
    """清理多余的空行和空白。"""
    # 3 个以上连续换行 → 2 个换行
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 行尾空白
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    # 行首空白保留缩进结构
    return text


def _remove_empty_headings(text: str) -> str:
    """移除没有内容的空标题。"""
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # 检查是否为标题
        if re.match(r"^#{1,6}\s+\S.*$", line) or re.match(r"^#{1,6}\s*$", line):
            # 向前看是否只有空白行
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            # 如果直到下一个标题都没有内容
            if j >= len(lines) or re.match(r"^#{1,6}\s", lines[j].strip()):
                i = j
                continue
        result.append(lines[i])
        i += 1
    return "\n".join(result)


# ============================================================================
# HTML 标签清理
# ============================================================================


def strip_html_tags(text: str) -> str:
    """移除所有残留的 HTML 标签，保留内部文本。

    Args:
        text: 可能包含 HTML 标签的文本。

    Returns:
        清理后的纯文本。
    """
    # 移除自闭合标签
    text = re.sub(r"<[^>]+?/\s*>", "", text)
    # 移除成对标签（保留内部文本）
    text = re.sub(r"<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?>(.*?)</\1>", r"\2", text, flags=re.DOTALL)
    # 移除所有剩余的标签
    text = re.sub(r"<[^>]+>", "", text)
    return text


# ============================================================================
# 公开 API
# ============================================================================


def parse_page(title: str, wikitext: str, source_url: str) -> str:
    """完整解析页面：wikitext → 最终 Markdown。

    Args:
        title: 页面标题。
        wikitext: MediaWiki API 返回的 wikitext。
        source_url: 页面原始 URL。

    Returns:
        完整的 Markdown 文本。
    """
    # 标题已在 wikitext_to_markdown 中通过第一个参数传入
    body = wikitext_to_markdown(wikitext, title="")

    # 清理残留 HTML
    body = strip_html_tags(body)

    # 构建最终 Markdown
    lines: list[str] = [
        f"# {title}",
        "",
        f"来源：",
        f"{source_url}",
        "",
        "---",
        "",
        body,
    ]

    return "\n".join(lines)
