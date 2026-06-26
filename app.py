"""
EasyInvest AI - Main Application entrypoint
This file boots the Streamlit application, configures the dark mode page layout,
routes pages via the sidebar menu, and houses the interactive UI sections.
Features dynamic yfinance integration for market benchmarks, gainers/losers and
interactive Plotly visualizations.
"""

import streamlit as st
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import plotly.graph_objects as go
from modules.aligned_buttons import AlignedButtons
import sys
import json
from modules.live_market_discovery import check_indian_market_status
# Ensure UTF-8 encoding for console output on Windows to support the rupee symbol (₹)
if sys.platform.startswith('win'):
    try:
        # Attempt to set UTF-8 encoding directly on the stdout TextIOWrapper.
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        # Fallback: set the PYTHONIOENCODING environment variable to ensure UTF-8.
        import os
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# Configure the page window layout
st.set_page_config(
    page_title="EasyInvest AI | Premium Stock Advisory & Forecasting",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply CSS styling from style.css
def load_custom_css():
    css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.markdown("""
            <style>
                body {
                    background-color: #0B0E14;
                    color: #FFFFFF;
                }
            </style>
        """, unsafe_allow_html=True)

load_custom_css()

# Import modules dynamically to handle early testing gracefully
try:
    from modules.advisor import calculate_portfolio
    from modules.predictor import download_historical_data, generate_technical_indicators, generate_predictions, plot_interactive_charts
    from modules.learning_assistant import get_financial_explanation
    modules_loaded = True
except ImportError as e:
    st.error(f"Error loading backend modules: {str(e)}")
    modules_loaded = False

# Initialize session state variables
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"sender": "ai", "message": "Hello! I am your EasyInvest AI Tutor. Ask me any question about investing, stock ratios, or market indicators to begin!"}
    ]

# ----------------- DYNAMIC DATA FETCHING & API PIPELINES -----------------

@st.cache_data(ttl=300)
def fetch_index_data() -> dict:
    """
    Fetches real-time prices for NIFTY 50 (^NSEI) and SENSEX (^BSESN) using yFinance.
    If offline or fetching fails, falls back gracefully to realistic dummy data.
    """
    data = {}
    try:
        # 1. NIFTY 50
        nifty = yf.Ticker("^NSEI")
        nifty_history = nifty.history(period="2d")
        if len(nifty_history) >= 2:
            prev_close = nifty_history["Close"].iloc[-2]
            curr_price = nifty_history["Close"].iloc[-1]
            nifty_change = ((curr_price - prev_close) / prev_close) * 100
            data["nifty"] = {"price": round(curr_price, 2), "change": round(nifty_change, 2), "offline": False}
        else:
            raise Exception("Insufficient Nifty data")
            
        # 2. SENSEX
        sensex = yf.Ticker("^BSESN")
        sensex_history = sensex.history(period="2d")
        if len(sensex_history) >= 2:
            prev_close = sensex_history["Close"].iloc[-2]
            curr_price = sensex_history["Close"].iloc[-1]
            sensex_change = ((curr_price - prev_close) / prev_close) * 100
            data["sensex"] = {"price": round(curr_price, 2), "change": round(sensex_change, 2), "offline": False}
        else:
            raise Exception("Insufficient Sensex data")
            
    except Exception as e:
        # High-fidelity mock fallback if internet/API fails
        data["nifty"] = {"price": 22932.40, "change": 0.84, "offline": True}
        data["sensex"] = {"price": 75418.00, "change": 0.79, "offline": True}
        
    return data

