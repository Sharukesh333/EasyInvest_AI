# modules/gpt_service.py
"""Service module providing LLM responses via OpenAI API.
This acts as a placeholder for the selected GPT-OSS 120B model.
If an appropriate local model implementation is available, replace the implementation accordingly.
"""
import os
import json

# Attempt to import OpenAI library; if unavailable, raise informative error.
try:
    import openai
except ImportError as e:
    raise ImportError("openai library is required for gpt_service. Install with 'pip install openai'.") from e


def generate_response(prompt: str, chat_history: list = None) -> str:
    """Send a prompt (and optional recent chat history) to the LLM and return its response.

    Parameters
    ----------
    prompt: str
        The user prompt to send to the model.
    chat_history: list of dict, optional
        Each dict should have keys 'sender' ('user' or 'ai') and 'message'.
        The last 5 messages are included to provide context.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set for GPT service.")
    openai.api_key = api_key

    # Build messages list for ChatCompletion API
    messages = []
    if chat_history:
        for entry in chat_history[-5:]:
            role = "assistant" if entry.get("sender") == "ai" else "user"
            messages.append({"role": role, "content": entry.get("message", "")})
    # Append current user prompt
    messages.append({"role": "user", "content": prompt})

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # placeholder; replace with GPT-OSS model identifier when available
        messages=messages,
        temperature=0.7,
    )
    # Extract reply text
    reply = response.choices[0].message.content.strip()
    return reply
