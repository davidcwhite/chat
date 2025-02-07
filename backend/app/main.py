from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from openai import OpenAI
import json
from typing import List, Dict
import asyncio
from bs4 import BeautifulSoup
import requests
import aiohttp
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import BeautifulSoupTransformer
import re
from datetime import datetime
from urllib.parse import quote
from .services.search import search_service
import logging

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

logger = logging.getLogger(__name__)

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

async def perform_web_search(query: str) -> List[Dict]:
    """Perform web search using crawl4ai"""
    try:
        results = await search_service.search(query)
        return results
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return []

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

@app.post("/chat")
async def chat(message: ChatMessage):
    try:
        # Check if this is a search query
        if message.message.startswith("[SEARCH]"):
            query = message.message[8:].strip()
            logger.info(f"Processing search query: {query}")
            
            # Use search service
            results = await search_service.search(query)
            
            if not results:
                search_results = "No relevant search results found."
            else:
                # Format search results with more content
                search_results = "\n\n".join([
                    f"Source: [{result['title']}]({result['source']})\n"
                    f"{result['snippet']}\n"
                    f"Content: {result['content'][:1000]}..."  # Increased to 1K chars
                    for result in results
                ])

            system_message = f"""You are a helpful assistant. Here are the search results for "{query}":

{search_results}

Please provide a clear summary of the information, including:
1. The most recent and relevant data
2. Direct quotes or numbers when available
3. Sources cited as markdown links
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

@app.get("/test-search")
async def test_search(query: str):
    """Test endpoint for search functionality"""
    try:
        results = await search_service.search(query)
        return {"status": "success", "results": results}
    except Exception as e:
        logger.error(f"Test search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 