@st.cache_data(ttl=300)
def fetch_market_movers() -> dict:
    """
    Fetches stock data for major Indian equities dynamically and returns
    categorized Top Gainers and Top Losers based on daily percentage change.
    """
    stock_changes = []
    # Prefer using cached candidate list (broader universe) and then compute movers via batch download
    cache_path = os.path.join(os.path.dirname(__file__), "data", "cache", "candidates_nse.json")
    try:
        tickers = []
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
                tickers = [c.get("symbol") for c in cached if c.get("symbol")]
        # If cache is empty or missing, fall back to a compact list
        if not tickers:
            tickers = ["TCS.NS", "RELIANCE.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TATAMOTORS.NS", "ZOMATO.NS", "SUZLON.NS"]

        # Limit batch size to keep downloads fast
        tickers = tickers[:40]

        data = yf.download(tickers, period="2d", progress=False, timeout=5)
        if data is not None and not data.empty:
            # Extract Close prices
            close = None
            if isinstance(data.columns, pd.MultiIndex):
                if "Close" in data.columns.levels[0]:
                    close = data["Close"]
            elif "Close" in data.columns:
                close = data["Close"]

            if close is not None:
                # Normalize single-ticker series
                if isinstance(close, pd.Series):
                    close = close.to_frame(name=tickers[0])

                for symbol in close.columns:
                    series = close[symbol].dropna()
                    if len(series) >= 2:
                        prev_close = series.iloc[-2]
                        curr_price = series.iloc[-1]
                        pct_change = ((curr_price - prev_close) / prev_close) * 100 if prev_close != 0 else 0.0
                        stock_changes.append({
                            "symbol": symbol,
                            "name": symbol.split(".")[0],
                            "price": round(curr_price, 2),
                            "change": round(pct_change, 2)
                        })

        if stock_changes:
            sorted_stocks = sorted(stock_changes, key=lambda x: x["change"], reverse=True)
            return {"gainers": sorted_stocks[:5], "losers": sorted_stocks[-5:][::-1], "offline": False}

    except Exception:
        # If batch download fails, try to surface movers from cached file if present
        try:
            if os.path.exists(cache_path):
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    # If cached entries contain a 'change' field, use it, else approximate 0
                    for c in cached[:10]:
                        stock_changes.append({
                            "symbol": c.get("symbol"),
                            "name": c.get("base_name", c.get("symbol", "")),
                            "price": round(c.get("current_price", c.get("price", 0.0)), 2),
                            "change": round(c.get("change", 0.0), 2)
                        })
                    if stock_changes:
                        sorted_stocks = sorted(stock_changes, key=lambda x: x["change"], reverse=True)
                        return {"gainers": sorted_stocks[:5], "losers": sorted_stocks[-5:][::-1], "offline": True}
        except Exception:
            pass

    # Absolute fallback - static list
    return {
        "gainers": [
            {"symbol": "TCS.NS", "name": "TCS", "price": 4012.50, "change": 5.42},
            {"symbol": "INFY.NS", "name": "INFY", "price": 1475.20, "change": 4.89},
            {"symbol": "RELIANCE.NS", "name": "RELIANCE", "price": 2845.75, "change": 3.21},
            {"symbol": "HDFCBANK.NS", "name": "HDFCBANK", "price": 1625.00, "change": 2.95},
            {"symbol": "TITAN.NS", "name": "TITAN", "price": 3280.50, "change": 2.45}
        ],
        "losers": [
            {"symbol": "SUZLON.NS", "name": "SUZLON", "price": 44.80, "change": -4.12},
            {"symbol": "ADANIENT.NS", "name": "ADANIENT", "price": 3122.00, "change": -3.95},
            {"symbol": "TATAMOTORS.NS", "name": "TATAMOTORS", "price": 945.25, "change": -2.85},
            {"symbol": "ZOMATO.NS", "name": "ZOMATO", "price": 178.50, "change": -1.75},
            {"symbol": "KPITTECH.NS", "name": "KPITTECH", "price": 1535.00, "change": -1.55}
        ],
        "offline": True
    }

@st.cache_data(ttl=600)
def fetch_nifty_chart_history() -> pd.DataFrame:
    """
    Downloads historical close prices for NIFTY 50 over the last 30 days to build
    the dashboard area chart.
    """
    try:
        nifty = yf.Ticker("^NSEI")
        df = nifty.history(period="1mo")
        if not df.empty:
            return df[["Close"]]
    except Exception:
        pass
    
    # Mock close curve if offline
    dates = pd.date_range(end=datetime.now(), periods=22, freq="B")
    mock_closes = np.linspace(22000, 22932, 22) + np.random.normal(0, 100, 22)
    return pd.DataFrame({"Close": mock_closes}, index=dates)

# Check Indian stock market status
market_status = check_indian_market_status()
market_badge_text = "🟢 Live Feed" if market_status["is_live"] else "⏸️ Market Closed"

