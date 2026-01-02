import os
import time
from dotenv import load_dotenv
import logging

logger = logging.getLogger("hoopr")

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")

def get_openai_client():    
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    return client

def get_gemini_client():
    """
    Get Gemini client - uses old API (google.generativeai) which is stable
    
    Returns:
        genai module configured with API key
    """
    # Check for API key first
    if not gemini_api_key:
        error_msg = (
            "GEMINI_API_KEY not found in environment variables.\n"
            "Please add GEMINI_API_KEY=your_api_key_here to your .env file.\n"
            "You can get your API key from: https://aistudio.google.com/apikey"
        )
        logger.error(error_msg)
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    
    # Use the stable google.generativeai package (works reliably)
    # Note: google.genai is the new package but has different API structure
    import google.generativeai as genai
    genai.configure(api_key=gemini_api_key)
    return genai

def get_completion_openai(prompt: str):
    client = get_openai_client()
    # Using responses API format
    response = client.responses.create(
        model="o3-2025-04-16",
        input=prompt
    )
    return response.output_text

def get_completion_gemini(prompt: str, model_name: str = "gemini-2.0-flash-exp"):
    """
    Get completion from Gemini model
    
    Args:
        prompt: Input prompt
        model_name: Gemini model to use (default: "gemini-2.0-flash-exp")
        
    Returns:
        Response text from Gemini
    """
    try:
        genai = get_gemini_client()
        # Use old API (google.generativeai) - stable and working
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
            
    except ValueError as e:
        # Re-raise ValueError (missing API key) with better message
        raise e
    except Exception as e:
        logger.error(f"❌ Gemini API error: {e}")
        raise

def get_completion(prompt: str, is_json=True):
    # Simplified - always use Gemini, no email routing
    if is_json:
        prompt = f"{prompt}. Output should be valid JSON only, no markdown or commentary."
    
    # Log metadata only - not the full prompt (could be huge!)
    prompt_preview = prompt[:100].replace('\n', ' ')  # First 100 chars on one line
    logger.info(f"Getting completion for prompt: {prompt_preview}... ({len(prompt)} chars)")
    
    start_time = time.time()
    
    # Always use Gemini
    logger.info("Getting completion using Gemini")
    response_text = get_completion_gemini(prompt)
    
    seconds = time.time() - start_time
    
    # ✅ FIX: Log metadata only, not full response
    response_length = len(response_text)
    logger.info(f"✅ Completion received in {seconds:.2f}s ({response_length} chars)")
    
    # Optional: Log first 100 chars for debugging (only if needed)
    # logger.debug(f"Response preview: {response_text[:100]}...")
    
    return response_text