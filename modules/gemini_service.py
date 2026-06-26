import os
import google.generativeai as genai
from typing import List, Dict, Optional

# Global model instance (lazy-loaded)
_model = None

def set_gemini_api_key(api_key: str) -> bool:
    """Store the API key in environment and configure the Gemini client.

    Returns True if configuration succeeds, False otherwise.
    """
    if not api_key:
        return False
    os.environ["GEMINI_API_KEY"] = api_key
    try:
        genai.configure(api_key=api_key)
        # Initialize model lazily
        global _model
        _model = None
        return True
    except Exception as e:
        # Configuration failed (invalid key, network, etc.)
        print(f"Gemini configuration error: {e}")
        return False

def _ensure_model():
    """Instantiate the Gemini model if not already done.
    Uses gemini-1.5-flash.
    """
    global _model
    if _model is None:
        try:
            _model = genai.GenerativeModel("gemini-1.5-flash")
        except Exception as e:
            raise RuntimeError(f"Failed to create Gemini model: {e}")
    return _model

def generate_response(prompt: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
    """Send a prompt (with optional history) to Gemini and return the markdown response.

    Parameters
    ----------
    prompt: str
        Full prompt to the model. Should already contain system instructions and user query.
    chat_history: list of dict, optional
        Each dict has ``"sender"`` ("user" or "ai") and ``"message"``. Converted into a simple conversation string.
    """
    model = _ensure_model()
    # Build a combined prompt if history provided
    if chat_history:
        history_str = "\n".join([
            f"User: {c['message']}" if c['sender'] == 'user' else f"AI: {c['message']}"
            for c in chat_history[-5:]
        ])
        full_prompt = f"{history_str}\nUser: {prompt}\nAI:"  # Ensure model replies as AI
    else:
        full_prompt = prompt
    try:
        response = model.generate_content(full_prompt)
        # Gemini returns a GenerativeModelResponse; we extract text.
        return response.text.strip()
    except Exception as e:
        raise RuntimeError(f"Gemini API request failed: {e}")
