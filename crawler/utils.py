"""
AstrBot BanG Dream! 知识库爬虫 —— 通用工具函数

包含日志、HTTP 请求、限速重试等基础设施。
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    API_COOKIE,
    API_URL,
    BACKOFF_BASE,
    BACKOFF_MAX,
    CACHE_DIR,
    MAX_RETRIES,
    PROGRESS_LOG,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
    ensure_directories,
)


class ApiAccessDenied(RuntimeError):
    """远端 API 要求认证或拒绝当前调用。"""

# ============================================================================
# 日志
# ============================================================================


def setup_logging() -> logging.Logger:
    """配置日志系统：同时输出到控制台和文件。

    Returns:
        配置好的 Logger 实例。
    """
    ensure_directories()

    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    logger = logging.getLogger("bandori")
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(console)

    # 文件 handler
    file_handler = logging.FileHandler(
        PROGRESS_LOG, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()

# ============================================================================
# 全局统计
# ============================================================================


class Stats:
    """爬取统计信息收集器。"""

    def __init__(self) -> None:
        self.start_time: datetime = datetime.now()
        self.pages_crawled: int = 0
        self.pages_failed: int = 0
        self.pages_skipped: int = 0
        self.categories_visited: int = 0
        self.markdown_count: int = 0
        self.retry_count: int = 0
        self.redirects_followed: int = 0

    @property
    def elapsed(self) -> timedelta:
        """已耗时。"""
        return datetime.now() - self.start_time

    def summary(self) -> str:
        """生成统计摘要。

        Returns:
            格式化的统计字符串。
        """
        lines = [
            "",
            "=" * 50,
            "  爬取统计",
            "=" * 50,
            f"  页面数量:        {self.pages_crawled}",
            f"  分类数量:        {self.categories_visited}",
            f"  Markdown 数量:   {self.markdown_count}",
            f"  重定向跟随:      {self.redirects_followed}",
            f"  跳过（已缓存）:   {self.pages_skipped}",
            f"  失败:            {self.pages_failed}",
            f"  总重试次数:      {self.retry_count}",
            f"  总耗时:          {self.elapsed}",
            "=" * 50,
        ]
        return "\n".join(lines)


stats = Stats()

# ============================================================================
# 中断处理
# ============================================================================

_interrupted: bool = False


def _signal_handler(signum: int, frame: Any) -> None:
    """处理 SIGINT / Ctrl+C，设置中断标志。"""
    global _interrupted
    _interrupted = True
    logger.warning("\n⚠ 收到中断信号，正在安全退出...（再按一次强制退出）")


signal.signal(signal.SIGINT, _signal_handler)


def is_interrupted() -> bool:
    """检查是否收到中断信号。"""
    return _interrupted


# ============================================================================
# HTTP 会话与限速
# ============================================================================


class RateLimiter:
    """简单的令牌桶限速器 —— 保证最小请求间隔。"""

    def __init__(self, min_interval: float = REQUEST_DELAY) -> None:
        self._min_interval: float = min_interval
        self._last_request: float = 0.0

    def wait(self) -> None:
        """等待直到可以发送下一个请求。"""
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()


_rate_limiter = RateLimiter()


def create_session() -> requests.Session:
    """创建配置好重试策略和 User-Agent 的 requests Session。

    Returns:
        配置好的 Session 对象。
    """
    session = requests.Session()

    # 重试策略（仅对连接/读取错误重试，不对 HTTP 错误码重试）
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_BASE,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    })
    if API_COOKIE:
        session.headers["Cookie"] = API_COOKIE

    return session


# 全局会话（复用连接）
_session: requests.Session | None = None


def get_session() -> requests.Session:
    """获取或创建全局 HTTP 会话。"""
    global _session
    if _session is None:
        _session = create_session()
    return _session


def api_get(params: dict[str, Any]) -> dict[str, Any] | None:
    """调用 MediaWiki API，带限速、重试和指数退避。

    Args:
        params: API 查询参数（不含 format=json，会自动添加）。

    Returns:
        API 响应 JSON，失败返回 None。
    """
    _rate_limiter.wait()

    params = dict(params)  # 不修改调用者传入的字典
    params.setdefault("format", "json")

    session = get_session()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(
                API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            # 检查 MediaWiki 层面的错误
            if "error" in data:
                error_info = data["error"]
                error_code = error_info.get("code", "unknown")
                error_message = error_info.get("info", str(error_info))
                logger.error(
                    "API 错误: %s - %s",
                    error_code,
                    error_message,
                )
                if error_code == "action-notallowed":
                    raise ApiAccessDenied(
                        "萌娘百科拒绝匿名 API 查询。请先登录萌娘百科，再通过 "
                        "MOEGIRL_COOKIE 环境变量提供当前会话 Cookie。"
                    )
                return None

            return data

        except ApiAccessDenied:
            raise
        except requests.exceptions.Timeout:
            logger.warning(
                "请求超时 (第 %d/%d 次): %s", attempt, MAX_RETRIES, params.get("titles", "")
            )
        except requests.exceptions.ConnectionError as e:
            logger.warning(
                "连接错误 (第 %d/%d 次): %s", attempt, MAX_RETRIES, e
            )
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            logger.warning(
                "HTTP %s (第 %d/%d 次)", status, attempt, MAX_RETRIES
            )
            # 4xx 客户端错误（非 429）不重试
            if status != 429 and (isinstance(status, int) and 400 <= status < 500):
                return None
        except requests.exceptions.RequestException as e:
            logger.warning(
                "请求异常 (第 %d/%d 次): %s", attempt, MAX_RETRIES, e
            )
        except Exception as e:
            logger.error("未知错误: %s", e)
            return None

        # 指数退避
        if attempt < MAX_RETRIES:
            delay = min(BACKOFF_BASE * (2 ** (attempt - 1)), BACKOFF_MAX)
            logger.debug("等待 %.1f 秒后重试...", delay)
            time.sleep(delay)
            stats.retry_count += 1

    logger.error("已达最大重试次数: %s", params.get("titles", ""))
    return None


def check_interrupt() -> None:
    """检查中断标志，若已设置则抛出 KeyboardInterrupt。"""
    if _interrupted:
        raise KeyboardInterrupt()
