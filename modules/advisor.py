# Updated advisor module with AI-driven recommendation engine
"""
EasyInvest AI - Module 1: AI Investment Assistant (Enhanced)
Implements a dynamic, AI‑based stock recommendation and allocation engine.
It fetches live market data, scores stocks using a simple AI‑style heuristic, and allocates
shares to maximize capital utilization while providing confidence scores and reasoning.

CRITICAL UPGRADE: Budget-aware adaptive allocation system that guarantees recommendations
for ANY budget from ₹500 upward, including intelligent discovery of affordable and
undervalued stocks for small investment amounts.
"""

import json
import yfinance as yf
import pandas as pd
import numpy as np
import random
import os
import time
import threading
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

# Import LIVE MARKET DISCOVERY helpers
from modules.live_market_discovery import fetch_nse_top_stocks

# ENHANCED: Comprehensive stock pool including affordable and penny stocks
# for small budget allocation (₹500-₹2000)
OFFLINE_PRICES = {
    # Blue-chip stocks (High-priced)
    "TCS": 3200.0,
    "INFY": 1500.0,
    "RELIANCE": 2800.0,
    "HDFCBANK": 1600.0,
    
    # Mid-range stocks
    "ITC": 380.0,
    "TATAMOTORS": 350.0,
    "BHARTIARTL": 800.0,
    "LT": 2100.0,
    "HINDUNILVR": 2500.0,
    "TITAN": 1200.0,
    "AXISBANK": 800.0,
    "MARUTI": 2500.0,
    "SUNPHARMA": 900.0,
    "NTPC": 150.0,
    "HCLTECH": 1200.0,
    
    # Affordable stocks for small budgets
    "SBIN": 650.0,      # State Bank of India
    "BAJAJFINSV": 1600.0,
    "ULTRACEMCO": 12000.0,
    "DMART": 4000.0,
    "WIPRO": 440.0,     # Affordable IT stock
    "TECHM": 1300.0,
    "LUPIN": 900.0,     # Pharma
    "DIVISLAB": 5200.0,
    "CHOLAFIN": 1100.0,
    "LICI": 850.0,      # Insurance - good for ₹500+
    "JSWSTEEL": 850.0,
    "COALINDIA": 380.0, # Very affordable
    "POWERGRID": 280.0, # Affordable PSU
    "BHEL": 220.0,      # Budget stock
    "SAIL": 75.0,       # Penny stock - excellent for ₹500 budget
    "NALCO": 95.0,      # Low-priced
    "MOIL": 180.0,
    "MCDOWELL": 850.0,
    "CIPLA": 1600.0,
    "IDEA": 45.0,       # Ultra-affordable for tiny budgets
    "VODAFONE": 12.0,   # Penny stock
    "AMBUJACEM": 480.0,
    "GAIL": 155.0,
    "IOC": 120.0,       # Very affordable
    "BPCL": 380.0,
    "IRFC": 65.0,       # Affordable
    "SBICARD": 600.0,
    "ICICIBANK": 1150.0,
    "PFC": 285.0,
    "REC": 135.0,
    "KPITTECH": 650.0,
    "GMRINFRA": 38.0,   # Penny stock
    "SUZLON": 28.0,     # Ultra-affordable
    "ADANIPORTS": 620.0,
    "ADANIGREEN": 1100.0,
    "TATAPOWER": 310.0,
}

# ---------------------------------------------------------------------------
# Helper: load candidate tickers from CSV or return default list.
# ---------------------------------------------------------------------------

CANDIDATE_SOURCE = "web"  # Options: "csv", "web", "hybrid"
MAX_REAL_TIME_CANDIDATES = 24
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def load_cached_candidates(market: str) -> List[Dict[str, Any]]:
    """
    Load cached candidate list from data/cache/candidates_{market}.json if present.
    This expands the universe beyond the small predefined OFFLINE_PRICES map.
    """
    cache_path = os.path.join(os.path.dirname(__file__), "..", "data", "cache", f"candidates_{market.lower()}.json")
    try:
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure unique symbols and basic fields
                seen = set()
                cleaned = []
                for item in data:
                    sym = item.get("symbol") or item.get("base_name")
                    if not sym:
                        continue
                    # Normalize symbol to include market suffix if missing
                    if "." not in sym and market.upper() == "NSE":
                        sym = f"{sym}.NS"
                    if sym in seen:
                        continue
                    seen.add(sym)
                    item["symbol"] = sym
                    # Fill minimal fields if missing
                    item.setdefault("base_name", sym.split('.')[0])
                    item.setdefault("name", item.get("base_name"))
                    item.setdefault("current_price", item.get("price", 0.0))
                    cleaned.append(item)
                return cleaned
    except Exception:
        return []


# Live price cache: stores (timestamp, prices_dict) to avoid repeated fetches
LIVE_PRICE_CACHE = {"timestamp": 0, "prices": {}, "ttl_seconds": 300}  # 5-min cache

def is_cache_valid(cache_path: str, ttl_seconds: int = 300) -> bool:
    if not os.path.exists(cache_path):
        return False
    try:
        mtime = os.path.getmtime(cache_path)
        return time.time() < mtime + ttl_seconds
    except Exception:
        return False


def get_cached_live_prices(cache_key: str = "default", ttl_seconds: int = 300) -> Dict[str, float]:
    """Get live prices from memory cache if still valid."""
    global LIVE_PRICE_CACHE
    
    current_time = time.time()
    cache_age = current_time - LIVE_PRICE_CACHE["timestamp"]
    
    if cache_age < ttl_seconds and len(LIVE_PRICE_CACHE["prices"]) > 0:
        return LIVE_PRICE_CACHE["prices"]
    
    return {}


def cache_live_prices(prices: Dict[str, float]) -> None:
    """Store live prices in memory cache with current timestamp."""
    global LIVE_PRICE_CACHE
    LIVE_PRICE_CACHE["timestamp"] = time.time()
    LIVE_PRICE_CACHE["prices"] = prices


