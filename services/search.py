"""
全局搜索服务
"""

from __future__ import annotations


class SearchService:
    def __init__(self, index, formatter) -> None:
        self._index = index
        self._fmt = formatter

    async def query(self, keyword: str) -> tuple[str, str]:
        if not keyword.strip():
            return (self._fmt.format_help(), "")

        results = self._index.search(keyword, category="", limit=8)
        if results:
            return (self._fmt.format_search_results(results, keyword), "")

        return (self._fmt.format_not_found(keyword), "")
