"""
AstrBot BanG Dream! 知识库爬虫 —— Markdown 导出器

将解析后的页面内容写为 Markdown 文件，支持大字量文件按章节拆分。
"""

from __future__ import annotations

import re
from pathlib import Path

from config import (
    MAX_WORDS_PER_FILE,
    OUTPUT_DIR,
    ensure_directories,
    sanitize_filename,
)
from utils import logger, stats


# ============================================================================
# 字数统计
# ============================================================================


def count_chinese_chars(text: str) -> int:
    """统计文本中的中文字符+英文单词数（粗略估计"字数"）。

    Args:
        text: 待统计文本。

    Returns:
        估计字数。
    """
    # 中文字符
    chinese = len(re.findall(r"[一-鿿]", text))
    # 英文单词
    english = len(re.findall(r"[a-zA-Z]+", text))
    return chinese + english


# ============================================================================
# 章节拆分
# ============================================================================


def split_by_headings(markdown: str, max_words: int = MAX_WORDS_PER_FILE) -> list[str]:
    """按 ## 二级标题将 Markdown 拆分为多个部分，每部分不超过 max_words 字。

    策略：
    1. 先按 ## 标题切分为章节块。
    2. 从前往后累积章节，当累积字数超过 max_words 时开始新文件。
    3. 保证每个输出文件都以完整的章节结束（不在段落中间截断）。

    Args:
        markdown: 完整 Markdown 文本（包含 # 一级标题行）。
        max_words: 每个文件的最大字数。

    Returns:
        Markdown 文本列表，每个元素对应一个输出文件。
    """
    if count_chinese_chars(markdown) <= max_words:
        return [markdown]

    lines = markdown.split("\n")

    # 提取一级标题行和来源行（文件头部元信息）
    header_lines: list[str] = []
    body_start: int = 0
    for i, line in enumerate(lines):
        header_lines.append(line)
        if line.strip() == "---":
            body_start = i + 1
            break

    body_lines = lines[body_start:]

    # 按 ## 二级标题拆分章节
    sections: list[list[str]] = []
    current_section: list[str] = []

    for line in body_lines:
        # 二级标题作为章节分隔（注意要排除 deeper headings 的误匹配）
        if re.match(r"^##\s+\S", line) and current_section:
            sections.append(current_section)
            current_section = [line]
        else:
            current_section.append(line)

    if current_section:
        sections.append(current_section)

    # 如果没有二级标题，尝试按三级标题拆分
    if len(sections) <= 1:
        sections = []
        current_section = []
        for line in body_lines:
            if re.match(r"^###\s+\S", line) and current_section:
                sections.append(current_section)
                current_section = [line]
            else:
                current_section.append(line)
        if current_section:
            sections.append(current_section)

    # 如果仍然只有一个章节，按段落强制拆分
    if len(sections) <= 1 and count_chinese_chars(markdown) > max_words:
        return _force_split(markdown, max_words)

    # 累积章节直到超过字数限制
    header_text = "\n".join(header_lines)
    result: list[str] = []
    current_chunk_lines: list[str] = []
    current_count: int = 0

    for section in sections:
        section_text = "\n".join(section)
        section_count = count_chinese_chars(section_text)

        # 如果当前累积 + 新章节超限，先保存当前 chunk
        if current_chunk_lines and (current_count + section_count > max_words):
            chunk_text = header_text + "\n" + "\n".join(current_chunk_lines)
            result.append(chunk_text.strip())
            current_chunk_lines = []
            current_count = 0

        current_chunk_lines.extend(section)
        current_count += section_count

    # 保存最后一个 chunk
    if current_chunk_lines:
        chunk_text = header_text + "\n" + "\n".join(current_chunk_lines)
        result.append(chunk_text.strip())

    return result if result else [markdown]


def _force_split(markdown: str, max_words: int) -> list[str]:
    """强制按段落拆分（当无法按章节拆分时使用）。

    在段落边界处拆分，尽量不在句子中间断开。

    Args:
        markdown: 完整 Markdown。
        max_words: 最大字数。

    Returns:
        拆分后的 Markdown 列表。
    """
    paragraphs = markdown.split("\n\n")
    result: list[str] = []
    current: list[str] = []
    current_count: int = 0

    for para in paragraphs:
        para_count = count_chinese_chars(para)
        if current and (current_count + para_count > max_words):
            result.append("\n\n".join(current))
            current = [para]
            current_count = para_count
        else:
            current.append(para)
            current_count += para_count

    if current:
        result.append("\n\n".join(current))

    return result if len(result) > 1 else [markdown]


# ============================================================================
# 导出函数
# ============================================================================


def export_page(title: str, markdown: str, source_url: str) -> int:
    """将页面导出为 Markdown 文件。

    自动处理：
    - 文件名非法字符
    - 大字量文件拆分

    Args:
        title: 页面标题。
        markdown: 解析后的 Markdown 文本。
        source_url: 页面原始 URL。

    Returns:
        生成的文件数量。
    """
    ensure_directories()

    safe_name = sanitize_filename(title)
    parts = split_by_headings(markdown)

    file_count: int = 0
    for i, part in enumerate(parts, 1):
        if len(parts) == 1:
            filepath = OUTPUT_DIR / f"{safe_name}.md"
        else:
            filepath = OUTPUT_DIR / f"{safe_name}-{i}.md"

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(part)
            file_count += 1
            logger.debug("  写入文件: %s", filepath.name)
        except OSError as e:
            logger.error("  写入失败: %s - %s", filepath, e)

    stats.markdown_count += file_count
    return file_count