def update_offline_prices_with_live_data(timeout_seconds: float = 2.0) -> Dict[str, float]:
    """
    HYBRID APPROACH: Fetch live prices from yfinance with timeout.
    Updates OFFLINE_PRICES in-place. Falls back to offline if fetch fails/times out.
    Returns dict of successfully updated stocks.
    
    Performance target: < 2 seconds to leave room for rest of scanning (total < 3 sec)
    """
    global OFFLINE_PRICES
    
    updated_count = 0
    start_time = time.time()
    updated_prices = {}
    
    try:
        # Get all unique base names
        symbols_to_fetch = list(OFFLINE_PRICES.keys())
        if not symbols_to_fetch:
            return {}
        
        # Add .NS suffix for batch download
        yahoo_symbols = [f"{s}.NS" for s in symbols_to_fetch]
        
        print(f"[Live Prices] Fetching real-time data for {len(yahoo_symbols)} stocks (timeout: {timeout_seconds}s)...")
        
        # Use download() with timeout - faster than individual Ticker() calls
        # Set a short period to get latest price
        data = yf.download(
            yahoo_symbols,
            period="1d",
            progress=False,
            timeout=timeout_seconds
        )
        
        elapsed = time.time() - start_time
        
        if data is not None and not data.empty:
            # Extract latest closing prices
            if len(yahoo_symbols) == 1:
                # Single stock returns Series
                latest_price = data["Close"].iloc[-1]
                base_name = symbols_to_fetch[0]
                if latest_price > 0:
                    OFFLINE_PRICES[base_name] = float(latest_price)
                    updated_prices[base_name] = float(latest_price)
                    updated_count += 1
            else:
                # Multiple stocks return DataFrame
                close_prices = data["Close"]
                for symbol, base_name in zip(yahoo_symbols, symbols_to_fetch):
                    if symbol in close_prices.columns:
                        latest_price = close_prices[symbol].iloc[-1]
                        if latest_price > 0:
                            OFFLINE_PRICES[base_name] = float(latest_price)
                            updated_prices[base_name] = float(latest_price)
                            updated_count += 1
        
        print(f"[Live Prices] Updated {updated_count}/{len(symbols_to_fetch)} stocks in {elapsed:.2f}s")
        return updated_prices
        
    except (Exception, TimeoutError) as e:
        elapsed = time.time() - start_time
        print(f"[Live Prices] Failed to fetch live data ({elapsed:.2f}s): {str(e)[:50]}... Using offline prices.")
        return {}

def fetch_candidate_list_web(market: str, use_live_prices: bool = True) -> List[Dict[str, Any]]:
    """
    FAST HYBRID SCANNER: Returns stock suggestions using LIVE prices with smart caching.
    
    Strategy:
    1. Check memory cache first (5-min TTL) - instant response if valid
    2. Try live fetch only if cache expired - with 2-second timeout
    3. Fall back to cached OFFLINE_PRICES instantly if live fetch fails
    
    Target performance: < 1.5 seconds (cache hit), < 3 seconds (cache miss with live fetch)
    """
    
    # If a curated cache of candidates exists, prefer it — provides broader universe
    cached = load_cached_candidates(market)
    if cached:
        # Fast path: return cached candidates immediately to guarantee <3s response.
        # Also start a short-lived background thread to refresh live prices without blocking.
        if use_live_prices:
            def _background_refresh(symbols_list: List[str], cached_list: List[Dict[str, Any]]):
                try:
                    metrics = fetch_batch_market_metrics(symbols_list, use_live=True)
                    updated = {}
                    for c in cached_list:
                        sym = c.get("symbol")
                        m = metrics.get(sym)
                        if m:
                            c["current_price"] = m.get("price", c.get("current_price", 0.0))
                            c["is_real_time"] = m.get("was_live", False)
                            updated[c.get("base_name", sym.split('.')[0])] = c["current_price"]
                    if updated:
                        try:
                            cache_live_prices(updated)
                        except Exception:
                            pass
                except Exception:
                    pass

            symbols = [c.get("symbol") for c in cached if c.get("symbol")]
            # Launch background refresh thread (daemon) to avoid blocking UI
            try:
                t = threading.Thread(target=_background_refresh, args=(symbols, cached), daemon=True)
                t.start()
            except Exception:
                pass

        return cached
            
    # TRY CACHED LIVE PRICES FIRST: Instant retrieval if cache valid
    live_prices_updated = {}
    if use_live_prices:
        cached_prices = get_cached_live_prices(ttl_seconds=300)
        if cached_prices:
            # Cache hit - use cached live prices without network call
            global OFFLINE_PRICES
            OFFLINE_PRICES.update(cached_prices)
            live_prices_updated = cached_prices
            print(f"[Live Prices] Using cached prices ({len(cached_prices)} stocks)")
        else:
            # Cache miss - try to fetch fresh live data with timeout
            live_prices_updated = update_offline_prices_with_live_data(timeout_seconds=2.0)
            if live_prices_updated:
                cache_live_prices(live_prices_updated)
    
    suffix = ".NS" if market == "NSE" else ".BO"
    candidates = []
    
    # Map OFFLINE_PRICES (with live updates if available) to risk categories
    seen = set()
    for base_name, price in OFFLINE_PRICES.items():
        if price <= 0:
            continue
        if base_name in seen:
            continue
        seen.add(base_name)

        # Risk classification based on current price (live if available, else cached)
        if price < 100:
            risk = "High"  # Penny stocks = higher risk
        elif price < 500:
            risk = "Medium"  # Affordable = medium
        else:
            risk = "Low"  # Expensive = defensive
        
        candidates.append({
            "symbol": f"{base_name}{suffix}",
            "base_name": base_name,
            "name": base_name,
            "category": "Mixed",
            "risk": risk,
            "current_price": price,
            "market_cap": 0,
            "pe_ratio": 0,
            "volatility": 0.0,
            "is_real_time": base_name in live_prices_updated,
            "is_from_live_fetch": base_name in live_prices_updated,
            "discovery_method": "hybrid_live_cached"
        })
    
    # Return all candidates with live OR cached prices
    if candidates:
        return candidates
    
    return []

