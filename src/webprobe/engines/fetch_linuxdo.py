from __future__ import annotations

import re
from typing import Dict

from bs4 import BeautifulSoup

from webprobe.utils.http_client import AsyncHttpClient, BuildHttpRequestOptions

_async_http_client = AsyncHttpClient()


async def fetch_linuxdo_article(url: str) -> Dict[str, str]:
    match = re.search(r"/topic/(\d+)", url)
    topic_id = match.group(1) if match else None
    if not topic_id:
        raise ValueError("Invalid linux.do URL; cannot extract topic id.")

    api_url = f"https://linux.do/t/{topic_id}.json"
    response = await _async_http_client.request(
        "GET",
        api_url,
        options=BuildHttpRequestOptions(
            headers={
                "accept": "application/json, text/javascript, */*; q=0.01",
                "accept-language": "zh-CN,zh;q=0.9",
                "cache-control": "no-cache",
                "discourse-track-view": "true",
                "discourse-track-view-topic-id": topic_id,
                "pragma": "no-cache",
                "referer": "https://linux.do/search",
                "sec-ch-ua": '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                "x-csrf-token": "K7YORqytPH8vZTM48iHLitfzv4NfU9GuiL1992MKuIBoviOCHyJk_w0LvTkfsX2bjn8ueXKzIGU8Uf8tzoxldg",
                "x-requested-with": "XMLHttpRequest",
                "Cookie": "_ga=GA1.1.1014556084.1750571986; cf_clearance=OHwsuY8kOismHG8rBN1tCKczIEyTdoJrMPH65aPVUSI-1750571989-1.2.1.1-uJ4vrRUBXQtFG8Ws7JrPw0VNT8_YWVWOz1GSvHyAWTCUPPC8PNqnKApl9hVhLHHs4kB.sQ4B0V54VEwG.RT23ewifTx0rifGNIVItA1Tt5Sq1M78h7sqlwaW7p0vWYuAasaSwcZLKElbcwIxDGd4_EU44Lss.jIl0p9PYPa9QWlUCtbwHISkR8lt8zHtX_YIFrU25pjsHLkLqzYgk7mpmEwAaryi4wgxoc7R0u_FqP5kD1Fq4t559mXPdvj3H23004H12XYT95hHNudrfmHUbO6yLzrspsmV0rdUxJHLwCtI_0aK6JvrQNGJpU13_XS0Q8R_WKOLYrVgHLC_wmg_YOJJ2tMRkJFt_yV2pHV0JPLCvN5I986ooXiLXkVAWvNQ; __stripe_mid=45e0bc73-88a1-4392-9a8e-56b3ad60d5017557f5; __stripe_sid=23ed10a8-f6f4-4cd8-948b-386cb239067ad435dc; _ga_1X49KS6K0M=GS2.1.s1750571986$o1$g1$t1750571999$j47$l0$h1911122445",
                "Host": "linux.do",
                "Connection": "keep-alive",
            },
            timeout=30.0,
            validate_status=lambda status: status < 400,
        ),
    )

    payload = response.json()
    cooked = (
        payload.get("post_stream", {})
        .get("posts", [{}])[0]
        .get("cooked", "")
    )

    text = BeautifulSoup(cooked or "", "html.parser").get_text(separator="\n").strip()
    return {"content": text}
