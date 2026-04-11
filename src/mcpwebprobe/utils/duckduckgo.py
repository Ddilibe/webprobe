# duckduckgo_search_improved.py
import asyncio
import json
import re
from typing import List, Optional
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from mcpwebprobe.types import SearchResult
from src.utils.http_request import build_http_request_options, BuildHttpRequestOptions


class DuckDuckGoSearch:
    """DuckDuckGo search client with improved error handling"""
    
    def __init__(self):
        self.timeout = 30.0
        self.max_retries = 3
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Main search method with retry logic"""
        # Try preload URL method first
        results = await self._search_preload_url(query, limit)
        if results:
            return results
        
        # Fall back to HTML method
        return await self._search_html(query, limit)
    
    async def _search_preload_url(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using preload URL method"""
        results = []
        offset = 0
        
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            # Get initial page to extract preload URL
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
            
            search_url = f"https://duckduckgo.com/?q={httpx.quote(query)}&t=h_&ia=web"
            response = await client.get(search_url, headers=headers)
            
            # Extract preload URL
            base_preload_url = self._extract_preload_url(response.text)
            if not base_preload_url:
                return []
            
            # Parse and paginate
            parsed_url = urlparse(base_preload_url)
            query_params = parse_qs(parsed_url.query)
            
            while len(results) < max_results:
                query_params['s'] = [str(offset)]
                new_query = urlencode(query_params, doseq=True)
                page_url = urlunparse(parsed_url._replace(query=new_query))
                
                # Request data page
                data_response = await client.get(page_url, headers=headers)
                page_results, new_offset = self._parse_jsonp_response(data_response.text, offset, max_results - len(results))
                
                if not page_results:
                    break
                
                results.extend(page_results)
                offset = new_offset
            
            return results[:max_results]
    
    async def _search_html(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using HTML endpoint"""
        results = []
        offset = 0
        url = "https://html.duckduckgo.com/html/"
        
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "*/*",
            }
            
            # First request
            response = await client.post(url, headers=headers, data={"q": query})
            page_results = self._parse_html_response(response.text)
            results.extend(page_results[:max_results])
            
            # Pagination
            while len(results) < max_results and page_results:
                offset += len(page_results)
                response = await client.post(
                    url,
                    headers=headers,
                    data={
                        "q": query,
                        "s": str(offset),
                        "dc": str(offset),
                        "v": "l",
                        "o": "json",
                        "api": "d.js"
                    }
                )
                page_results = self._parse_html_response(response.text)
                results.extend(page_results[:max_results - len(results)])
            
            return results[:max_results]
    
    def _extract_preload_url(self, html: str) -> Optional[str]:
        """Extract preload URL from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Method 1: Check preload links
        for link in soup.find_all('link', rel='preload'):
            href = link.get('href')
            if href and 'links.duckduckgo.com/d.js' in href:
                return href
        
        # Method 2: Check script tag
        script = soup.find('script', id='deep_preload_script')
        if script and script.get('src'):
            src = script.get('src')
            if 'links.duckduckgo.com/d.js' in src:
                return src
        
        # Method 3: Regex fallback
        match = re.search(r'https://links\.duckduckgo\.com/d\.js\?[^"\']+', html, re.IGNORECASE)
        if match:
            return match.group(0)
        
        return None
    
    def _parse_jsonp_response(self, text: str, current_offset: int, max_results: int) -> tuple[List[SearchResult], int]:
        """Parse JSONP response and extract results"""
        results = []
        valid_count = 0
        
        match = re.search(r'DDG\.pageLayout\.load\(\'d\',\s*(\[.*?\])\s*\);', text, re.DOTALL)
        if not match:
            return results, current_offset
        
        try:
            data = json.loads(match.group(1))
            for item in data:
                if item.get('n'):  # Skip navigation items
                    continue
                
                valid_count += 1
                if len(results) >= max_results:
                    break
                
                results.append(SearchResult(
                    title=item.get('t', ''),
                    url=item.get('u', ''),
                    description=item.get('a', ''),
                    source=item.get('i') or item.get('sn') or '',
                    engine='duckduckgo'
                ))
            
            new_offset = current_offset + valid_count
            return results, new_offset
            
        except json.JSONDecodeError:
            return results, current_offset
    
    def _parse_html_response(self, html: str) -> List[SearchResult]:
        """Parse HTML response and extract results"""
        results = []
        soup = BeautifulSoup(html, 'html.parser')
        
        for item in soup.find_all('div', class_='result'):
            # Skip advertisements
            if 'result--ad' in item.get('class', []):
                continue
            
            title_el = item.find('a', class_='result__a')
            if not title_el:
                continue
            
            title = title_el.get_text(strip=True)
            url = title_el.get('href', '')
            
            if not title or not url:
                continue
            
            snippet_el = item.find(class_='result__snippet')
            source_el = item.find(class_='result__url')
            
            results.append(SearchResult(
                title=title,
                url=url,
                description=snippet_el.get_text(strip=True) if snippet_el else '',
                source=source_el.get_text(strip=True) if source_el else '',
                engine='duckduckgo'
            ))
        
        return results


# Singleton instance
_default_search = None


def get_duckduckgo_search() -> DuckDuckGoSearch:
    """Get default DuckDuckGo search instance"""
    global _default_search
    if _default_search is None:
        _default_search = DuckDuckGoSearch()
    return _default_search


async def search_duckduck_go(query: str, limit: int) -> List[SearchResult]:
    """Convenience function for DuckDuckGo search"""
    search = get_duckduckgo_search()
    return await search.search(query, limit)


def search_duckduck_go_sync(query: str, limit: int) -> List[SearchResult]:
    """Synchronous convenience function"""
    return asyncio.run(search_duckduck_go(query, limit))