from bs4 import BeautifulSoup
import aiohttp
from typing import List, Dict
import logging
from urllib.parse import quote, urljoin
import asyncio

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class SearchService:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session = None
        self.base_url = "https://html.duckduckgo.com/html/"

    async def _ensure_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
            logger.info("Created new aiohttp session")

    async def _fetch_page_content(self, url: str) -> str:
        """Fetch and extract content from a webpage"""
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Successfully fetched page: {url}")
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Remove script, style, nav, footer elements
                    for elem in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                        elem.decompose()
                    
                    # Get main content (prioritize article or main tags)
                    main_content = soup.find(['article', 'main']) or soup
                    
                    # Get text and clean it
                    text = ' '.join(main_content.stripped_strings)
                    return text[:10000]  # Increased limit to 10K chars
                else:
                    logger.warning(f"Failed to fetch page {url}, status: {response.status}")
                    return ""
        except Exception as e:
            logger.error(f"Error fetching page {url}: {str(e)}")
            return ""

    async def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """Perform web search and process results"""
        try:
            await self._ensure_session()
            logger.info(f"Starting search for query: {query}")
            
            # Add request logging
            logger.info(f"Sending request to: {self.base_url}")
            logger.info(f"Search parameters: {query}")
            
            async with self.session.post(
                self.base_url, 
                data={'q': query, 'kl': 'us-en', 't': 'h_', 'ia': 'web'},
                timeout=30
            ) as response:
                logger.info(f"Search response status: {response.status}")
                
                if response.status != 200:
                    logger.error(f"Search failed with status {response.status}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                results = []
                
                # Find all search results
                for result in soup.select('.links_main')[:max_results]:
                    try:
                        title_elem = result.select_one('a.result__a')
                        snippet_elem = result.select_one('.result__snippet')
                        
                        if not title_elem:
                            continue
                            
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '')
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        
                        if url and url.startswith('http'):
                            logger.info(f"Processing result: {title[:30]}...")
                            
                            # Fetch full content
                            content = await self._fetch_page_content(url)
                            
                            results.append({
                                'title': title,
                                'content': content or snippet,
                                'source': url,
                                'snippet': snippet,
                                'error': False
                            })
                            logger.info(f"Added result: {title[:30]}...")
                    except Exception as e:
                        logger.error(f"Error processing result: {str(e)}")
                        continue
                
                logger.info(f"Search completed with {len(results)} results")
                return results

        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return []
            
    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

# Create singleton instance
search_service = SearchService() 