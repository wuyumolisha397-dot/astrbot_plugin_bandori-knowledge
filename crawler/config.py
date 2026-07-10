"""
AstrBot BanG Dream! 知识库爬虫 —— 全局配置

所有可调参数集中在此文件，方便修改而无需改动业务代码。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ============================================================================
# 路径
# ============================================================================

# 项目根目录（config.py 所在目录）
PROJECT_ROOT: Path = Path(__file__).resolve().parent

# Markdown 输出目录
OUTPUT_DIR: Path = PROJECT_ROOT / "output"

# 缓存目录（断点续爬）
CACHE_DIR: Path = PROJECT_ROOT / "cache"

# 已完成页面列表（一行一个页面标题）
COMPLETED_PAGES_FILE: Path = CACHE_DIR / "completed_pages.txt"

# 已访问分类列表
VISITED_CATEGORIES_FILE: Path = CACHE_DIR / "visited_categories.txt"

# 爬取进度日志
PROGRESS_LOG: Path = CACHE_DIR / "progress.log"

# ============================================================================
# MediaWiki API
# ============================================================================

API_URL: str = "https://zh.moegirl.org.cn/api.php"

# User-Agent（遵守 robots.txt 礼仪）
USER_AGENT: str = (
    "BandoriKnowledgeBot/1.1 "
    "(https://github.com/wuyumolisha397-dot/astrbot_plugin_bandori-knowledge)"
)

# 萌娘百科目前会拒绝部分匿名 MediaWiki API 查询。
# 登录后可从浏览器请求头中复制 Cookie，并通过环境变量传入。
API_COOKIE: str = os.getenv("MOEGIRL_COOKIE", "").strip()

# ============================================================================
# 爬取配置
# ============================================================================

# 起始分类
ROOT_CATEGORY: str = "Category:BanG Dream!"

# 分类命名空间 ID（MediaWiki 中 Category = 14）
NS_CATEGORY: int = 14

# 主命名空间 ID（普通页面 = 0）
NS_MAIN: int = 0

# 每次 API 请求返回的最大条目数（MediaWiki 上限通常为 500）
API_LIMIT: int = 500

# 每秒最大请求数
REQUESTS_PER_SECOND: float = 2.0

# 最大重试次数
MAX_RETRIES: int = 5

# 指数退避基础等待时间（秒）
BACKOFF_BASE: float = 1.0

# 指数退避最大等待时间（秒）
BACKOFF_MAX: float = 120.0

# HTTP 请求超时（秒）
REQUEST_TIMEOUT: int = 30

# 两次请求之间的最小间隔（秒）
REQUEST_DELAY: float = 1.0 / REQUESTS_PER_SECOND

# ============================================================================
# 内容过滤
# ============================================================================

# 需要移除的模板前缀（不展示的模板）
SKIP_TEMPLATES: set[str] = {
    "Template:",
    "模板:",
    "Navbox",
    "导航",
    "Clear",
    "clr",
    "-",
    "=",
    "Infobox",
    "信息框",
    "Documentation",
    "文档",
    "TOC",
    "目录",
    "Reflist",
    "参考文献",
    "NoteTA",
    "Note",
    "注意",
    "Color",
    "颜色",
    "Coloredlink",
    "Font",
    "字体",
    "Size",
    "大小",
    "Align",
    "对齐",
    "Ruby",
    "注音",
    "Lang",
    "语言",
    "Ja",
    "En",
    "Zh",
    "Hide",
    "隐藏",
    "Toggle",
    "切换",
    "Anchor",
    "锚点",
    "Main",
    "主条目",
    "See also",
    "参见",
    "Further",
    "更多",
    "Details",
    "详情",
    "Stub",
    "小作品",
    "Delete",
    "删除",
    "Merge",
    "合并",
    "Split",
    "拆分",
    "Move",
    "移动",
    "Protect",
    "保护",
    "Lock",
    "锁定",
    "Vandalism",
    "破坏",
    "Disclaimer",
    "免责",
    "Terms",
    "条款",
    "Policy",
    "方针",
    "Guideline",
    "指引",
    "Help",
    "帮助",
    "Template doc",
    "模板文档",
    "Documentation subpage",
    "文档子页",
}

# 页面标题包含这些关键词则跳过
SKIP_TITLE_KEYWORDS: list[str] = [
    "Category:",
    "Template:",
    "File:",
    "Help:",
    "Talk:",
    "User:",
    "MediaWiki:",
    "Special:",
    "Project:",
    "Module:",
    "Gadget:",
    "Gadget definition:",
    "Topic:",
    "Draft:",
    "Portal:",
    "TimedText:",
]

# 需要保留的章节关键词（其他章节可能被跳过）
KEEP_SECTIONS: list[str] = []  # 空列表表示保留所有章节

# ============================================================================
# Markdown 导出
# ============================================================================

# 单个 Markdown 文件最大字数（超过则拆分）
MAX_WORDS_PER_FILE: int = 5000

# 拆分文件后缀格式（如 千早爱音-1.md）
SPLIT_SUFFIX: str = "-{n}"

# Windows 文件名字符替换映射
FILENAME_REPLACEMENTS: dict[str, str] = {
    "\\": "＼",   # 全角反斜线
    "/": "／",    # 全角斜线
    ":": "：",    # 全角冒号
    "*": "＊",    # 全角星号
    "?": "？",    # 全角问号
    '"': "＂",    # 全角双引号
    "<": "＜",    # 全角小于号
    ">": "＞",    # 全角大于号
    "|": "｜",    # 全角竖线
    "\r": "",
    "\n": "",
    "\t": " ",
}

# ============================================================================
# 初始化
# ============================================================================


def ensure_directories() -> None:
    """确保所有需要的目录存在。"""
    for d in (OUTPUT_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_completed_set(filepath: Path) -> set[str]:
    """从文件加载已完成的条目集合。

    Args:
        filepath: 缓存文件路径。

    Returns:
        已完成的条目标题集合。
    """
    if not filepath.exists():
        return set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except Exception:
        return set()


def save_completed_set(filepath: Path, items: set[str]) -> None:
    """保存已完成条目到文件。

    Args:
        filepath: 缓存文件路径。
        items: 条目标题集合。
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for item in sorted(items):
            f.write(item + "\n")


def sanitize_filename(filename: str) -> str:
    """清理文件名，替换 Windows 非法字符。

    Args:
        filename: 原始文件名（不含扩展名）。

    Returns:
        合法的文件名。
    """
    for ch, replacement in FILENAME_REPLACEMENTS.items():
        filename = filename.replace(ch, replacement)
    # 去除首尾空格和点
    filename = filename.strip(" .")
    # 确保不为空
    if not filename:
        filename = "_unnamed"
    # Windows 保留名处理
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5",
        "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
        "LPT6", "LPT7", "LPT8", "LPT9",
    }
    if filename.upper() in reserved:
        filename = "_" + filename
    # 限制长度（Windows 路径最长 260，留足余量）
    if len(filename) > 200:
        filename = filename[:200]
    return filename
