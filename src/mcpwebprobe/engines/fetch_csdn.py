from __future__ import annotations

from typing import Dict

from mcpwebprobe.utils.csdn import fetch_csdn_article as _fetch_csdn_article


async def fetch_csdn_article(url: str) -> Dict[str, str]:
    """
    Fetch a CSDN article, returning a dict with the readable "content".
    """
    return await _fetch_csdn_article(url)
