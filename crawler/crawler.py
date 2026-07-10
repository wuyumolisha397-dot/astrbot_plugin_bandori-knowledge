#!/usr/bin/env python3
"""
AstrBot BanG Dream! 知识库爬虫 —— 主入口

使用 MediaWiki API 递归爬取萌娘百科 BanG Dream! 相关页面，
转换为 Markdown 供 AstrBot 知识库导入。

用法：
    python crawler.py
"""

from __future__ import annotations

import sys
import time
import traceback
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from config import (
    API_LIMIT,
    CACHE_DIR,
    COMPLETED_PAGES_FILE,
    NS_CATEGORY,
    NS_MAIN,
    OUTPUT_DIR,
    ROOT_CATEGORY,
    SKIP_TITLE_KEYWORDS,
    VISITED_CATEGORIES_FILE,
    ensure_directories,
    load_completed_set,
    save_completed_set,
    sanitize_filename,
)
from exporter import export_page
from parser import parse_page
from utils import (
    ApiAccessDenied,
    api_get,
    check_interrupt,
    is_interrupted,
    logger,
    stats,
)


# ============================================================================
# 缓存管理
# ============================================================================


def load_progress() -> tuple[set[str], set[str]]:
    """加载断点续爬状态。

    Returns:
        (已完成页面集合, 已访问分类集合)
    """
    ensure_directories()
    completed = load_completed_set(COMPLETED_PAGES_FILE)
    visited_cats = load_completed_set(VISITED_CATEGORIES_FILE)
    logger.info("加载缓存: %d 个已完成页面, %d 个已访问分类", len(completed), len(visited_cats))
    return completed, visited_cats


def save_progress(completed: set[str], visited_cats: set[str]) -> None:
    """保存断点续爬状态。"""
    save_completed_set(COMPLETED_PAGES_FILE, completed)
    save_completed_set(VISITED_CATEGORIES_FILE, visited_cats)


def mark_page_completed(title: str, completed: set[str]) -> None:
    """标记页面已完成并持久化。"""
    completed.add(title)
    # 每完成 10 个页面保存一次
    if len(completed) % 10 == 0:
        save_completed_set(COMPLETED_PAGES_FILE, completed)


# ============================================================================
# API 调用封装
# ============================================================================


def get_category_members(
    category_title: str,
    namespace: int = NS_MAIN,
    cmcontinue: str | None = None,
) -> dict[str, Any] | None:
    """获取分类下的所有成员页面。

    Args:
        category_title: 分类标题（如 "Category:BanG Dream!"）。
        namespace: 命名空间 ID（0=主页面, 14=分类）。
        cmcontinue: 分页继续令牌。

    Returns:
        API 响应数据。
    """
    params: dict[str, Any] = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category_title,
        "cmlimit": min(API_LIMIT, 500),
        "cmnamespace": namespace,
    }
    if cmcontinue:
        params["cmcontinue"] = cmcontinue
    return api_get(params)


def get_page_content(title: str) -> dict[str, Any] | None:
    """获取页面的 wikitext 内容。

    Args:
        title: 页面标题。

    Returns:
        API 响应数据，包含 revisions 和可能的 redirect 信息。
    """
    params: dict[str, Any] = {
        "action": "query",
        "prop": "revisions|info",
        "rvprop": "content",
        "rvslots": "main",
        "titles": title,
        "redirects": "1",  # 自动解析重定向
        "inprop": "url",
    }
    return api_get(params)


def get_subcategories(
    category_title: str,
    cmcontinue: str | None = None,
) -> dict[str, Any] | None:
    """获取分类下的子分类。

    Args:
        category_title: 父分类标题。
        cmcontinue: 分页继续令牌。

    Returns:
        API 响应数据。
    """
    return get_category_members(category_title, namespace=NS_CATEGORY, cmcontinue=cmcontinue)


def get_pages_in_category(
    category_title: str,
    cmcontinue: str | None = None,
) -> dict[str, Any] | None:
    """获取分类下的主命名空间页面。

    Args:
        category_title: 分类标题。
        cmcontinue: 分页继续令牌。

    Returns:
        API 响应数据。
    """
    return get_category_members(category_title, namespace=NS_MAIN, cmcontinue=cmcontinue)


# ============================================================================
# 处理逻辑
# ============================================================================


