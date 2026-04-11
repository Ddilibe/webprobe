import httpx
import pytest

from webprobe.engines.fetch_csdn import fetch_csdn_article
from webprobe.engines.fetch_juejin import fetch_juejin_article
from webprobe.engines.fetch_linuxdo import fetch_linuxdo_article
from webprobe.engines.github import fetch_github_readme
import webprobe.utils.csdn as csdn_module


@pytest.mark.asyncio
async def test_fetch_csdn_article(monkeypatch):
    html = "<div id='content_views'><p>Secret content</p></div>"

    class DummyClient:
        async def request(self, *_args, **_kwargs):
            return httpx.Response(200, text=html)

    monkeypatch.setattr(
        csdn_module, "get_default_http_client", lambda: DummyClient()
    )
    monkeypatch.setattr(
        csdn_module, "build_request_options", lambda cookie=None: {}
    )
    result = await fetch_csdn_article("https://blog.csdn.net/example/article/details/1")
    assert "Secret content" in result["content"]


@pytest.mark.asyncio
async def test_fetch_linuxdo_article(monkeypatch):
    async def fake_request(*_, **__):
        payload = {
            "post_stream": {
                "posts": [
                    {"cooked": "<p>Linux do text</p>"}
                ]
            }
        }
        return httpx.Response(200, json=payload)

    monkeypatch.setattr("webprobe.engines.fetch_linuxdo._async_http_client.request", fake_request)
    result = await fetch_linuxdo_article("https://linux.do/topic/123")
    assert "Linux do text" in result["content"]


@pytest.mark.asyncio
async def test_fetch_juejin_article(monkeypatch):
    html = "<div class='article-content'><p>Juejin body</p></div>"

    async def fake_request(*_, **__):
        return httpx.Response(200, text=html)

    monkeypatch.setattr("webprobe.engines.fetch_juejin._async_http_client.request", fake_request)
    result = await fetch_juejin_article("https://juejin.cn/post/1")
    assert "Juejin body" in result["content"]


@pytest.mark.asyncio
async def test_fetch_github_readme(monkeypatch):
    async def fake_request(*_, **__):
        return httpx.Response(200, text="README content")

    monkeypatch.setattr("webprobe.engines.github._async_http_client.request", fake_request)
    assert await fetch_github_readme("https://github.com/example/repo") == "README content"
