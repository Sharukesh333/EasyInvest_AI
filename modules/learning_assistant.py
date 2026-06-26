"""
EasyInvest AI - Module 3: AI Learning Assistant
This module integrates Google's Gemini API client (using gemini-1.5-flash) to provide
highly interactive, context-aware, beginner-friendly financial definitions.
Includes high-fidelity local fallback libraries for offline testing.
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, List
import google.generativeai as genai
from dotenv import load_dotenv

# Global request tracking for Gemini free tier
_gemini_call_count = 0
_GEMINI_CALL_LIMIT = 5

load_dotenv()
if not os.getenv("GEMINI_API_KEY"):
    env_example = Path(__file__).parents[1] / ".env.example"
    if env_example.is_file():
        load_dotenv(dotenv_path=env_example)

# GEMINI API key should be set in a .env file as GEMINI_API_KEY=your_key
# The load_dotenv() call above loads it into the environment.
# No hardcoded keys or manual environment variable assignments are needed here.


def set_gemini_api_key(api_key: str) -> bool:
    """
    Sets the Gemini API key directly in the module.
    
    Args:
        api_key (str): The Gemini API key to configure.
        
    Returns:
        bool: True if key is set and SDK configured successfully, False otherwise.
    """
    if not api_key:
        return False
    
    try:
        os.environ["GEMINI_API_KEY"] = api_key
        genai.configure(api_key=api_key)
        return True
    except Exception:
        return False

def initialize_gemini() -> bool:
    """
    Reads the Gemini API key from environment variables and configures the SDK.
    
    Returns:
        bool: True if key is set and SDK configured, False otherwise.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return False
    
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception:
        return False

def get_financial_explanation(query: str, chat_history: List[Dict[str, str]] = None) -> str:
    """
    Interfaces with the Gemini SDK to get a friendly financial answer.
    Supports chat history contexts to enable continuous conversation.
    
    Args:
        query (str): The beginner question.
        chat_history (List[Dict[str, str]]): List of previous dialog blocks.
        
    Returns:
        str: Styled Markdown answer.
    """
    system_prompt = (
        "You are the EasyInvest AI Tutor, a friendly, highly knowledgeable financial advisor "
        "designed specifically to teach absolute beginners. "
        "Your goal is to explain financial concepts in simple, plain English without heavy jargon.\n\n"
        "Please format your responses beautifully using clear Markdown sections:\n"
        "1. **Core Meaning**: A one-sentence, intuitive summary of the concept.\n"
        "2. **Real-world Analogy**: A creative, non-financial analogy (sports, household items, cars, food, etc.).\n"
        "3. **Why it Matters**: Why a beginner investor should pay attention to this metric/concept.\n"
        "4. **Practical Example**: A short concrete example using hypothetical stock tickers (e.g. TCS, RELIANCE) to illustrate calculations.\n\n"
        "If the user is continuing a conversation (evident in chat history), answer their follow-up "
        "question in a natural, conversational way while maintaining these clear learning principles."
    )
    
    # Check if Gemini key is configured
    if not initialize_gemini():
        return get_offline_fallback(query)
        
    try:
        # Build prompt with history details
        prompt_parts = [system_prompt, "\n\n"]
        
        # Add past 4 messages for conversational context
        if chat_history:
            # Skip the first AI greetings message to focus context window on active questions
            for chat in chat_history[-4:]:
                role = "User" if chat["sender"] == "user" else "AI Tutor"
                prompt_parts.append(f"{role}: {chat['message']}\n")
                
        prompt_parts.append(f"User: {query}\nAI Tutor:")
        prompt = "".join(prompt_parts)
        
        # Call gemini-1.5-flash
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        # Handle rate limit errors (429) by waiting and retrying once
        if "429" in str(e):
            try:
                # Extract retry delay if present, default 20 seconds
                delay = 20
                # Simple wait before retry
                time.sleep(delay)
                response = model.generate_content(prompt)
                return response.text
            except Exception:
                pass
        # Fall back to offline explanations in case of network or key errors
        return f"### AI Connection Alert\nGemini API client could not complete the request: `{str(e)}`\n\n" + get_offline_fallback(query)