def should_skip_title(title: str) -> bool:
    """检查页面标题是否应该跳过。

    Args:
        title: 页面标题。

    Returns:
        True 表示跳过。
    """
    for keyword in SKIP_TITLE_KEYWORDS:
        if title.startswith(keyword):
            return True
    return False


def resolve_redirect(title: str) -> tuple[str, str | None]:
    """检查页面是否为重定向，若是则跟随解析。

    Args:
        title: 页面标题。

    Returns:
        (实际标题, 重定向来源或 None)。
    """
    data = get_page_content(title)
    if not data:
        return title, None

    query = data.get("query", {})

    # 检查重定向
    redirects = query.get("redirects", [])
    if redirects:
        # MediaWiki 已经自动跟随了重定向
        actual_title = redirects[0].get("to", title)
        logger.info("  ↪ 重定向: %s → %s", title, actual_title)
        stats.redirects_followed += 1
        return actual_title, title

    # 检查页面是否本身是重定向到别处
    pages = query.get("pages", {})
    for page_id, page_info in pages.items():
        if page_info.get("pageid", 0) < 0:
            # 无效页面
            return title, None

    return title, None


def fetch_and_parse_page(title: str) -> tuple[str, str, str] | None:
    """获取页面 wikitext 并解析为 Markdown。

    Args:
        title: 页面标题。

    Returns:
        (title, markdown, source_url) 或 None。
    """
    data = get_page_content(title)
    if not data:
        return None

    query = data.get("query", {})
    pages = query.get("pages", {})

    for page_id, page_info in pages.items():
        # 跳过无效页面
        if "missing" in page_info:
            logger.warning("  页面不存在: %s", title)
            return None
        if page_info.get("pageid", 0) < 0:
            logger.warning("  无效页面: %s", title)
            return None

        # 提取 wikitext
        revisions = page_info.get("revisions", [])
        if not revisions:
            logger.warning("  无修订记录: %s", title)
            return None

        wikitext = revisions[0].get("slots", {}).get("main", {}).get("*", "")
        if not wikitext:
            logger.warning("  空内容: %s", title)
            return None

        # 获取实际标题（可能已解析重定向）
        actual_title = page_info.get("title", title)
        source_url = page_info.get("fullurl", "")
        if not source_url:
            source_url = f"https://zh.moegirl.org.cn/{quote(actual_title)}"

        # 解析为 Markdown
        markdown = parse_page(actual_title, wikitext, source_url)
        return actual_title, markdown, source_url

    return None


def process_page(
    title: str,
    completed: set[str],
    visited_cats: set[str],
    page_queue: deque[str],
    cat_queue: deque[str],
) -> None:
    """处理单个页面：获取 → 解析 → 导出。

    Args:
        title: 页面标题。
        completed: 已完成页面集合。
        visited_cats: 已访问分类集合。
        page_queue: 页面队列。
        cat_queue: 分类队列。
    """
    if title in completed:
        stats.pages_skipped += 1
        logger.debug("  ⊘ 跳过（已缓存）: %s", title)
        return

    if should_skip_title(title):
        logger.debug("  ⊘ 跳过（命名空间）: %s", title)
        return

    logger.info("  正在抓取: %s", title)

    try:
        result = fetch_and_parse_page(title)
        if result is None:
            stats.pages_failed += 1
            return

        actual_title, markdown, source_url = result

        # 导出为 Markdown
        file_count = export_page(actual_title, markdown, source_url)

        mark_page_completed(title, completed)
        stats.pages_crawled += 1
        logger.info("  ✓ 成功: %s (%d 文件)", actual_title, file_count)

    except (KeyboardInterrupt, ApiAccessDenied):
        raise
    except Exception:
        logger.error("  ✗ 失败: %s\n%s", title, traceback.format_exc())
        stats.pages_failed += 1


