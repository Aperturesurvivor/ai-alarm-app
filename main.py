# main.py
import os
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from mastodon import Mastodon
import openai

app = FastAPI()

# Replace with your OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Replace with your Mastodon credentials
MASTODON_API_BASE_URL = os.getenv("MASTODON_API_BASE_URL")  # e.g., https://mastodon.social
MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")

openai.api_key = OPENAI_API_KEY

mastodon_client = Mastodon(
    access_token=MASTODON_ACCESS_TOKEN,
    api_base_url=MASTODON_API_BASE_URL,
)

class Bot(BaseModel):
    id: int
    name: str
    prompt: str
    post_interval_minutes: int

bots = []
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    scheduler.start()

@app.get("/bots", response_model=List[Bot])
async def list_bots():
    return bots

@app.post("/bots", response_model=Bot)
async def create_bot(bot: Bot):
    # Simple uniqueness check for id
    if any(b.id == bot.id for b in bots):
        raise HTTPException(status_code=400, detail="Bot with this ID already exists")
    bots.append(bot)
    # Schedule posting job
    scheduler.add_job(
        post_content_job,
        'interval',
        minutes=bot.post_interval_minutes,
        args=[bot],
        id=f"bot_{bot.id}",
        replace_existing=True,
    )
    return bot

async def generate_content(prompt: str) -> str:
    # Use OpenAI to generate a short post based on the prompt
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.8,
        )
        content = response.choices[0].message.content.strip()
        return content
    except Exception as e:
        print(f"OpenAI generation error: {e}")
        return ""

def post_to_mastodon(text: str):
    try:
        mastodon_client.status_post(text)
        print(f"Posted to Mastodon: {text}")
    except Exception as e:
        print(f"Mastodon post error: {e}")

def post_content_job(bot: Bot):
    print(f"Running scheduled post for bot {bot.name}")
    content = asyncio.run(generate_content(bot.prompt))
    if content:
        post_to_mastodon(content)
    else:
        print(f"No content generated for bot {bot.name}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