# TOP NAVIGATION BAR with improved spacing
st.markdown(
    "<div style='background: rgba(22, 28, 45, 0.6); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,0.05); padding: 15px 30px; margin: -70px -45px 30px -45px; display: flex; align-items: center; justify-content: space-between;'>"
    "<div style='display: flex; align-items: center; gap: 20px;'>"
    "<h1 style='color: #2962FF; margin: 0px; font-weight: 800; font-size: 36px; letter-spacing: -0.5px;'>EasyInvest AI</h1>"
    "<p style='color: #8F9CAE; font-size: 14px; font-weight: 600; letter-spacing: 1px; margin: 0px;'>INTELLIGENT WEALTH SYSTEMS</p>"
    "</div>"
    "<div style='font-size: 12px; color: #8F9CAE; text-align: right;'>"
    f"{market_badge_text} | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    "</div>"
    "</div>",
    unsafe_allow_html=True
)

# Market Status Banner
if market_status["is_live"]:
    st.markdown(
        f"<div style='background: rgba(0, 200, 83, 0.1); border: 1px solid rgba(0, 200, 83, 0.2); padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; color: #00C853; font-weight: 600;'>"
        f"🟢 <strong>INDIAN STOCK MARKET IS LIVE</strong> &nbsp;|&nbsp; {market_status['status_message']} &nbsp;|&nbsp; {market_status['ist_time']}"
        f"</div>",
        unsafe_allow_html=True
    )
else:
    st.markdown(
        f"<div style='background: rgba(255, 61, 0, 0.1); border: 1px solid rgba(255, 61, 0, 0.2); padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; color: #FF3D00; font-weight: 600;'>"
        f"⏸️ <strong>INDIAN STOCK MARKET IS CLOSED</strong> &nbsp;|&nbsp; {market_status['status_message']} &nbsp;|&nbsp; {market_status['ist_time']}<br>"
        f"<span style='font-size: 13px; font-weight: 400; color: #8F9CAE;'>The dashboard is displaying last active trading data. Real-time updates will resume during market hours: Monday-Friday, 9:15 AM - 3:30 PM IST (excluding holidays).</span>"
        f"</div>",
        unsafe_allow_html=True
    )

# Top Navigation Tabs - Improved Spacing and Font Size
nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(4)

with nav_col1:
    if st.button("Live Market Dashboard", use_container_width=True, key="nav_dash"):
        st.session_state.current_page = "Dashboard"
    st.markdown("<style>div[data-testid='stButton'] button { font-size: 16px; font-weight: 700; padding: 12px 24px; }</style>", unsafe_allow_html=True)
        
with nav_col2:
    if st.button("AI Assistant", use_container_width=True, key="nav_invest"):
        st.session_state.current_page = "Investment Assistant"
        
with nav_col3:
    if st.button("AI Predictor", use_container_width=True, key="nav_pred"):
        st.session_state.current_page = "Stock Predictor"
        
with nav_col4:
    if st.button("AI Learning", use_container_width=True, key="nav_learn"):
        st.session_state.current_page = "Learning Assistant"

# Initialize current page
if "current_page" not in st.session_state:
    st.session_state.current_page = "Dashboard"

st.markdown("---")

# PAGE SELECTION
selected_page = st.session_state.current_page