def get_offline_fallback(term: str) -> str:
    """
    Standard high-fidelity pre-compiled explanations for offline or keyless testing.
    
    Args:
        term (str): Query terms.
        
    Returns:
        str: Markdown explanation.
    """
    term_upper = term.upper().strip()
    
    if "PE RATIO" in term_upper or "P/E" in term_upper:
        return (
            "### Price-to-Earnings (P/E) Ratio Explained (Offline Mode)\n\n"
            "**1. Core Meaning**\n"
            "The P/E Ratio tells you how much money you are paying for every ₹1 of net profit a company generates.\n\n"
            "**2. Real-world Analogy**\n"
            "Imagine buying a local grocery store. If it makes ₹1,000 profit a year, and the owner sells it to you for ₹10,000, "
            "you bought it at a **P/E of 10**. If they wanted ₹30,000, it would be a P/E of 30.\n\n"
            "**3. Why it Matters**\n"
            "It is a quick health-check to see if a stock's current price is over-inflated (too expensive) or a discount compared to similar companies.\n\n"
            "**4. Practical Example**\n"
            "- **TCS.NS** is selling at ₹4,000 with annual earnings of ₹100 per share. **P/E = 40** (₹4000 / ₹100).\n"
            "- **INFY.NS** is selling at ₹1,500 with annual earnings of ₹50 per share. **P/E = 30** (₹1500 / ₹50).\n"
            "This suggests Infosys is relatively cheaper relative to its profits."
        )
    elif "RSI" in term_upper or "RELATIVE STRENGTH" in term_upper:
        return (
            "### Relative Strength Index (RSI) Explained (Offline Mode)\n\n"
            "**1. Core Meaning**\n"
            "RSI is a momentum meter between 0 and 100 that tracks how fast and drastically a stock's price is moving.\n\n"
            "**2. Real-world Analogy**\n"
            "Think of a rubber band. If you stretch it too far in one direction (prices rising extremely fast), it becomes 'Overbought' "
            "and will eventually snap back to its rest state. If you compress it too much, it is 'Oversold'.\n\n"
            "**3. Why it Matters**\n"
            "It gives beginners buying/selling signals: RSI above **70** signals the stock is overbought (prices may pull back), while RSI below **30** signals it is oversold (potential bargain buying window).\n\n"
            "**4. Practical Example**\n"
            "If Tata Motors runs from ₹900 to ₹1,050 in 4 days, its RSI might shoot up to **76**. This indicates buying momentum is overextended, "
            "warning you not to chase the stock at its current peak."
        )
    elif "MARKET CAP" in term_upper:
        return (
            "### Market Capitalization Explained (Offline Mode)\n\n"
            "**1. Core Meaning**\n"
            "Market Cap is the total dollar/rupee cost to buy 100% of a public company's shares. It represents the net size of a business.\n\n"
            "**2. Real-world Analogy**\n"
            "If a local residential society has 10 houses, and each house is valued at ₹1 Crore, the total value of the society is ₹10 Crores. "
            "That total valuation is the 'Market Cap' of the society.\n\n"
            "**3. Why it Matters**\n"
            "It segments companies so you understand their stability:\n"
            "- **Large-Caps** (above ₹20,000 Crore): Giant, stable leaders (TCS, Reliance).\n"
            "- **Mid-Caps** (₹5,000 - ₹20,000 Crore): Fast-growing, moderate risk.\n"
            "- **Small-Caps** (under ₹5,000 Crore): High-risk, hyper-growth startups.\n\n"
            "**4. Practical Example**\n"
            "If a business has 1 Crore shares outstanding trading at ₹200 each, its **Market Capitalization is ₹200 Crores** (10,000,000 shares x ₹200)."
        )
    elif "DIVIDEND" in term_upper:
        return (
            "### Dividend Explained (Offline Mode)\n\n"
            "**1. Core Meaning**\n"
            "A dividend is a direct cash payment distributed to company shareholders from the company's accumulated net profits.\n\n"
            "**2. Real-world Analogy**\n"
            "Think of owning an investment apartment. In addition to the apartment's value changing on the market, you get periodic "
            "rent payments from your tenant. Dividends are like 'company rent' paid directly to you.\n\n"
            "**3. Why it Matters**\n"
            "Dividends provide stable, passive, regular income, typically paid by mature, cash-rich large-cap giants like ITC or Coal India.\n\n"
            "**4. Practical Example**\n"
            "If TCS declares a dividend of ₹20 per share, and you own **15 shares** of TCS.NS, they will deposit **₹300** cash directly into your savings account."
        )
    elif "NSE" in term_upper or "NATIONAL STOCK EXCHANGE" in term_upper:
        return (
            "### National Stock Exchange (NSE) Explained (Offline Mode)\n\n"
            "**1. Core Meaning**\n"
            "The NSE is India's largest stock exchange by trading volume, where public company shares are bought and sold electronically.\n\n"
            "**2. Real-world Analogy**\n"
            "Think of NSE as a giant marketplace for company shares, like a farmer's market but for stocks. Instead of buying vegetables from different farmers, "
            "you buy shares of different companies. The ticker suffix **.NS** means the stock trades on NSE.\n\n"
            "**3. Why it Matters**\n"
            "NSE is where individual investors like you participate in wealth creation. It's regulated, transparent, and provides fair pricing for stocks. "
            "Most major Indian companies (TCS, Infosys, Reliance) list here.\n\n"
            "**4. Practical Example**\n"
            "When you buy **TCS.NS** or **INFY.NS**, you're purchasing shares through the National Stock Exchange. The .NS suffix tells you it's an NSE-listed stock. "
            "You can trade during market hours (9:15 AM - 3:30 PM on weekdays) through your broker's app or website."
        )
    else:
        return (
            f"### Financial Explanation: {term} (Offline Mode)\n\n"
            f"To get highly interactive, custom answers for '*{term}*', please insert a valid `GEMINI_API_KEY` in the left sidebar configuration panel.\n\n"
            f"**Tutor Tip for Beginners:**\n"
            f"Always master fundamental ratios (P/E ratio, Market Cap) and financial concepts (compound interest, inflation) before trading speculative technical signals."
        )