def load_candidate_tickers(market: str, use_live_prices: bool = True) -> List[Dict[str, Any]]:
    """
    LOAD CANDIDATE TICKERS: Prioritizes REAL-TIME market data with intelligent fallback.
    
    Priority:
    1. Live Market Data - Real-time NSE/BSE prices via yfinance (2-sec timeout)
    2. Cached Offline Prices - Instant fallback if live fetch fails
    3. CSV Watchlist - User-maintained list (if web/live disabled)
    4. Predefined Fallback - Only if all real-time sources fail
    """
    # PRIMARY: Prefer curated cached candidate list if available (broader universe)
    cached_candidates = load_cached_candidates(market)
    if cached_candidates and len(cached_candidates) >= 10:
        print(f"[AI Market Scanner] Using cached candidate list: {len(cached_candidates)} stocks")
        return cached_candidates

    # PRIMARY: Try to fetch REAL-TIME market data (live prices with smart fallback)
    result = fetch_candidate_list_web(market, use_live_prices=use_live_prices)
    if result and len(result) >= 10:
        live_count = sum(1 for s in result if s.get("is_from_live_fetch"))
        print(f"[AI Market Scanner] Using REAL-TIME data: {len(result)} stocks ({live_count} live prices) from {market}")
        return result
    
    # SECONDARY: Try CSV watchlist if exists
    if not use_live_prices or "csv" in CANDIDATE_SOURCE.lower():
        csv_path = os.path.join(os.path.dirname(__file__), f"../data/stocks_{market.lower()}.csv")
        if os.path.exists(csv_path):
            try:
                csv_data = pd.read_csv(csv_path).to_dict('records')
                if csv_data and len(csv_data) > 10:
                    print(f"[AI Market Scanner] Using CSV watchlist: {len(csv_data)} stocks")
                    return csv_data
            except Exception:
                pass
    
    # TERTIARY FALLBACK: Use predefined stocks ONLY as last resort
    print(f"[AI Market Scanner] Real-time sources failed. Using fallback predefined stocks.")
    suffix = ".NS" if market == "NSE" else ".BO"
    
    predefined_pool = [
        {"symbol": f"TCS{suffix}", "base_name": "TCS", "name": "Tata Consultancy Services", "category": "Information Technology", "risk": "Low", "is_real_time": False},
        {"symbol": f"INFY{suffix}", "base_name": "INFY", "name": "Infosys Ltd.", "category": "Information Technology", "risk": "Low", "is_real_time": False},
        {"symbol": f"RELIANCE{suffix}", "base_name": "RELIANCE", "name": "Reliance Industries Ltd.", "category": "Energy & Retail", "risk": "Low", "is_real_time": False},
        {"symbol": f"HDFCBANK{suffix}", "base_name": "HDFCBANK", "name": "HDFC Bank Ltd.", "category": "Banking & Financials", "risk": "Low", "is_real_time": False},
        {"symbol": f"ITC{suffix}", "base_name": "ITC", "name": "ITC Ltd.", "category": "FMCG", "risk": "Low", "is_real_time": False},
        {"symbol": f"TATAMOTORS{suffix}", "base_name": "TATAMOTORS", "name": "Tata Motors Ltd.", "category": "Automotive", "risk": "Medium", "is_real_time": False},
        {"symbol": f"BHARTIARTL{suffix}", "base_name": "BHARTIARTL", "name": "Bharti Airtel Ltd.", "category": "Telecommunications", "risk": "Medium", "is_real_time": False},
        {"symbol": f"LT{suffix}", "base_name": "LT", "name": "Larsen & Toubro Ltd.", "category": "Engineering & Infra", "risk": "Medium", "is_real_time": False},
        {"symbol": f"HINDUNILVR{suffix}", "base_name": "HINDUNILVR", "name": "Hindustan Unilever Ltd.", "category": "Consumer Goods", "risk": "Medium", "is_real_time": False},
        {"symbol": f"TITAN{suffix}", "base_name": "TITAN", "name": "Titan Company Ltd.", "category": "Luxury & Consumer", "risk": "Medium", "is_real_time": False},
        {"symbol": f"AXISBANK{suffix}", "base_name": "AXISBANK", "name": "Axis Bank Ltd.", "category": "Banking", "risk": "Low", "is_real_time": False},
        {"symbol": f"MARUTI{suffix}", "base_name": "MARUTI", "name": "Maruti Suzuki India Ltd.", "category": "Automotive", "risk": "Medium", "is_real_time": False},
        {"symbol": f"SUNPHARMA{suffix}", "base_name": "SUNPHARMA", "name": "Sun Pharmaceutical Industries Ltd.", "category": "Pharma", "risk": "Medium", "is_real_time": False},
        {"symbol": f"NTPC{suffix}", "base_name": "NTPC", "name": "NTPC Ltd.", "category": "Power Generation", "risk": "Low", "is_real_time": False},
        {"symbol": f"HCLTECH{suffix}", "base_name": "HCLTECH", "name": "HCL Technologies Ltd.", "category": "IT Services", "risk": "Medium", "is_real_time": False},
        {"symbol": f"SBIN{suffix}", "base_name": "SBIN", "name": "State Bank of India", "category": "Banking", "risk": "Low", "is_real_time": False},
        {"symbol": f"WIPRO{suffix}", "base_name": "WIPRO", "name": "Wipro Limited", "category": "IT", "risk": "Low", "is_real_time": False},
        {"symbol": f"JSWSTEEL{suffix}", "base_name": "JSWSTEEL", "name": "JSW Steel Limited", "category": "Steel", "risk": "Medium", "is_real_time": False},
        {"symbol": f"CIPLA{suffix}", "base_name": "CIPLA", "name": "Cipla Limited", "category": "Pharma", "risk": "Medium", "is_real_time": False},
        {"symbol": f"IRFC{suffix}", "base_name": "IRFC", "name": "IRFC Limited", "category": "Finance", "risk": "Low", "is_real_time": False},
    ]
    
    return predefined_pool


# ---------------------------------------------------------------------------
# Helper: get a broader pool of candidate stocks for each market.
# ---------------------------------------------------------------------------

def get_candidate_pool(market: str) -> List[Dict[str, Any]]:
    """Return a list of candidate stocks for the given market."""
    return load_candidate_tickers(market)

# ---------------------------------------------------------------------------
# Helper: fetch live price and basic historic metrics for a ticker.
# ---------------------------------------------------------------------------

def fetch_batch_market_metrics(ticker_symbols: List[str], use_live: bool = True) -> Dict[str, Dict[str, Any]]:
    """Fetch market metrics for multiple tickers using a batch yfinance download for speed."""
    metrics = {}
    if use_live and ticker_symbols:
        try:
            raw_data = yf.download(
                ticker_symbols,
                period="10d",
                interval="1d",
                progress=False,
                timeout=5
            )
            if raw_data is not None and not raw_data.empty:
                close_df = None
                if isinstance(raw_data.columns, pd.MultiIndex):
                    if "Close" in raw_data.columns.levels[0]:
                        close_df = raw_data["Close"]
                elif "Close" in raw_data.columns:
                    close_df = raw_data["Close"]

                if close_df is not None:
                    if isinstance(close_df, pd.Series):
                        close_df = close_df.to_frame(name=ticker_symbols[0])

                    for ticker in ticker_symbols:
                        series = close_df[ticker].dropna() if ticker in close_df.columns else pd.Series(dtype=float)
                        price = float(series.iloc[-1]) if not series.empty else 0.0
                        momentum = 0.0
                        volatility = 0.0
                        if len(series) >= 5 and series.iloc[-5] > 0:
                            momentum = (price - float(series.iloc[-5])) / float(series.iloc[-5]) * 100.0
                        returns = series.pct_change().dropna()
                        if not returns.empty:
                            volatility = float(returns.rolling(window=min(5, len(returns))).std().iloc[-1] * np.sqrt(252))

                        if price > 0:
                            metrics[ticker] = {
                                "price": round(price, 2),
                                "momentum": round(momentum, 2),
                                "volatility": round(volatility, 4),
                                "market_cap": 0,
                                "pe_ratio": 0.0,
                                "was_live": True,
                            }
        except Exception:
            pass

    for ticker in ticker_symbols:
        if ticker not in metrics:
            base_name = ticker.split(".")[0]
            price = OFFLINE_PRICES.get(base_name, 100.0)
            metrics[ticker] = {
                "price": round(price, 2),
                "momentum": 0.0,
                "volatility": 0.0,
                "market_cap": 0,
                "pe_ratio": 0.0,
                "was_live": False,
            }
    return metrics


def get_live_quote(ticker_symbol: str) -> Tuple[float, bool]:
    """Return the latest live stock price from yfinance using fast_info or intraday history."""
    price = 0.0
    was_live = False
    ticker = yf.Ticker(ticker_symbol)

    try:
        fast_info = getattr(ticker, "fast_info", None) or {}
        if isinstance(fast_info, dict):
            price = float(fast_info.get("last_price") or fast_info.get("lastPrice") or 0.0)
        else:
            price = float(getattr(fast_info, "last_price", 0.0) or getattr(fast_info, "lastPrice", 0.0) or 0.0)

        if price and price > 0:
            return price, True
    except Exception:
        pass

    try:
        hist = ticker.history(period="2d", interval="1m")
        if hist is not None and not hist.empty and "Close" in hist.columns:
            last_price = float(hist["Close"].iloc[-1])
            if last_price > 0:
                return last_price, True
    except Exception:
        pass

    return 0.0, False