# Page 1: Dashboard
if selected_page == "Dashboard":
    if not market_status["is_live"]:
        st.info("⏸️ **Market Closed Disclaimer**: The Indian Share Market is currently closed. Live data updates are paused. Shown metrics represent the latest market closing prices.")
        
    # Market Benchmarks Widget (Live Market Dashboard only)
    indices = fetch_index_data()
    
    bench_title_col, refresh_col = st.columns([8, 2])
    with bench_title_col:
        st.markdown("### Live Market Benchmarks")
    with refresh_col:
        if st.button("Refresh Live Data 🔄", key="refresh_live_bench"):
            st.cache_data.clear()
            st.rerun()
            
    bench_col1, bench_col2 = st.columns(2)

    with bench_col1:
        nifty_color = "#00C853" if indices["nifty"]["change"] >= 0 else "#FF3D00"
        nifty_sign = "+" if indices["nifty"]["change"] >= 0 else ""
        st.markdown(
            f"<div style='background: rgba(22, 28, 45, 0.4); border: 1px solid rgba(255,255,255,0.05); padding: 12px; border-radius: 8px;'>"
            f"<span style='font-size:12px; color:#8F9CAE; font-weight:700;'>NIFTY 50</span><br>"
            f"<strong style='font-size:16px;'>₹{indices['nifty']['price']:,}</strong> "
            f"<span style='color:{nifty_color}; font-size:12px; font-weight:700;'>{nifty_sign}{indices['nifty']['change']}%</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    with bench_col2:
        sensex_color = "#00C853" if indices["sensex"]["change"] >= 0 else "#FF3D00"
        sensex_sign = "+" if indices["sensex"]["change"] >= 0 else ""
        st.markdown(
            f"<div style='background: rgba(22, 28, 45, 0.4); border: 1px solid rgba(255,255,255,0.05); padding: 12px; border-radius: 8px;'>"
            f"<span style='font-size:12px; color:#8F9CAE; font-weight:700;'>SENSEX</span><br>"
            f"<strong style='font-size:16px;'>₹{indices['sensex']['price']:,}</strong> "
            f"<span style='color:{sensex_color}; font-size:12px; font-weight:700;'>{sensex_sign}{indices['sensex']['change']}%</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")
    st.markdown("<h1 style='font-weight: 800; margin-bottom: 5px; font-size: 36px; letter-spacing: -0.5px;'>Market Overview</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8F9CAE; font-size: 16px; margin-bottom: 30px;'>Dynamic financial benchmarks and top trending equity symbols fetched live via yFinance.</p>", unsafe_allow_html=True)
    
    # 1. Glassmorphism Indices Indicators
    col1, col2 = st.columns(2)
    with col1:
        nifty_sign = "+" if indices["nifty"]["change"] >= 0 else ""
        n_color = "#00C853" if indices["nifty"]["change"] >= 0 else "#FF3D00"
        st.markdown(
            f"<div class='stock-card' style='border-top: 3px solid {n_color};'>"
            f"<div class='stock-card-header'>"
            f"<span class='stock-name'>NIFTY 50 Benchmark</span>"
            f"<span class='stock-symbol' style='background: rgba(41, 98, 255, 0.08); color: {n_color}; border-color: rgba(0,0,0,0); font-size: 14px;'>{nifty_sign}{indices['nifty']['change']}%</span>"
            f"</div>"
            f"<h2 style='margin: 0px; font-size: 32px; font-weight: 800;'>₹{indices['nifty']['price']:,}</h2>"
            f"<p style='color: #8F9CAE; margin-top: 6px; font-size: 13px; font-weight: 500;'>National Stock Exchange of India • NSEI</p>"
            f"</div>",
            unsafe_allow_html=True
        )
    with col2:
        sensex_sign = "+" if indices["sensex"]["change"] >= 0 else ""
        s_color = "#00C853" if indices["sensex"]["change"] >= 0 else "#FF3D00"
        st.markdown(
            f"<div class='stock-card' style='border-top: 3px solid {s_color};'>"
            f"<div class='stock-card-header'>"
            f"<span class='stock-name'>SENSEX Benchmark</span>"
            f"<span class='stock-symbol' style='background: rgba(41, 98, 255, 0.08); color: {s_color}; border-color: rgba(0,0,0,0); font-size: 14px;'>{sensex_sign}{indices['sensex']['change']}%</span>"
            f"</div>"
            f"<h2 style='margin: 0px; font-size: 32px; font-weight: 800;'>₹{indices['sensex']['price']:,}</h2>"
            f"<p style='color: #8F9CAE; margin-top: 6px; font-size: 13px; font-weight: 500;'>Bombay Stock Exchange • BSESN</p>"
            f"</div>",
            unsafe_allow_html=True
        )
    
    st.markdown("---")
    
    # Dynamic Gainers/Losers Layout - Top 5
    st.markdown("### 🔥 Live Market Movers - Top 5 Gainers & Losers")
    movers = fetch_market_movers()
    
    g_col, l_col = st.columns(2)
    with g_col:
        st.markdown("<h4 style='color: #00C853; font-weight: 700; margin-bottom: 15px;'>🟢 Dynamic Top Gainers</h4>", unsafe_allow_html=True)
        for g in movers["gainers"][:3]:
            st.markdown(
                f"<div class='stock-card' style='border-left: 4px solid #00C853; padding: 18px; margin-bottom: 12px;'>"
                f"<div class='stock-card-header' style='padding-bottom: 8px; margin-bottom: 8px;'>"
                f"<div><span style='font-size: 18px; font-weight: 700;'>{g['symbol']}</span><br><span style='color: #8F9CAE; font-size: 11px;'>Active Indian Stock</span></div>"
                f"<span class='shares-badge' style='background: rgba(0, 200, 83, 0.1); color: #00C853;'>+{g['change']}%</span>"
                f"</div>"
                f"<div class='stock-price-section' style='margin-top: 8px;'>"
                f"<span class='price-label'>Current Price</span>"
                f"<strong style='font-size: 20px;'>₹{g['price']:,}</strong>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            
    with l_col:
        st.markdown("<h4 style='color: #FF3D00; font-weight: 700; margin-bottom: 15px;'>🔴 Dynamic Top Losers</h4>", unsafe_allow_html=True)
        for l in movers["losers"][:3]:
            st.markdown(
                f"<div class='stock-card' style='border-left: 4px solid #FF3D00; padding: 18px; margin-bottom: 12px;'>"
                f"<div class='stock-card-header' style='padding-bottom: 8px; margin-bottom: 8px;'>"
                f"<div><span style='font-size: 18px; font-weight: 700;'>{l['symbol']}</span><br><span style='color: #8F9CAE; font-size: 11px;'>Active Indian Stock</span></div>"
                f"<span class='shares-badge' style='background: rgba(255, 61, 0, 0.1); color: #FF3D00; border-color: rgba(255, 61, 0, 0.2);'>{l['change']}%</span>"
                f"</div>"
                f"<div class='stock-price-section' style='margin-top: 8px;'>"
                f"<span class='price-label'>Current Price</span>"
                f"<strong style='font-size: 20px;'>₹{l['price']:,}</strong>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True
            )

# Page 2: Investment Assistant
elif selected_page == "Investment Assistant":
    st.markdown("<h1 style='font-weight: 800; margin-bottom: 5px; font-size: 36px; letter-spacing: -0.5px;'>AI Investment Assistant</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8F9CAE; font-size: 16px; margin-bottom: 30px;'>Diversify capital seamlessly. Maps cash budget to equity sectors matching your risk-reward threshold.</p>", unsafe_allow_html=True)
    
    # 2. Inputs Panels
    col1, col2, col3 = st.columns(3)
    with col1:
        invest_amount = st.number_input("Investment Capacity (INR ₹)", min_value=500.0, value=500.0, step=500.0, help="e.g., 500")
        risk_level = st.select_slider("Risk Tolerance Threshold", ["Low", "Medium", "High"])
    with col2:
        market_choice = st.selectbox("Stock Market Target", ["NSE", "BSE"])
        horizon_choice = st.selectbox("Preferred Holding Period", ["Long Term", "Short Term"])
    with col3:
        st.write("")
        st.write("")
        assist_clicked = AlignedButtons().render_assist()
    
    # Render allocations
    if assist_clicked and modules_loaded:
        with st.spinner("Analyzing quantitative risk portfolios..."):
            portfolio = calculate_portfolio(invest_amount, market_choice, risk_level, horizon_choice)
            
            st.markdown(f"### 📋 {portfolio['suggested_type']}")
            
            # Displays stock recommended cards
            recs = portfolio["recommendations"]
            if len(recs) == 0:
                st.info("Based on the current budget and selected risk level, no whole shares could be allocated. Consider adjusting the risk level, increasing the investment amount, or reviewing the recommended stocks list.")
            else:
                card_cols = st.columns(len(recs))
                for i, rec in enumerate(recs):
                    with card_cols[i]:
                        st.markdown(
                            f"<div class='stock-card' style='height: 100%; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid rgba(255,255,255,0.1);'>"
                            f"<div class='stock-card-header'>"
                            f"<span class='stock-name'>{rec['name'].split()[0]}</span>"
                            f"<span class='stock-symbol'>{rec['symbol']}</span>"
                            f"</div>"
                            f"<div class='stock-price-section' style='margin-top: 16px;'>"
                            f"<div>"
                            f"<span class='price-label'>CMP</span><br>"
                            f"<strong style='font-size: 18px;'>₹{rec['current_price']:,}</strong>"
                            f"</div>"
                            f"<span class='shares-badge'>Shares: {rec['shares']}</span>"
                            f"</div>"
                            f"<div style='margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.05); font-size: 13px; text-align: right;'>"
                            f"Total Allocation:<br><strong style='font-size: 16px; color:#2962FF;'>₹{rec['total_cost']:,}</strong>"
                            f"</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                
                st.markdown("<br>", unsafe_allow_html=True)
                stat_col1, stat_col2, stat_col3 = st.columns(3)
                with stat_col1:
                    st.metric("Total Capital Allocated", f"₹{portfolio['total_allocated']:,}")
                with stat_col2:
                    st.metric("Leftover Liquid Cash", f"₹{portfolio['leftover_cash']:,}")
                with stat_col3:
                    utilization = (portfolio['total_allocated'] / invest_amount) * 100
                    st.metric("Capital Utilization Efficiency", f"{utilization:.1f}%")
                
                st.markdown("---")
                st.markdown("**Why these stocks?**")
                st.write(portfolio.get('reasoning', 'AI-driven allocation optimized for your budget and risk profile.'))
# Page 3: Stock Predictor
elif selected_page == "Stock Predictor":
    st.markdown("<h1 style='font-weight: 800; margin-bottom: 5px; font-size: 36px; letter-spacing: -0.5px;'>AI Stock Predictor</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8F9CAE; font-size: 16px; margin-bottom: 30px;'>Pull-down real-time equity metrics, construct key quantitative oscillators, and run deep-learning LSTM time-series forecasts.</p>", unsafe_allow_html=True)
    
    symbol_col, btn_col = st.columns([3, 1])
    with symbol_col:
        stock_symbol = st.text_input("Enter NSE/BSE Stock Ticker Symbol:", placeholder="E.g: TCS.NS", help="Include market suffixes (.NS for NSE, .BO for BSE)")
    with btn_col:
        st.write("")
        st.write("")
        predict_clicked = AlignedButtons().render_predict()
    
    if predict_clicked and modules_loaded:
        if not stock_symbol:
            st.error("❌ Please enter a stock ticker symbol.")
        else:
            with st.spinner("Downloading financial timelines and running LSTM weights..."):
                try:
                    hist_df = download_historical_data(stock_symbol)
                    hist_df = generate_technical_indicators(hist_df)
                    forecast = generate_predictions(stock_symbol, hist_df)
                    
                    # 1. Beautiful Recommendation Card and Metric Grid
                    rec_badge = "badge-buy"
                    if forecast["recommendation"] == "SELL":
                        rec_badge = "badge-sell"
                    elif forecast["recommendation"] == "HOLD":
                        rec_badge = "badge-hold"
                        
                    st.markdown(
                        f"<div class='stock-card'>"
                        f"<div class='stock-card-header' style='border-bottom:none;'>"
                        f"<div>"
                        f"<h2 style='margin: 0px;'>{stock_symbol} Forecasting Dashboard</h2>"
                        f"<p style='color: #8F9CAE; margin: 5px 0 0 0; font-size: 13px;'>LSTM Sequence Memory Analysis • Live Feed</p>"
                        f"</div>"
                        f"<span class='{rec_badge}' style='font-size: 18px;'>AI SIGNAL: {forecast['recommendation']}</span>"
                        f"</div>"
                        f"<hr style='border: 0; height: 1px; background: rgba(255, 255, 255, 0.08); margin: 15px 0;'>"
                        f"<div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; padding: 10px 0;'>"
                        f"<div><span style='color: #8F9CAE; font-size: 13px; font-weight: 500;'>Current Price</span><h3 style='margin: 6px 0 0 0; font-size: 26px; font-weight: 800;'>₹{forecast['current_price']:,}</h3></div>"
                        f"<div><span style='color: #8F9CAE; font-size: 13px; font-weight: 500;'>Tomorrow</span><h3 style='margin: 6px 0 0 0; font-size: 22px; font-weight: 800; color: #00C853;'>₹{forecast['tomorrow']['low']:.0f} - ₹{forecast['tomorrow']['high']:.0f}</h3></div>"
                        f"<div><span style='color: #8F9CAE; font-size: 13px; font-weight: 500;'>Next Week</span><h3 style='margin: 6px 0 0 0; font-size: 22px; font-weight: 800; color: #00C853;'>₹{forecast['next_week']['low']:.0f} - ₹{forecast['next_week']['high']:.0f}</h3></div>"
                        f"<div><span style='color: #8F9CAE; font-size: 13px; font-weight: 500;'>Next Month</span><h3 style='margin: 6px 0 0 0; font-size: 22px; font-weight: 800; color: #00C853;'>₹{forecast['next_month']['low']:.0f} - ₹{forecast['next_month']['high']:.0f}</h3></div>"
                        f"</div>"
                        f"<div style='margin-top: 20px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 15px; display: flex; justify-content: space-between; align-items: center;'>"
                        f"<span style='color: #8F9CAE; font-size: 14px;'>LSTM Model Convergence Stability</span>"
                        f"<strong style='font-size: 18px; color: #2962FF;'>{forecast['confidence_score']}% Confidence Score</strong>"
                        f"</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                    
                    # 2. Plotly Charts Layout
                    st.markdown("### 📊 Actual Price (Green) vs Predicted Price (Red) & Future Forecast")
                    fig = plot_interactive_charts(hist_df, stock_symbol, forecast)
                    
                    # Generate confidence band coordinates visually to wow user
                    dates = hist_df.index
                    closes = hist_df["Close"]
                    
                    # Predict bounds - RED LINE FOR PREDICTED PRICES
                    fig.add_trace(go.Scatter(
                        x=[dates[-1], dates[-1] + timedelta(days=1), dates[-1] + timedelta(days=7), dates[-1] + timedelta(days=30)],
                        y=[closes.iloc[-1], (forecast['tomorrow']['low'] + forecast['tomorrow']['high'])/2, (forecast['next_week']['low'] + forecast['next_week']['high'])/2, (forecast['next_month']['low'] + forecast['next_month']['high'])/2],
                        mode="lines+markers",
                        name="Predicted Price (Future)",
                        line=dict(color="#FF3D00", width=3, dash="dash"),
                        marker=dict(size=8, color="#FF3D00")
                    ))
                    
                    # Translucent confidence shading
                    predict_dates = [dates[-1], dates[-1] + timedelta(days=1), dates[-1] + timedelta(days=7), dates[-1] + timedelta(days=30)]
                    high_bounds = [closes.iloc[-1], forecast['tomorrow']['high'], forecast['next_week']['high'], forecast['next_month']['high']]
                    low_bounds = [closes.iloc[-1], forecast['tomorrow']['low'], forecast['next_week']['low'], forecast['next_month']['low']]
                    
                    fig.add_trace(go.Scatter(
                        x=predict_dates + predict_dates[::-1],
                        y=high_bounds + low_bounds[::-1],
                        fill="toself",
                        fillcolor="rgba(255, 61, 0, 0.08)",
                        line=dict(color="rgba(0,0,0,0)"),
                        name="Prediction Confidence Range",
                        showlegend=True
                    ))
                    
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                except ValueError as e:
                    st.error(f"❌ {str(e)}")
                except Exception as e:
                    st.error(f"❌ An error occurred: {str(e)}")

# Page 4: Learning Assistant
elif selected_page == "Learning Assistant":
    st.markdown("<h1 style='font-weight: 800; margin-bottom: 5px; font-size: 36px; letter-spacing: -0.5px;'>AI Learning Assistant</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8F9CAE; font-size: 16px; margin-bottom: 25px;'>Premium conversational chatbot workspace. Ask custom finance queries to learn investing fundamentals.</p>", unsafe_allow_html=True)
    
    # 4. Chat Workspace Layout - Improved UI
    st.markdown("### 💬 Chat Assistant")
    chat_box = st.container(height=380, border=True)
    with chat_box:
        for chat in st.session_state.chat_history:
            bubble_class = "chat-bubble-ai" if chat["sender"] == "ai" else "chat-bubble-user"
            align_div = "left" if chat["sender"] == "ai" else "right"
            st.markdown(
                f"<div style='text-align: {align_div}; margin-bottom: 10px;'>"
                f"<div class='chat-bubble {bubble_class}' style='display: inline-block; text-align: left; max-width: 85%;'>"
                f"{chat['message']}"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            
    # Query Input Section
    st.markdown("### ❓ Ask a Question")
    query_col1, query_col2 = st.columns([4, 1])
    
    with query_col1:
        custom_in = st.text_input(
            "Your question:",
            placeholder="E.g: What is a P/E ratio? How do I calculate compound interest? What's the difference between stocks and bonds?",
            key="user_chat_input_new"
        )
    
    with query_col2:
        st.write("")
        ask_clicked = AlignedButtons().render_ask()
    
    if ask_clicked and custom_in and modules_loaded:
        # Append User question
        st.session_state.chat_history.append({"sender": "user", "message": custom_in})
        
        # Call Gemini backend API or fallbacks
        with st.spinner("AI Tutor is formulating an answer..."):
            ans = get_financial_explanation(custom_in, st.session_state.chat_history)
            st.session_state.chat_history.append({"sender": "ai", "message": ans})
            st.rerun()
