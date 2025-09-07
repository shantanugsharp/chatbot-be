import os
import time
from dotenv import load_dotenv
import logging

logger = logging.getLogger("hoopr")

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

def get_openai_client():
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    return client

def get_completion_openai(prompt: str):
    client = get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.7
    )
    return response.choices[0].message.content

def get_completion(prompt: str, is_json=True):
    # Simplified - always use OpenAI, no email routing
    if is_json:
        prompt = f"{prompt}. Output should be valid JSON only, no markdown or commentary."
    
    logger.info(f"Getting completion for prompt: {prompt}")
    start_time = time.time()
    
    # Always use OpenAI
    logger.info("Getting completion using OpenAI")
    response_text = get_completion_openai(prompt)
    
    seconds = time.time() - start_time
    logger.info(f"Completion response in {seconds}: {response_text}")
    return response_text