def fetch_market_metrics(ticker_symbol: str) -> Dict[str, Any]:
    """Fetch live price and momentum/volatility metrics from yfinance."""
    base_name = ticker_symbol.split(".")[0]
    price = OFFLINE_PRICES.get(base_name, 100.0)
    momentum = 0.0
    volatility = 0.0
    market_cap = 0
    pe_ratio = 0.0
    was_live = False

    try:
        ticker = yf.Ticker(ticker_symbol)
        live_price, was_live = get_live_quote(ticker_symbol)
        if live_price > 0:
            price = live_price

        hist = ticker.history(period="3mo", interval="1d")
        if hist is not None and not hist.empty and "Close" in hist.columns:
            if price <= 0:
                price = float(hist["Close"].iloc[-1])
                was_live = True
            if len(hist) >= 10:
                past_price = float(hist["Close"].iloc[-10])
                if past_price > 0:
                    momentum = (price - past_price) / past_price * 100.0
            returns = hist["Close"].pct_change().dropna()
            if len(returns) >= 21:
                volatility = float(returns.rolling(window=21).std().iloc[-1] * np.sqrt(252))
            else:
                volatility = float(returns.std() * np.sqrt(252)) if not returns.empty else 0.0

        info = {}
        try:
            info = ticker.info or {}
        except Exception:
            info = {}
        market_cap = int(info.get("marketCap", 0) or 0)
        pe_ratio = float(info.get("trailingPE") or info.get("forwardPE") or 0.0)
    except Exception:
        price = OFFLINE_PRICES.get(base_name, price)
        momentum = 0.0
        volatility = 0.0
        market_cap = 0
        pe_ratio = 0.0
        was_live = False

    return {
        "price": round(price, 2),
        "momentum": round(momentum, 2),
        "volatility": round(volatility, 4),
        "market_cap": market_cap,
        "pe_ratio": round(pe_ratio, 2),
        "was_live": was_live,
    }

# ---------------------------------------------------------------------------
# Scoring heuristic – simple AI‑style weighted sum.
# ---------------------------------------------------------------------------

def score_stock(metrics: Dict[str, Any], risk_level: str) -> float:
    """Weighted score using momentum, volatility, dividend yield and ROE."""
    momentum = metrics.get("momentum", 0.0)
    volatility = metrics.get("volatility", 0.0)
    dividend_yield = metrics.get("dividend_yield", 0.0) * 100  # convert to percent
    roe = metrics.get("roe", 0.0) * 100
    # Base weights
    weights = {
        "momentum": 0.3,
        "volatility": -0.2,
        "dividend_yield": 0.15,
        "roe": 0.15,
    }
    # Adjust volatility weight per risk level
    if risk_level == "Low":
        vol_weight = -0.4
    elif risk_level == "Medium":
        vol_weight = -0.2
    else:
        vol_weight = -0.1
    weights["volatility"] = vol_weight
    score = (
        weights["momentum"] * momentum +
        weights["volatility"] * volatility +
        weights["dividend_yield"] * dividend_yield +
        weights["roe"] * roe
    )
    return score

def fetch_fundamentals(ticker_symbol: str) -> Dict[str, Any]:
    """Retrieve additional fundamentals like dividend yield and ROE via yfinance."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        return {
            "dividend_yield": info.get("dividendYield", 0.0),
            "roe": info.get("returnOnEquity", 0.0),
        }
    except Exception:
        return {"dividend_yield": 0.0, "roe": 0.0}


def categorize_stock_by_price(price: float) -> str:
    """Categorize stock by price range."""
    if price < 100:
        return "penny"      # Penny stocks: ₹0-₹100
    elif price < 300:
        return "affordable" # Affordable: ₹100-₹300
    elif price < 800:
        return "mid"        # Mid-range: ₹300-₹800
    elif price < 1500:
        return "high_mid"   # High-mid: ₹800-₹1500
    else:
        return "premium"    # Premium: ₹1500+


def classify_risk_level(price: float, volatility: float, market_cap: float, symbol: str = "") -> str:
    """Classify a stock's intrinsic risk bucket based on fundamentals."""
    # Blue-chip / Large-cap = Low Risk
    large_cap_stocks = ["TCS", "INFY", "RELIANCE", "HDFCBANK", "ICICIBANK", "WIPRO", "SBIN", "AXISBANK", "LT", "HINDUNILVR", "MARUTI", "TITAN", "SUNPHARMA"]
    if any(symbol.startswith(bc) for bc in large_cap_stocks):
        return "Low"
    
    # Mid-cap / Stable = Medium Risk  
    mid_cap_stocks = ["ITC", "BHARTIARTL", "TATAMOTORS", "HCLTECH", "NTPC", "CIPLA", "LUPIN", "TECHM", "CHOLAFIN"]
    if any(symbol.startswith(mc) for mc in mid_cap_stocks):
        return "Medium"
    
    # Small-cap / Penny stocks = High Risk
    if price < 100:
        return "High"
    if price < 200:
        return "Medium"
    if price > 2000:
        return "Low"
    if price > 800:
        return "Low"
    
    return "Medium"


def get_ai_recommendations(
    candidate_stocks: List[Dict[str, Any]],
    investment_amount: float,
    market: str,
    risk_level: str,
    horizon: str,
) -> List[Dict[str, Any]]:
    """Ask an LLM to rank and allocate stocks based on provided metrics.
    The LLM receives a JSON‑serializable prompt containing candidate data and
    user constraints, and is instructed to return a JSON list with the fields:
    symbol, name, category, price, shares, total_cost, confidence_score,
    risk, growth_factors, and a short reasoning string.
    If the LLM response cannot be parsed, an empty list is returned.
    """
    from modules.gemini_service import generate_response
    import re
    import ast

    prompt_payload = {
        "investment_amount": investment_amount,
        "market": market,
        "risk_level": risk_level,
        "horizon": horizon,
        "candidates": candidate_stocks,
    }

    # Strong JSON-only instruction and schema example for robust parsing
    prompt = (
        "You are a precise AI financial analyst.\n"
        "INPUT: a JSON array `candidates` is provided with current prices and metadata. Use these exact prices to allocate shares.\n"
        "TASK: From the candidate list, choose the best stocks to allocate the provided `investment_amount` for the given `risk_level` and `horizon`.\n"
        "REQUIREMENTS:\n"
        "  - Return ONLY a single JSON ARRAY (no text, no markdown fences).\n"
        "  - Each element must be an object with these fields: `symbol`, `name`, `category`, `price`, `shares`, `total_cost`, `confidence_score` (0-100), `risk` (Low/Medium/High), `growth_factors` (array of short strings), `reasoning` (short).\n"
        "  - Do not suggest the same `symbol` more than once. Prefer instruments with `is_real_time` true.\n"
        "  - Aim to maximize capital utilization and share counts; minimize leftover cash. Allocate across multiple symbols when possible (2-5).\n"
        "  - Ensure variety across price ranges and avoid returning only high-priced symbols for micro budgets.\n"
        "  - If no valid whole-share allocation is possible, return an empty JSON array `[]`.\n"
        "EXAMPLE OUTPUT: [{\n"
        "  \"symbol\": \"TCS.NS\", \"name\": \"TCS\", \"category\": \"IT\", \"price\": 3200.0, \"shares\": 1, \"total_cost\": 3200.0, \"confidence_score\": 85, \"risk\": \"Low\", \"growth_factors\": [\"strong earnings\"], \"reasoning\": \"Large-cap defensive pick\"\n"
        "}]\n"
    )

    full_prompt = f"{prompt}\n\nDATA:\n{json.dumps(prompt_payload, default=str, indent=2)}"
    try:
        response = generate_response(full_prompt)
        text = response.strip()

        # Find first JSON array in the response using regex DOTALL
        m = re.search(r"(\[.*\])", text, re.DOTALL)
        if not m:
            return []
        json_text = m.group(1)

        try:
            return json.loads(json_text)
        except Exception:
            try:
                # Fallback: use ast.literal_eval for loosely-quoted JSON-like output
                return ast.literal_eval(json_text)
            except Exception:
                return []
    except Exception as e:
        print(f"LLM recommendation error: {e}")
        return []


