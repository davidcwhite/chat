from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from openai import OpenAI
import json

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

class ChatMessage(BaseModel):
    message: str
    model: str = "gpt-4o-mini"  # Updated default to match new model name

@app.get("/")
async def read_root():
    return {"status": "healthy"}

@app.post("/chat")
async def chat(message: ChatMessage):
    try:
        # Map frontend model names to OpenAI model names
        model_mapping = {
            "o3-mini": "o3-mini-2025-01-31",
            "gpt-4o-mini": "gpt-4o-mini"
        }
        
        # Get the correct model ID, defaulting to gpt-4o-mini if not found
        model_id = model_mapping.get(message.model, "gpt-4-0125-preview")  # Changed default
        
        # Make a streaming call to OpenAI
        completion = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": """You are a helpful assistant that uses markdown formatting effectively. Always format your responses using:
                    - Headers with # for sections
                    - **Bold** for emphasis
                    - `code` for inline code
                    - ```language for code blocks
                    - * or - for bullet points
                    - 1. 2. 3. for numbered lists
                    - > for blockquotes
                    - [text](url) for links
                    - | tables | when | appropriate |
                    
                    Make your responses visually structured and easy to read."""},
                {"role": "user", "content": message.message}
            ],
            temperature=0.7,
            max_tokens=700,
            stream=True  # Enable streaming
        )
        
        async def generate():
            try:
                collected_chunks = []
                collected_messages = []

                # Iterate through the stream of events
                for chunk in completion:
                    if chunk.choices[0].delta.content is not None:
                        collected_chunks.append(chunk)  # save the event response
                        chunk_message = chunk.choices[0].delta.content  # extract the message
                        collected_messages.append(chunk_message)  # save the message
                        yield f"data: {json.dumps({'content': chunk_message})}\n\n"
                        
            except Exception as e:
                print(f"Error while streaming: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 