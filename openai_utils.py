import os
import time
from dotenv import load_dotenv
import logging

logger = logging.getLogger("hoopr")

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")
# Default provider: "openai" or "gemini", can be overridden via env var
provider = os.getenv("AI_PROVIDER", "openai").lower()

def get_openai_client():
    """Get OpenAI client"""
    from openai import OpenAI
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    client = OpenAI(api_key=openai_api_key)
    return client

def get_gemini_client():
    """Get Google Gemini client using the new google.genai package"""
    try:
        import google.genai as genai
    except ImportError:
        raise ImportError("google-genai package not installed. Install it with: pip install google-genai")
    
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    
    # Initialize client with API key
    client = genai.Client(api_key=gemini_api_key)
    return client

def get_completion_openai(prompt: str, model: str = "o3-2025-04-16"):
    """Get completion from OpenAI"""
    client = get_openai_client()
    # Using responses API format
    try:
        response = client.responses.create(
            model=model,
            input=prompt
        )
        return response.output_text
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise

def get_completion_gemini(prompt: str, model: str = "gemini-2.5-flash"):
    """Get completion from Google Gemini using the new google.genai package"""
    client = get_gemini_client()
    
    try:
        # Use the correct API format: client.models.generate_content()
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        
        # The response has a 'text' attribute directly
        if hasattr(response, 'text') and response.text:
            return response.text
        
        # Fallback: try to extract from candidates if text is not directly available
        if hasattr(response, 'candidates') and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content'):
                content = candidate.content
                if hasattr(content, 'parts'):
                    # Extract text from all parts
                    text_parts = []
                    for part in content.parts:
                        if hasattr(part, 'text'):
                            text_parts.append(part.text)
                    if text_parts:
                        return ''.join(text_parts)
        
        # If we get here, something unexpected happened
        raise ValueError(f"Could not extract text from Gemini response. Response type: {type(response)}")
            
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise

def get_completion(prompt: str, is_json=True, provider_override: str = None, model: str = None):
    """
    Get completion from AI provider (OpenAI or Gemini)
    
    Args:
        prompt: The input prompt
        is_json: Whether to request JSON output
        provider_override: Override default provider ("openai" or "gemini")
        model: Override default model for the provider
    
    Returns:
        str: The completion response
    """
    # Determine which provider to use
    current_provider = provider_override or provider
    
    # Add JSON instruction if needed
    if is_json:
        prompt = f"{prompt}. Output should be valid JSON only, no markdown or commentary."
    
    logger.info(f"Getting completion for prompt (first 200 chars): {prompt[:200]}...")
    start_time = time.time()
    
    try:
        if current_provider == "gemini":
            logger.info("Getting completion using Gemini")
            # Default Gemini models: gemini-2.5-flash, gemini-1.5-pro, gemini-1.5-flash
            default_model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            response_text = get_completion_gemini(prompt, model=default_model)
        else:
            logger.info("Getting completion using OpenAI")
            # Default OpenAI model
            default_model = model or os.getenv("OPENAI_MODEL", "o3-2025-04-16")
            response_text = get_completion_openai(prompt, model=default_model)
        
        seconds = time.time() - start_time
        logger.info(f"Completion response in {seconds:.2f}s (first 200 chars): {response_text[:200]}...")
        return response_text
        
    except Exception as e:
        logger.error(f"Error getting completion from {current_provider}: {e}")
        # Fallback to other provider if one fails
        if current_provider == "gemini" and provider == "openai":
            logger.warning("Gemini failed, falling back to OpenAI")
            try:
                default_model = model or os.getenv("OPENAI_MODEL", "o3-2025-04-16")
                response_text = get_completion_openai(prompt, model=default_model)
                return response_text
            except:
                raise e
        elif current_provider == "openai" and provider == "gemini":
            logger.warning("OpenAI failed, falling back to Gemini")
            try:
                default_model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                response_text = get_completion_gemini(prompt, model=default_model)
                return response_text
            except:
                raise e
        else:
            raise