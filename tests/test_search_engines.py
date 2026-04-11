import asyncio

import httpx
import pytest

from mcpwebprobe.engines import (
    baidu,
    brave,
    csdn,
    duckduckgo,
    exa,
    juejin,
    linuxdo,
    startpage,
)
from mcpwebprobe.types import SearchResult


@pytest.mark.asyncio
async def test_duckduckgo_parses_html(monkeypatch):
    html = """
    <div class='result'>
      <a class='result__a' href='https://example.com/result'>Result Title</a>
      <div class='result__snippet'>Snippet text</div>
      <div class='result__url'>example.com</div>
    </div>
    """

    async def fake_request(*_, **__):
        return httpx.Response(200, text=html)

    monkeypatch.setattr(duckduckgo._async_http_client, "request", fake_request)
    results = await duckduckgo.search_duckduckgo("test", 1)
    assert len(results) == 1
    assert results[0].url == "https://example.com/result"
    assert results[0].title == "Result Title"


@pytest.mark.asyncio
async def test_baidu_parses_html(monkeypatch):
    html = """
    <div class='result c-container'>
      <h3>
        <a href='https://baidu.example/result'>Baidu Title</a>
      </h3>
      <div class='c-abstract'>Description</div>
      <span class='f13'>source</span>
    </div>
    """

    async def fake_request(*_, **__):
        return httpx.Response(200, text=html)

    monkeypatch.setattr(baidu._async_http_client, "request", fake_request)
    results = await baidu.search_baidu("test", 1)
    assert results and results[0].title == "Baidu Title"


@pytest.mark.asyncio
async def test_brave_parses_html(monkeypatch):
    html = """
    <div id='results'>
      <div class='snippet'>
        <div class='result-content'>
          <a href='https://brave.example/result'>
            <div class='search-snippet-title'>Brave Title</div>
            <div class='site-name-wrapper'>brave.com</div>
          </a>
          <div class='generic-snippet'>desc</div>
        </div>
      </div>
    </div>
    """

    async def fake_request(*_, **__):
        return httpx.Response(200, text=html)

    monkeypatch.setattr(brave._async_http_client, "request", fake_request)
    results = await brave.search_brave("test", 1)
    assert results and results[0].title == "Brave Title"


@pytest.mark.asyncio
async def test_exa_returns_json(monkeypatch):
    payload = {
        "results": [
            {
                "title": "Exa Result",
                "url": "https://exa.example/result",
                "publishedDate": "2025-01-01T00:00:00",
                "author": "Agent",
            }
        ]
    }

    async def fake_request(*_, **__):
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(exa._async_http_client, "request", fake_request)
    results = await exa.search_exa("test", 1)
    assert results[0].url == "https://exa.example/result"


@pytest.mark.asyncio
async def test_csdn_search_json(monkeypatch):
    payload = {
        "result_vos": [
            {
                "title": "CSDN",
                "digest": "content",
                "url_location": "https://csdn.example",
                "nickname": "author",
            }
        ]
    }

    async def fake_request(*_, **__):
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(csdn._async_http_client, "request", fake_request)
    results = await csdn.search_csdn("test", 1)
    assert results[0].source == "author"


@pytest.mark.asyncio
async def test_juejin_search_json(monkeypatch):
    payload = {
        "err_no": 0,
        "data": [
            {
                "result_model": {
                    "article_id": "123",
                    "article_info": {
                        "title": "Juejin Title",
                        "view_count": 1,
                        "digg_count": 2,
                    },
                    "author_user_info": {"user_name": "Writer"},
                    "category": {"category_name": "Tech"},
                    "tags": [{"tag_name": "tag"}],
                },
            }
        ],
        "has_more": False,
        "cursor": "0",
    }

    async def fake_request(*_, **__):
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(juejin._async_http_client, "request", fake_request)
    results = await juejin.search_juejin("test", 1)
    assert any("Juejin Title" in r.title for r in results)


@pytest.mark.asyncio
async def test_startpage_search(monkeypatch):
    responses = iter(
        [
            httpx.Response(
                200,
                text="<form action='/sp/search'><input name='sc' value='token'/></form>",
            ),
            httpx.Response(
                200,
                text="""
                <a class='result-title result-link' href='https://startpage.example'>
                  <h2>Startpage Title</h2>
                  <p class='description'>desc</p>
                </a>
                """,
            ),
        ]
    )

    async def fake_request(*_, **__):
        return next(responses)

    monkeypatch.setattr(startpage._async_http_client, "request", fake_request)
    results = await startpage.search_startpage("test", 1)
    assert results[0].title == "Startpage Title"


@pytest.mark.asyncio
async def test_linuxdo_filters_results(monkeypatch):
    async def fake_bing(query, limit):
        return [
            SearchResult(
                title="Linux",
                url="https://linux.do/topic/1",
                description="desc",
                source="linux.do",
                engine="bing",
            )
        ]

    monkeypatch.setattr(linuxdo, "search_bing", fake_bing)
    monkeypatch.setattr(linuxdo, "search_brave", fake_bing)
    monkeypatch.setattr(linuxdo, "search_duckduckgo", fake_bing)
    results = await linuxdo.search_linuxdo("test", 2)
    assert all("linux.do" in r.url for r in results)
