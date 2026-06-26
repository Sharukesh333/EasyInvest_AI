# EasyInvest AI 📈

EasyInvest AI is a production-quality, modern AI-driven financial wealth assistant and deep-learning stock predictor specifically engineered for beginner investors. Inspired by premium financial platforms like **Groww, Zerodha, and TradingView**, this system provides a beautiful, unified dark-mode dashboard housing state-of-the-art predictive quantitative tools and AI-powered tutor interfaces.

---

## 🌟 Architectural Features

### 1. AI Investment Assistant (Module 1)
- Maps beginner capital (₹) and risk thresholds (**Low, Medium, High**) to customized diversified stock baskets.
- Formulates integer share allocation schemas (avoiding fractionals) and minimal leftover cash indexes.
- Renders results in highly aesthetic custom portfolio cards rather than basic spreadsheets.

### 2. AI Stock Predictor (Module 2)
- Downloads daily historical data directly from financial exchanges via the **yFinance** pipeline.
- Performs feature engineering to compute core momentum, trend, and volatility oscillators (**RSI**, **MACD**, **SMA50**, **SMA200**, **Volatility**, **Volume Trend**).
- Simulates recurrent neural network forecasts utilizing **LSTM** weights to output Tomorrow, Next Week, and Next Month price ranges along with dynamic **Confidence Scores** and `BUY/HOLD/SELL` signals.
- Generates TradingView-inspired interactive graphs with customized confidence shading.

### 3. AI Learning Assistant (Module 3)
- Integrates with the **Google Gemini API** (`gemini-1.5-flash`) to offer dynamic, analogical, beginner-friendly definitions of core financial metrics.
- Provides a responsive offline local knowledge base as a backup.

---

## 📂 Project Directory Structure

```text
EasyInvestAI/
│
├── app.py                      # Main entry point (Streamlit UI, Page Router & Dashboard)
├── requirements.txt            # Package dependency specifications
├── README.md                   # Complete developer and user manual
│
├── modules/                    # Core modular code package
│   ├── __init__.py             # Makes 'modules' a python package
│   ├── advisor.py              # Module 1: AI Investment Assistant portfolio allocation logic
│   ├── predictor.py            # Module 2: Stock Predictor, indicators, LSTM inference, Plotly plots
│   └── learning_assistant.py   # Module 3: Gemini AI Learning Assistant (LLM financial educator)
│
├── models/                     # Holds serialized trained LSTM models and MinMaxScaler scalers
│
├── data/
│   ├── raw/                    # Caches raw yFinance stock historical CSV/JSON files
│   └── processed/              # Caches calculated technical indicators (RSI, MACD, etc.)
│
└── assets/
    └── style.css               # Modern sleek dark-theme styles (Zerodha, Groww & TradingView inspired)
```

---

## 🛠️ Installation & Setup

### 1. Clone & Navigate
Ensure you are in the workspace root directory:
```powershell
cd "c:\Users\SHARUKESH GANESAN\OneDrive\Attachments\Desktop\EasyInvest AI"
```

### 2. Create Virtual Environment (Recommended)
Create and activate a clean local Python virtual environment to isolate the dependencies:
```powershell
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
Install the required packages using the pinned manifest:
```powershell
pip install -r requirements.txt
```

---

## 🚀 Running the Application

Boot the Streamlit server directly:
```powershell
streamlit run app.py
```
This will automatically open the interactive dashboard in your default browser at:
`http://localhost:8501`

---

## 🧪 Phase 1 Verification and Testing

To verify the installation and system architecture files are set up correctly:

1. **Verify directory existence:**
   Confirm the `modules/`, `assets/`, `models/`, and `data/` directories exist on disk.
2. **Sanity Import Test:**
   Execute a simple Python shell import to make sure all dependencies resolve properly:
   ```powershell
   python -c "import streamlit, tensorflow, sklearn, plotly, pandas, numpy, yfinance, google.generativeai; print('All libraries imported successfully!')"
   ```
3. **Execution Test:**
   Ensure `streamlit run app.py` boots without any syntax or path-routing warnings.