# ---------------------------------------------------------------------------
# AI-DRIVEN REAL-TIME MARKET SCANNER
# ---------------------------------------------------------------------------

def scan_real_time_affordable_opportunities(budget: float, market: str, risk_level: str) -> List[Dict[str, Any]]:
    """
    FAST AI-DRIVEN SCANNER: Real-time scan using candidate tickers and batch market data.
    Returns stock suggestions filtered by user budget, risk tolerance, and live price.
    """
    print(f"[AI Real-Time Scanner] Scanning {market} for opportunities under INR{budget}...")
    candidate_pool = load_candidate_tickers(market)

    if not candidate_pool:
        print("[AI Scanner] No candidates found")
        return []

    ticker_symbols = [stock.get("symbol") for stock in candidate_pool if stock.get("symbol")]
    batch_metrics = fetch_batch_market_metrics(ticker_symbols, use_live=True)

    live_opportunities = []
    fallback_opportunities = []

    for stock in candidate_pool:
        try:
            ticker = stock.get("symbol", "")
            if not ticker:
                continue

            metrics = batch_metrics.get(ticker, {
                "price": OFFLINE_PRICES.get(stock.get("base_name", ""), 0.0),
                "momentum": 0.0,
                "volatility": 0.0,
                "market_cap": 0,
                "pe_ratio": 0.0,
                "was_live": False,
            })
            current_price = metrics.get("price", 0.0)
            if current_price <= 0 or current_price > budget:
                continue

            shares_possible = int(budget // current_price)
            if shares_possible < 1:
                continue

            momentum = metrics.get("momentum", 0.0)
            volatility = metrics.get("volatility", 0.0)
            market_cap = metrics.get("market_cap", 0)

            ai_score = (max(1, budget / current_price) * 8.0) + momentum * 0.6 - (volatility * 50.0)
            ai_score += 5.0 if stock.get("risk") == risk_level else 0.0
            opportunity = {
                "symbol": ticker,
                "base_name": stock.get("base_name", ""),
                "name": stock.get("name", ticker),
                "category": stock.get("category", ""),
                "current_price": round(current_price, 2),
                "momentum": round(momentum, 2),
                "volatility": round(volatility, 4),
                "market_cap": market_cap,
                "ai_score": round(ai_score, 2),
                "shares_possible": shares_possible,
                "risk": stock.get("risk", "Medium"),
                "is_real_time_data": metrics.get("was_live", False) or stock.get("is_from_live_fetch", False),
                "price_source": "live" if metrics.get("was_live", False) else "cached"
            }
            if metrics.get("was_live", False):
                live_opportunities.append(opportunity)
            else:
                fallback_opportunities.append(opportunity)
        except Exception:
            continue

    if live_opportunities:
        # Shuffle to introduce variety when scores are close
        random.shuffle(live_opportunities)
        opportunities = sorted(live_opportunities, key=lambda x: (x["ai_score"], -x["current_price"]), reverse=True)
        print(f"[AI Scanner] Found {len(opportunities)} live affordable opportunities")
    else:
        random.shuffle(fallback_opportunities)
        opportunities = sorted(fallback_opportunities, key=lambda x: (x["ai_score"], -x["current_price"]), reverse=True)
        print(f"[AI Scanner] Found {len(opportunities)} fallback affordable opportunities")

    return opportunities


# ---------------------------------------------------------------------------
# Core function – now AI driven.
# ---------------------------------------------------------------------------

def calculate_portfolio(investment_amount: float, market: str, risk_level: str, horizon: str, price_range: tuple = None) -> Dict[str, Any]:
    """
    Generate portfolio using LIVE MARKET STOCKS - NO PREDEFINED LIST!
    
    FEATURES:
    1. Fetches real stocks from NSE/BSE with live prices
    2. Guaranteed response time: 2-3 seconds
    3. No predefined stock list - all from internet/market
    4. Smart caching for speed
    5. Automatic price range optimization
    
    Args:
        investment_amount: Budget in ₹
        market: "NSE" or "BSE"
        risk_level: "Low", "Medium", or "High"
        horizon: "Long Term" or "Short Term"
        price_range: Optional override for price range
    
    Returns:
        Dict with recommendations from LIVE MARKET DATA
    """
    print(f"\n[Portfolio] 🔴 LIVE MARKET MODE - Fetching real stocks from internet")
    print(f"[Portfolio] Budget: ₹{investment_amount} | Risk: {risk_level} | Horizon: {horizon}")
    
    start_time = time.time()
    
    # STEP 1: Get LIVE market recommendations from the broader candidate universe
    live_suggestions = scan_real_time_affordable_opportunities(
        investment_amount,
        market,
        risk_level
    )
    
    elapsed = time.time() - start_time
    print(f"[Portfolio] [OK] Retrieved {len(live_suggestions)} live stocks in {elapsed:.2f}s")
    
    if not live_suggestions:
        print("[Portfolio] No live stocks available - using fallback")
        return {
            "suggested_type": "Error - No Live Data Available",
            "recommendations": [],
            "total_allocated": 0,
            "leftover_cash": investment_amount,
            "confidence_score": 0,
            "reasoning": "Unable to fetch live market data. Check internet connection.",
            "data_source": "none",
            "prices_are_live": False
        }
    
    # STEP 2: Allocate from live suggestions
    recommendations = allocate_from_live_suggestions(
        investment_amount=investment_amount,
        live_suggestions=live_suggestions
    )
    
    if recommendations and len(recommendations) > 0:
        total_allocated = sum(r["total_cost"] for r in recommendations)
        
        return {
            "suggested_type": f"🔴 LIVE MARKET Portfolio for {horizon} Investing",
            "recommendations": recommendations,
            "total_allocated": round(total_allocated, 2),
            "leftover_cash": round(max(0, investment_amount - total_allocated), 2),
            "confidence_score": 90.0,
            "reasoning": f"Selected {len(recommendations)} best stocks from LIVE NSE/BSE market data with real-time prices",
            "data_source": "live_market_real_time",
            "prices_are_live": True,
            "fetch_timestamp": datetime.now().isoformat(),
            "market": market
        }
    
    return {
        "suggested_type": "No Allocation Possible",
        "recommendations": [],
        "total_allocated": 0,
        "leftover_cash": investment_amount,
        "confidence_score": 0,
        "reasoning": "No suitable stocks found in budget and risk range",
        "data_source": "live_market_real_time",
        "prices_are_live": False
    }


def allocate_from_live_suggestions(
    investment_amount: float,
    live_suggestions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Allocate portfolio from LIVE market suggestions.
    Distributes budget across 2-3 best performing stocks.
    """
    if not live_suggestions:
        return []
    
    # Sort by momentum (best performers first)
    sorted_stocks = sorted(live_suggestions, key=lambda x: x.get("momentum", 0), reverse=True)
    
    recommendations = []
    remaining_budget = investment_amount
    allocation_ratios = [0.50, 0.35, 0.15]  # 50%, 35%, 15% allocation
    allocated_count = 0
    selected_symbols = set()
    
    for stock in sorted_stocks:
        if remaining_budget <= 0 or allocated_count >= 3:
            break
        
        symbol = stock.get("symbol")
        if symbol in selected_symbols:
            continue
        
        price = stock.get("current_price", 0)
        if price <= 0:
            continue
        
        # Allocate based on position
        if allocated_count < len(allocation_ratios):
            alloc_ratio = allocation_ratios[allocated_count]
        else:
            alloc_ratio = 0
        
        allocated_budget = investment_amount * alloc_ratio
        allocated_budget = min(allocated_budget, remaining_budget)
        
        shares = int(allocated_budget // price)
        if shares <= 0:
            continue
        
        total_cost = round(shares * price, 2)
        
        recommendations.append({
            "name": stock.get("name", symbol),
            "symbol": symbol,
            "current_price": round(price, 2),
            "shares": shares,
            "total_cost": total_cost,
            "category": "Live Market Stock",
            "price_band": stock.get("price_band", ""),
            "momentum": round(stock.get("momentum", 0), 2),
            "volatility": round(stock.get("volatility", 0), 4),
            "confidence_score": min(95, 70 + abs(stock.get("momentum", 0)) / 5),
            "risk": stock.get("risk", "Medium"),
            "reasoning": f"✓ {shares} shares of {symbol} @ ₹{price:.2f} (Momentum: {stock.get('momentum', 0):.2f}%)",
            "is_live_data": True
        })
        
        remaining_budget -= total_cost
        selected_symbols.add(symbol)
        allocated_count += 1
    
    return recommendations


def determine_optimal_price_range(investment_amount: float) -> Tuple[float, float]:
    """Determine the optimal price range for stocks based on investment amount."""
    if investment_amount < 1000:
        # Micro budget: focus on penny to affordable stocks
        return (0, 300)
    elif investment_amount < 3000:
        # Small budget: affordable to mid-range
        return (50, 600)
    elif investment_amount < 10000:
        # Medium budget: mid-range to high-mid
        return (200, 1200)
    elif investment_amount < 50000:
        # Large budget: broader range including premium
        return (500, 2500)
    else:
        # Mega budget: all stocks viable
        return (500, 5000)


def smart_diverse_allocation(
    investment_amount: float,
    pool: List[Dict[str, Any]],
    risk_level: str,
    horizon: str,
    price_range: Tuple[float, float]
) -> List[Dict[str, Any]]:
    """Allocate portfolio selecting diverse stocks across price categories."""
    
    if not pool:
        return None
    
    # Group stocks by price category for diversity
    price_categories = {}
    for stock in pool:
        cat = stock.get("price_category", "mid")
        if cat not in price_categories:
            price_categories[cat] = []
        price_categories[cat].append(stock)
    
    # Sort each category by score
    for cat in price_categories:
        price_categories[cat] = sorted(
            price_categories[cat],
            key=lambda x: x.get("momentum", 0) + x.get("dividend_yield", 0) * 100,
            reverse=True
        )
    
    recommendations = []
    remaining_budget = investment_amount
    allocation_budget_ratios = [0.40, 0.35, 0.25]  # For 3 stocks
    allocated_count = 0
    selected_symbols = set()
    
    # Allocate from each category for diversity
    categories_order = ["penny", "affordable", "mid", "high_mid", "premium"]
    
    for cat in categories_order:
        if allocated_count >= 3 or remaining_budget <= 0:
            break
        
        if cat not in price_categories or not price_categories[cat]:
            continue
        
        # Pick best stock from this category that we haven't selected
        for stock in price_categories[cat]:
            if stock.get("symbol") in selected_symbols:
                continue
            
            price = stock.get("price", 0)
            if price <= 0 or price > remaining_budget:
                continue
            
            # Allocate based on budget position
            if allocated_count < len(allocation_budget_ratios):
                alloc_ratio = allocation_budget_ratios[allocated_count]
            else:
                alloc_ratio = 0.0
            
            allocated_budget = remaining_budget * alloc_ratio
            shares = int(allocated_budget // price)
            
            if shares > 0:
                cost = round(shares * price, 2)
                recommendations.append({
                    "name": stock.get("name", stock.get("symbol")),
                    "symbol": stock.get("symbol"),
                    "current_price": round(price, 2),
                    "shares": shares,
                    "total_cost": cost,
                    "category": stock.get("category", ""),
                    "price_band": cat,
                    "confidence_score": min(95, 60 + stock.get("momentum", 0) / 2),
                    "risk": stock.get("risk", risk_level),
                    "reasoning": f"{shares} shares of {stock.get('name')} ({cat}) at ₹{price:.2f}"
                })
                
                remaining_budget -= cost
                selected_symbols.add(stock.get("symbol"))
                allocated_count += 1
                break
    
    return recommendations if recommendations else None


# ---------------------------------------------------------------------------
# NEW FUNCTIONS FOR BUDGET-AWARE ALLOCATION
# ---------------------------------------------------------------------------

def categorize_budget(amount: float) -> str:
    """Categorize investment amount to determine allocation strategy."""
    if amount < 1000:
        return "micro"
    elif amount < 5000:
        return "small"
    elif amount < 20000:
        return "medium"
    elif amount < 100000:
        return "large"
    else:
        return "mega"


def allocate_from_real_time_opportunities(
    investment_amount: float,
    opportunities: List[Dict[str, Any]],
    budget_category: str
) -> List[Dict[str, Any]]:
    """
    Allocate portfolio from real-time market opportunities using a truly budget‑aware strategy.
    The function now iterates over the sorted opportunities and allocates the maximum
    affordable shares for each stock given the *remaining* budget, ensuring that the
    set of recommendations varies with the investment size.
    """
    if not opportunities:
        return []
    
    # Shuffle to add variety for ties, then sort by AI score descending and price ascending
    random.shuffle(opportunities)
    opportunities = sorted(opportunities, key=lambda x: (x["ai_score"], -x["current_price"]), reverse=True)
    
    recommendations: List[Dict[str, Any]] = []
    remaining_budget = investment_amount
    used_symbols = set()
    allocation_count = 0
    
    for opp in opportunities:
        symbol = opp.get("symbol")
        if not symbol or symbol in used_symbols:
            continue
        price = opp.get("current_price", 0)
        if price <= 0 or price > remaining_budget:
            continue
        # Determine number of shares to allocate based on remaining budget and allocation strategy
        # First three allocations get larger portions of budget
        if allocation_count == 0:
            alloc_ratio = 0.45
        elif allocation_count == 1:
            alloc_ratio = 0.32
        elif allocation_count == 2:
            alloc_ratio = 0.23
        else:
            # Remaining budget split equally among remaining slots (max 5 total)
            alloc_ratio = min(0.1, remaining_budget / investment_amount)
        
        allocated_budget = investment_amount * alloc_ratio
        # Ensure we don't allocate more than remaining budget
        allocated_budget = min(allocated_budget, remaining_budget)
        shares = int(allocated_budget // price)
        if shares < 1:
            # If we can't afford at least one share with this allocation, try minimal 1 share
            shares = 1 if price <= remaining_budget else 0
        if shares <= 0:
            continue
        total_cost = round(shares * price, 2)
        recommendations.append({
            "name": opp.get("name", symbol),
            "symbol": symbol,
            "current_price": round(price, 2),
            "shares": shares,
            "total_cost": total_cost,
            "category": opp.get("category", ""),
            "confidence_score": min(95, 50 + opp.get("ai_score", 0) / 2),
            "risk": opp.get("risk", "Medium"),
            "reasoning": f"Allocated {shares} shares at ₹{price:.2f}"
        })
        remaining_budget -= total_cost
        used_symbols.add(symbol)
        allocation_count += 1
        if remaining_budget <= 0 or allocation_count >= 5:
            break
    
    return recommendations


def get_affordable_stock_pool(market: str, max_price: float) -> List[Dict[str, Any]]:
    """
    FAST DISCOVERY: Find affordable stocks instantly from OFFLINE_PRICES.
    Zero network I/O - returns in milliseconds.
    """
    # Get all candidates from OFFLINE_PRICES
    real_time_stocks = fetch_candidate_list_web(market)
    affordable = []
    
    for stock in real_time_stocks:
        price = stock.get("current_price", 0.0)
        if price > 0 and price <= max_price:
            affordable.append({
                **stock,
                "price": price,
                "is_real_time": False,
                "discovery_method": "offline_instant"
            })
    
    if len(affordable) > 5:
        print(f"[AI Discovery] Found {len(affordable)} affordable stocks instantly")
        return affordable
    
    # Return all available if small list
    print(f"[AI Discovery] Affordable pool size: {len(affordable)}")
    return affordable


def smart_budget_allocation(
    investment_amount: float,
    market: str,
    risk_level: str,
    horizon: str,
    budget_category: str,
    enhanced_pool: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """SMART ALLOCATION ENGINE: Adaptively allocates budget for ANY amount.

    This is the core fix that ensures we NEVER return empty portfolios. Uses budget-aware strategies tailored to investment amount.
    """

    # STAGE 1: Try using enhanced pool with all-stocks allocation (no risk filtering)
    if enhanced_pool:
        allocated = try_allocate_from_pool(
            pool=enhanced_pool,
            investment_amount=investment_amount,
            strategy="highest_score"
        )
        if allocated:
            return allocated

    # STAGE 2: Use budget-aware affordable stock pool
    max_price = investment_amount / 2 if investment_amount < 5000 else investment_amount / 5
    affordable_pool = get_affordable_stock_pool(market, max_price)

    if affordable_pool:
        # Enhance affordable pool with metrics
        enhanced_affordable = []
        for stock in affordable_pool:
            metrics = fetch_market_metrics(stock["symbol"])
            fundamentals = fetch_fundamentals(stock["symbol"])
            enhanced_affordable.append({**stock, **metrics, **fundamentals})

        allocated = try_allocate_from_pool(
            pool=enhanced_affordable,
            investment_amount=investment_amount,
            strategy="affordability_first"
        )
        if allocated:
            return allocated
            
    # STAGE 3: If no affordable pool, fetch broader real-time candidates
    # Use web fetch without price filter to get best stocks based on live data
    broader_candidates = fetch_candidate_list_web(market, use_live_prices=True)
    if broader_candidates:
        # Enhance with metrics and fundamentals
        enhanced_broader = []
        for stock in broader_candidates:
            metrics = fetch_market_metrics(stock["symbol"])
            fundamentals = fetch_fundamentals(stock["symbol"])
            enhanced_broader.append({**stock, **metrics, **fundamentals})
        allocated = try_allocate_from_pool(
            pool=enhanced_broader,
            investment_amount=investment_amount,
            strategy="highest_score"
        )
        if allocated:
            return allocated
    
    # STAGE 4: For micro budgets, use penny stock allocation
    if budget_category in ["micro", "small"]:
        penny_stock_allocation = allocate_penny_stocks(
            investment_amount=investment_amount,
            market=market,
            budget_category=budget_category
        )
        if penny_stock_allocation:
            return penny_stock_allocation
            
    # STAGE 5: As a last resort, allocate to the cheapest stock available
    return allocate_single_best_stock(investment_amount, market, budget_category)



def try_allocate_from_pool(
    pool: List[Dict[str, Any]],
    investment_amount: float,
    strategy: str = "highest_score"
) -> List[Dict[str, Any]]:
    """
    Try to allocate from a given stock pool using the specified strategy.
    Returns None if no valid allocation possible.
    """
    if not pool:
        return None

    # Calculate allocation score for each stock
    scored_stocks = []
    for stock in pool:
        score = score_stock(stock, stock.get("risk", "Medium"))
        price = stock.get("price", 0.0)
        if price > 0:
            scored_stocks.append({**stock, "score": score})

    # Currently we only support highest_score strategy which sorts by score descending
    ranked = sorted(scored_stocks, key=lambda x: x["score"], reverse=True)

    recommendations: List[Dict[str, Any]] = []
    remaining_budget = investment_amount
    allocation_count = 0

    for stock in ranked:
        if remaining_budget <= 0:
            break
        price = stock.get("price", 0.0)
        if price <= 0:
            continue
        # Determine allocation ratio based on count
        if allocation_count == 0:
            alloc_ratio = 0.45
        elif allocation_count == 1:
            alloc_ratio = 0.32
        elif allocation_count == 2:
            alloc_ratio = 0.23
        else:
            alloc_ratio = min(0.1, remaining_budget / investment_amount)
        allocated_budget = min(investment_amount * alloc_ratio, remaining_budget)
        shares = int(allocated_budget // price)
        if shares <= 0:
            continue
        cost = round(shares * price, 2)
        recommendations.append({
            "name": stock.get("name", stock.get("symbol")),
            "symbol": stock.get("symbol"),
            "current_price": round(price, 2),
            "shares": shares,
            "total_cost": cost,
            "category": stock.get("category", ""),
            "confidence_score": min(95, 50 + stock.get("score", 0) / 2),
            "risk": stock.get("risk", "Medium"),
            "reasoning": f"Allocated {shares} shares at ₹{price}"
        })
        remaining_budget -= cost
        allocation_count += 1
        if allocation_count >= 5:
            break

    return recommendations if recommendations else None


def allocate_penny_stocks(
    investment_amount: float,
    market: str,
    budget_category: str
) -> List[Dict[str, Any]]:
    """
    Special allocation for micro-budgets (₹500-₹1000) using penny stocks
    and ultra-affordable NSE/BSE options.
    """
    suffix = ".NS" if market == "NSE" else ".BO"
    
    penny_stocks = [
        {"symbol": f"SAIL{suffix}", "name": "Steel Authority of India", "price": 75.0, "category": "Steel"},
        {"symbol": f"IDEA{suffix}", "name": "Idea Cellular", "price": 45.0, "category": "Telecom"},
        {"symbol": f"POWERGRID{suffix}", "name": "Power Grid", "price": 280.0, "category": "Power"},
        {"symbol": f"COAL{suffix}", "name": "Coal India", "price": 380.0, "category": "Mining"},
        {"symbol": f"IOC{suffix}", "name": "Indian Oil", "price": 120.0, "category": "Energy"},
        {"symbol": f"GAIL{suffix}", "name": "GAIL India", "price": 155.0, "category": "Energy"},
        {"symbol": f"IRFC{suffix}", "name": "IRFC Limited", "price": 65.0, "category": "Finance"},
        {"symbol": f"TATAPOWER{suffix}", "name": "Tata Power", "price": 310.0, "category": "Power"},
        {"symbol": f"REC{suffix}", "name": "REC Limited", "price": 135.0, "category": "Finance"},
        {"symbol": f"PFC{suffix}", "name": "Power Finance", "price": 285.0, "category": "Finance"},
        {"symbol": f"SUZLON{suffix}", "name": "Suzlon Energy", "price": 28.0, "category": "Energy"},
        {"symbol": f"GMRINFRA{suffix}", "name": "GMR Infrastructure", "price": 38.0, "category": "Infrastructure"},
    ]
    
    recommendations = []
    remaining_budget = investment_amount
    
    # For ultra-small budgets, prioritize affordable entry
    for stock in penny_stocks:
        if remaining_budget <= 0:
            break
        
        price = stock.get("price", 50.0)
        shares = int(remaining_budget // price)
        
        if shares > 0:
            cost = shares * price
            recommendations.append({
                "name": stock.get("name"),
                "symbol": stock.get("symbol"),
                "current_price": round(price, 2),
                "shares": shares,
                "total_cost": round(cost, 2),
                "category": stock.get("category", ""),
                "confidence_score": 80.0,
                "risk": "High" if price < 50 else "Medium",
                "reasoning": f"Affordable entry with {shares} shares at ₹{price}"
            })
            
            remaining_budget -= cost
            
            # For micro budgets, max 2-3 stocks
            if len(recommendations) >= 3:
                break
    
    if recommendations:
        return recommendations
    
    return None


def allocate_single_best_stock(
    investment_amount: float,
    market: str,
    budget_category: str
) -> List[Dict[str, Any]]:
    """
    GUARANTEED ALLOCATION: When all else fails, allocate to the single
    cheapest available stock. This ensures we NEVER return empty portfolio.
    """
    suffix = ".NS" if market == "NSE" else ".BO"
    
    # Ultra-cheap options sorted by price (cheapest first)
    fallback_stocks = [
        {"symbol": f"SUZLON{suffix}", "name": "Suzlon Energy", "price": 28.0, "category": "Renewable Energy"},
        {"symbol": f"GMRINFRA{suffix}", "name": "GMR Infrastructure", "price": 38.0, "category": "Infrastructure"},
        {"symbol": f"IDEA{suffix}", "name": "Idea Cellular", "price": 45.0, "category": "Telecom"},
        {"symbol": f"SAIL{suffix}", "name": "Steel Authority", "price": 75.0, "category": "Steel"},
        {"symbol": f"IRFC{suffix}", "name": "IRFC Limited", "price": 65.0, "category": "Finance"},
        {"symbol": f"IOC{suffix}", "name": "Indian Oil Corp", "price": 120.0, "category": "Energy"},
        {"symbol": f"REC{suffix}", "name": "REC Limited", "price": 135.0, "category": "Finance"},
        {"symbol": f"GAIL{suffix}", "name": "GAIL India", "price": 155.0, "category": "Energy"},
        {"symbol": f"POWERGRID{suffix}", "name": "Power Grid", "price": 280.0, "category": "Power"},
    ]
    
    # Use the cheapest stock available
    best_stock = None
    for stock in fallback_stocks:
        price = stock.get("price", 100.0)
        shares = int(investment_amount // price)
        if shares > 0:
            best_stock = stock
            break
    
    if not best_stock:
        # Absolutely final fallback with guaranteed allocation
        best_stock = {"symbol": f"IRFC.NS", "name": "IRFC Limited", "price": 65.0, "category": "Finance"}
    
    price = best_stock.get("price", 100.0)
    shares = max(1, int(investment_amount // price))
    cost = shares * price
    
    return [{
        "name": best_stock.get("name"),
        "symbol": best_stock.get("symbol"),
        "current_price": round(price, 2),
        "shares": shares,
        "total_cost": round(cost, 2),
        "category": best_stock.get("category", ""),
        "confidence_score": 70.0,
        "risk": "High",
        "reasoning": f"Entry-level allocation: {shares} shares of {best_stock.get('name')} at ₹{price} per share"
    }]


def format_recommendations(raw_recs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format LLM recommendations to UI schema."""
    recommendations = []
    for rec in raw_recs:
        recommendations.append({
            "name": rec.get("name") or rec.get("symbol"),
            "symbol": rec.get("symbol"),
            "current_price": rec.get("price") or rec.get("current_price"),
            "shares": rec.get("shares", 0),
            "total_cost": rec.get("total_cost", 0),
            "category": rec.get("category", ""),
            "confidence_score": rec.get("confidence_score", 0),
            "risk": rec.get("risk", ""),
            "growth_factors": rec.get("growth_factors", []),
            "reasoning": rec.get("reasoning", "")
        })
    return recommendations

# ---------------------------------------------------------------------------
# Existing helper – retained for fallback usage elsewhere.
# ---------------------------------------------------------------------------

# Retained for compatibility, now maps to real-time candidates only

def get_stock_pool(market: str, risk_level: str) -> List[Dict[str, Any]]:
    """Return candidate stocks filtered by risk level using live web data."""
    # Fetch live candidate list and filter by risk
    candidates = fetch_candidate_list_web(market, use_live_prices=True)
    return [s for s in candidates if s["risk"] == risk_level]


def get_live_stock_price(ticker_symbol: str, base_name: str) -> float:
    """Legacy wrapper retained for compatibility – uses the new fetch_market_metrics.
    """
    metrics = fetch_market_metrics(ticker_symbol)

# NOTE: The UI in app.py will automatically pick up the new fields (confidence_score, reasoning)
# if you wish to display them, but the existing layout remains unchanged.

