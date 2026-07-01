"""
响应格式化模块 — 美观的 Markdown 输出
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kb_index import IndexEntry

HR = "——————————————————"


# ── 正文清洗 ──────────────────────────────────────────────────────────────

def _clean_content(text: str) -> str:
    """清洗 markdown 正文"""
    # 去所有 markdown 标题行
    text = re.sub(r'#{1,4}\s+[^\n]+\n?', '', text)
    # HTML 实体
    text = text.replace('&nbsp;', ' ')
    # 去 wiki 标记残留
    text = re.sub(r'[\*]{1,3}', '', text)
    # 合并空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 去首尾空白行
    text = text.strip()
    return text


def _preview(text: str, n: int = 120) -> str:
    cleaned = _clean_content(text)
    return cleaned[:n].replace('\n', ' ').strip()


# ── 详情页 ────────────────────────────────────────────────────────────────

def format_entry_detail(entry: "IndexEntry", content: str, max_len: int = 1200) -> str:
    emoji = {"角色": "🎤", "歌曲": "🎵", "乐队": "🎸", "声优": "🎙️"}.get(entry.category_dir, "📖")
    body = _clean_content(content)

    if len(body) > max_len:
        cut = max(body.rfind("。", max_len - 200, max_len),
                  body.rfind("\n", max_len - 200, max_len),
                  max_len - 100)
        body = body[:cut] + "…"

    return (
        f"{emoji} **{entry.title}**\n\n"
        f"{body}\n"
        f"\n📖 萌娘百科 · 本地知识库"
    )


# ── 搜索结果列表 ──────────────────────────────────────────────────────────

def format_search_results(
    results: list[tuple["IndexEntry", float]],
    query: str,
    category: str = "",
    is_rag: bool = False,
) -> str:
    cat_label = category or "全部"
    source = "云端" if is_rag else "本地"

    if not results:
        return (
            f"🔍 搜索 **「{query}」**（{cat_label} · {source}）\n\n"
            f"未找到相关结果。\n\n"
            f"试试：缩短关键词  换用中文/日文  用 `/随机{category}` 浏览"
        )

    lines = [f"🔍 **「{query}」** — 共 {len(results)} 条结果\n"]
    for i, (entry, _) in enumerate(results, 1):
        pv = _preview(entry.preview, 100) if entry.preview else ""
        lines.append(f"  {i}. {entry.title}")
        if pv:
            lines.append(f"     {pv}")

    lines.append(f"\n💡 输入 `/角色 xxx` `/歌曲 xxx` 可查看详情")
    return "\n".join(lines)


# ── 随机 ──────────────────────────────────────────────────────────────────

def format_random(entry: "IndexEntry", content: str) -> str:
    emoji = {"角色": "🎤", "歌曲": "🎵", "乐队": "🎸", "声优": "🎙️"}.get(entry.category_dir, "📖")
    body = _clean_content(content)

    if len(body) > 700:
        cut = max(body.rfind("。", 600, 750), body.rfind("\n", 600, 750), 600)
        body = body[:cut] + "…"

    return (
        f"🎲 {emoji} **{entry.title}**\n\n"
        f"{body}\n"
        f"\n`/随机{entry.category_dir}` 换一个"
    )


# ── 帮助 ──────────────────────────────────────────────────────────────────

def format_help() -> str:
    return (
        f"🎸 **BanG Dream! 知识库**\n\n"
        f"`/角色 名字`     `角色 名字`     查询角色\n"
        f"`/歌曲 歌名`     `歌曲 歌名`     查询歌曲\n"
        f"`/乐队 名称`     `乐队 名称`     查询乐队\n"
        f"`/声优 名字`     `声优 名字`     查询声优\n"
        f"`/随机角色`                     随机角色\n"
        f"`/随机歌曲`                     随机歌曲\n"
        f"`/随机乐队`                     随机乐队\n"
        f"`/随机声优`                     随机声优\n"
        f"`/萌百搜索 关键词`              全站搜索\n"
        f"\n📖 萌娘百科 BanG Dream! 专题  ·  本地检索"
    )


# ── 错误 / 未找到 ─────────────────────────────────────────────────────────

def format_error(msg: str) -> str:
    return f"⚠️ {msg}"


def format_not_found(query: str, category: str = "") -> str:
    cat_label = f"{category}内" if category else ""
    return (
        f"未在{cat_label}找到「{query}」\n\n"
        f"试试 `/萌百搜索 {query}` 或 `/随机{category}`"
    )
