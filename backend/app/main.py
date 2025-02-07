from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from openai import OpenAI
import json
from typing import List
import asyncio
from bs4 import BeautifulSoup
import requests
import aiohttp
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import BeautifulSoupTransformer
import re
from datetime import datetime
from urllib.parse import quote

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_sp500_data() -> dict:
    """Fetch S&P 500 data from multiple financial sources"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # List of financial websites to try
    sources = [
        {
            'url': 'https://finance.yahoo.com/quote/%5EGSPC',
            'price_selector': 'fin-streamer[data-symbol="^GSPC"][data-field="regularMarketPrice"]',
            'time_selector': 'div#quote-market-notice',
        },
        {
            'url': 'https://www.marketwatch.com/investing/index/spx',
            'price_selector': 'bg-quote[class="value"]',
            'time_selector': 'div.timestamp__timestamp',
        },
        {
            'url': 'https://www.investing.com/indices/us-spx-500',
            'price_selector': 'div[data-test="instrument-price-last"]',
            'time_selector': 'time[data-test="instrument-price-timestamp"]',
        }
    ]
    
    results = []
    
    async with aiohttp.ClientSession() as session:
        for source in sources:
            try:
                async with session.get(source['url'], headers=headers, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'lxml')
                        
                        # Extract price
                        price_element = soup.select_one(source['price_selector'])
                        if price_element:
                            price = price_element.get_text().strip()
                            # Clean up price
                            price = re.sub(r'[^\d.,]', '', price)
                            
                            # Extract time
                            time_element = soup.select_one(source['time_selector'])
                            time_text = time_element.get_text().strip() if time_element else "Latest available"
                            
                            results.append({
                                'source': source['url'],
                                'price': price,
                                'time': time_text,
                                'raw_html': str(soup)[:1000]  # Store partial HTML for debugging
                            })
            except Exception as e:
                print(f"Error fetching from {source['url']}: {str(e)}")
                continue
    
    return results

async def perform_web_search(query: str, max_results: int = 3) -> list:
    try:
        if "s&p" in query.lower() and ("price" in query.lower() or "closing" in query.lower()):
            results = await get_sp500_data()
            
            if not results:
                return [{
                    'title': 'S&P 500 Data Not Available',
                    'link': 'https://finance.yahoo.com/quote/%5EGSPC',
                    'body': 'Could not fetch real-time S&P 500 data. Please check financial websites directly.'
                }]
            
            formatted_results = []
            seen_urls = set()  # Track unique URLs
            
            for result in results:
                if result['link'] not in seen_urls:  # Only add if URL is new
                    seen_urls.add(result['link'])
                    formatted_results.append({
                        'title': f"S&P 500 Price from {result['source'].split('/')[2]}",
                        'link': result['source'],
                        'body': f"Price: {result['price']}\nTime: {result['time']}"
                    })
            
            return formatted_results[:max_results]  # Ensure we don't exceed max_results
        else:
            # Use DuckDuckGo to get initial search results
            search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers) as response:
                    html = await response.text()
                    
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            # Find all result containers
            result_elements = soup.find_all('div', class_='result')[:max_results]
            urls = []
            
            for element in result_elements:
                try:
                    title_element = element.find('a', class_='result__a')
                    if not title_element:
                        continue
                        
                    title = title_element.text.strip()
                    link = title_element.get('href', '')
                    
                    if link and link.startswith('http'):
                        urls.append(link)
                        snippet_element = element.find('a', class_='result__snippet')
                        snippet = snippet_element.text.strip() if snippet_element else ""
                        
                        results.append({
                            'title': title,
                            'link': link,
                            'body': snippet
                        })
                except Exception as e:
                    print(f"Error processing search result: {str(e)}")
                    continue
            
            # Use LangChain's AsyncHtmlLoader for the top results
            if urls:
                try:
                    loader = AsyncHtmlLoader(urls)
                    docs = await loader.aload()
                    
                    # Transform HTML to readable text
                    bs_transformer = BeautifulSoupTransformer()
                    docs_transformed = bs_transformer.transform_documents(docs)
                    
                    # Update results with more detailed content
                    for i, doc in enumerate(docs_transformed[:len(results)]):
                        results[i]['body'] = doc.page_content[:500] + "..."  # Limit content length
                except Exception as e:
                    print(f"Error loading web content: {str(e)}")
                
            return results
    except Exception as e:
        print(f"Search error: {str(e)}")
        raise

class ChatMessage(BaseModel):
    message: str
    model: str = "gpt-4o-mini"  # Updated default to match new model name

# Add new model for search results
class SearchResult(BaseModel):
    title: str
    link: str
    snippet: str

@app.get("/")
async def read_root():
    return {"status": "healthy"}

@app.post("/search")
async def search(query: str, num_results: int = 3) -> List[SearchResult]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
            
        return [
            SearchResult(
                title=result['title'],
                link=result['link'],
                snippet=result['body']
            )
            for result in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(message: ChatMessage):
    try:
        if message.message.startswith("[SEARCH]"):
            query = message.message[8:].strip()
            print(f"Processing search query: {query}")
            
            try:
                results = await perform_web_search(query)
                
                if not results:
                    search_results = "No relevant search results found."
                else:
                    print(f"Found {len(results)} results")
                    search_results = "\n\n".join([
                        f"Source: {result['title']}\n"
                        f"URL: {result['link']}\n"
                        f"Summary: {result['body']}"
                        for result in results
                    ])
                    print(f"Search results being sent to model:\n{search_results}")
                
                system_message = f"""You are a helpful assistant that provides accurate information based on web search results.
                
                Search query: "{query}"
                
                Search Results:
                {search_results}
                
                Please provide a comprehensive answer using these search results. Your response should:
                1. Directly answer the query using the most recent information from the search results
                2. Include specific details, numbers, and dates from the search results
                3. Cite sources using markdown links like this: [Source Title](URL)
                4. Format the response clearly with markdown
                5. If the search results don't contain a direct answer, acknowledge this and suggest where to find the information
                6. For financial data or statistics, include the date/time of the information
                """
                print("System message created with search results")  # Debug log
            except Exception as e:
                print(f"Search error: {str(e)}")
                system_message = f"""You are a helpful assistant. The web search for "{query}" failed due to technical limitations. 
                Please inform the user that you couldn't perform the search right now and suggest they:
                1. Try again in a few moments
                2. Try rephrasing their query
                3. Consider checking popular websites directly for this information
                """
        else:
            system_message = """You are a helpful assistant that uses markdown formatting effectively. Always format your responses using:
                - Headers with # for sections
                - **Bold** for emphasis
                - `code` for inline code
                - ```language for code blocks
                - * or - for bullet points
                - 1. 2. 3. for numbered lists
                - > for blockquotes
                - [text](url) for links
                - | tables | when | appropriate |
                
                Make your responses visually structured and easy to read."""

        # Map frontend model names to OpenAI model names
        model_mapping = {
            "o3-mini": "o3-mini-2025-01-31",
            "gpt-4o-mini": "gpt-4o-mini"
        }
        
        # Create the chat completion
        print(f"Sending request to model with system message length: {len(system_message)}")  # Debug log
        completion = client.chat.completions.create(
            model=model_mapping.get(message.model, "gpt-4-0125-preview"),
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": message.message if not message.message.startswith("[SEARCH]") 
                                          else message.message[8:].strip()}
            ],
            temperature=0.7,
            max_tokens=1000,
            stream=True
        )
        
        async def generate():
            try:
                collected_messages = []
                last_message = ""  # Track the last message to prevent duplicates

                # Iterate through the stream of events
                for chunk in completion:
                    if chunk.choices[0].delta.content is not None:
                        chunk_message = chunk.choices[0].delta.content
                        if chunk_message != last_message:  # Only yield if content is new
                            collected_messages.append(chunk_message)
                            last_message = chunk_message
                            yield f"data: {json.dumps({'content': chunk_message})}\n\n"
                            
            except Exception as e:
                print(f"Error while streaming: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 