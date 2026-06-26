import os
import streamlit as st
import google.generativeai as genai
from typing import List, Dict, Optional

# Global model instance
_model = None


def get_gemini_api_key():
    """
    Get Gemini API key.
    Works locally (.env) and Streamlit Cloud (secrets).
    """

    # Streamlit Cloud
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    # Local environment
    return os.getenv("GEMINI_API_KEY")


def set_gemini_api_key(api_key: str = None) -> bool:
    """
    Configure Gemini client.
    """

    if api_key is None:
        api_key = get_gemini_api_key()

    if not api_key:
        print("Gemini API key missing")
        return False

    try:
        os.environ["GEMINI_API_KEY"] = api_key

        genai.configure(api_key=api_key)

        global _model
        _model = None

        return True

    except Exception as e:
        print(f"Gemini configuration error: {e}")
        return False


def _ensure_model():
    """
    Create Gemini model lazily.
    """

    global _model

    if _model is None:

        # configure before creating model
        if not set_gemini_api_key():
            raise RuntimeError(
                "Gemini API key not found. Add GEMINI_API_KEY in Streamlit secrets."
            )

        try:
            _model = genai.GenerativeModel(
                "gemini-1.5-flash"
            )

        except Exception as e:
            raise RuntimeError(
                f"Failed to create Gemini model: {e}"
            )

    return _model



def generate_response(
    prompt: str,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Generate Gemini response.
    """

    model = _ensure_model()


    if chat_history:

        history = "\n".join(
            [
                (
                    f"User: {item['message']}"
                    if item["sender"] == "user"
                    else f"AI: {item['message']}"
                )
                for item in chat_history[-5:]
            ]
        )

        full_prompt = (
            f"{history}\n"
            f"User: {prompt}\n"
            "AI:"
        )

    else:
        full_prompt = prompt


    try:

        response = model.generate_content(
            full_prompt
        )

        return response.text.strip()


    except Exception as e:

        raise RuntimeError(
            f"Gemini API request failed: {e}"
        )