def process_category(
    cat_title: str,
    completed: set[str],
    visited_cats: set[str],
    page_queue: deque[str],
    cat_queue: deque[str],
) -> None:
    """处理分类：获取子分类和页面成员，加入队列。

    Args:
        cat_title: 分类标题。
        completed: 已完成页面集合。
        visited_cats: 已访问分类集合。
        page_queue: 页面队列（将被追加新页面）。
        cat_queue: 分类队列（将被追加新子分类）。
    """
    if cat_title in visited_cats:
        return

    if is_interrupted():
        return

    logger.info("📁 正在探索分类: %s", cat_title)

    try:
        # ---- 获取子分类 ----
        cmcontinue: str | None = None
        subcat_count: int = 0
        while True:
            check_interrupt()
            data = get_subcategories(cat_title, cmcontinue)
            if not data:
                break

            query = data.get("query", {})
            members = query.get("categorymembers", [])
            for member in members:
                subcat = member.get("title", "")
                if subcat and subcat not in visited_cats:
                    cat_queue.append(subcat)
                    subcat_count += 1

            # 分页
            if "continue" in data:
                cmcontinue = data["continue"].get("cmcontinue")
                if not cmcontinue:
                    break
            else:
                break

        logger.info("  ├─ 发现 %d 个子分类", subcat_count)

        # ---- 获取页面成员 ----
        cmcontinue = None
        page_count: int = 0
        while True:
            check_interrupt()
            data = get_pages_in_category(cat_title, cmcontinue)
            if not data:
                break

            query = data.get("query", {})
            members = query.get("categorymembers", [])
            for member in members:
                page_title = member.get("title", "")
                if page_title and page_title not in completed and not should_skip_title(page_title):
                    page_queue.append(page_title)
                    page_count += 1

            # 分页
            if "continue" in data:
                cmcontinue = data["continue"].get("cmcontinue")
                if not cmcontinue:
                    break
            else:
                break

        logger.info("  ├─ 发现 %d 个页面", page_count)
        visited_cats.add(cat_title)
        stats.categories_visited += 1

        # 定期保存分类缓存
        if stats.categories_visited % 5 == 0:
            save_completed_set(VISITED_CATEGORIES_FILE, visited_cats)

    except (KeyboardInterrupt, ApiAccessDenied):
        raise
    except Exception:
        logger.error("  ✗ 处理分类失败: %s\n%s", cat_title, traceback.format_exc())


# ============================================================================
# 主流程
# ============================================================================


def main() -> int:
    """主函数 —— 初始化并执行爬取流程。"""
    logger.info("=" * 60)
    logger.info("  AstrBot BanG Dream! 知识库爬虫")
    logger.info("  数据源: 萌娘百科 (zh.moegirl.org.cn)")
    logger.info("  起始分类: %s", ROOT_CATEGORY)
    logger.info("=" * 60)

    # 初始化
    ensure_directories()
    completed, visited_cats = load_progress()

    # 旧版本会把 API 失败的根分类错误标记为“已访问”，导致以后直接跳过。
    if not any(OUTPUT_DIR.glob("*.md")) and not completed:
        if ROOT_CATEGORY in visited_cats:
            logger.warning("检测到无输出的无效缓存，将重新尝试根分类。")
            visited_cats.discard(ROOT_CATEGORY)

    # 队列
    cat_queue: deque[str] = deque()
    page_queue: deque[str] = deque()

    # 如果首次运行，添加起始分类
    if ROOT_CATEGORY not in visited_cats:
        cat_queue.append(ROOT_CATEGORY)

    logger.info("开始爬取...")
    logger.info("输出目录: %s", OUTPUT_DIR)
    logger.info("缓存目录: %s", CACHE_DIR)
    logger.info("")

    exit_code = 0
    try:
        # ---- 主循环：广度优先遍历 ----
        while cat_queue or page_queue:
            check_interrupt()

            # 优先处理当前层级的分类（BFS）
            if cat_queue:
                cat = cat_queue.popleft()
                process_category(cat, completed, visited_cats, page_queue, cat_queue)
                continue

            # 处理页面
            if page_queue:
                title = page_queue.popleft()
                process_page(title, completed, visited_cats, page_queue, cat_queue)
                continue

        # ---- 完成 ----
        logger.info("")
        logger.info("✓ 所有任务完成！")

    except KeyboardInterrupt:
        logger.info("")
        logger.info("⚠ 用户中断。正在保存进度...")
        exit_code = 130
    except ApiAccessDenied as e:
        logger.error("爬取已停止: %s", e)
        exit_code = 1
    except Exception as e:
        logger.error("致命错误: %s", e)
        traceback.print_exc()
        exit_code = 1
    finally:
        # 最终保存
        save_progress(completed, visited_cats)
        logger.info("进度已保存。")

    # 输出统计
    logger.info(stats.summary())

    # 列出输出文件
    md_files = sorted(OUTPUT_DIR.glob("*.md"))
    logger.info("")
    logger.info("生成的 Markdown 文件 (%d 个):", len(md_files))
    for f in md_files:
        logger.info("  - %s", f.name)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
