# 🤖 FusionBot - AI-Powered Crypto Trading Bot

An event-driven trading system that fuses **News Sentiment** with **Technical Analysis** for low-risk crypto trading.

## 🎯 Philosophy

> "Survival first, Profit second."

FusionBot is designed for traders with limited capital who cannot afford losses from bugs, crashes, or market chaos. It implements a paranoid approach to safety with multiple layers of protection.

## ✨ Key Features

- **Fusion Analysis**: Combines RSS news sentiment with technical indicators (RSI, EMA, MACD) using Google Gemini AI
- **Hybrid Stop-Loss System**: 
  - Virtual stops (-2%) managed by bot for optimal exits
  - Catastrophe stops (-10%) on exchange for disaster protection
- **Macro Guard**: Monitors financial news for Fed/CPI/war keywords to enter defensive mode
- **Time Decay**: Auto-closes zombie trades after 4 hours
- **Zero Amnesia**: PostgreSQL persistence survives bot crashes
- **Paper Trading**: Test strategies with fake money before going live

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MAIN LOOP                            │
├─────────────────────────────────────────────────────────────┤
│  1. Health Check     │  Exchange, Database, AI connectivity │
│  2. Macro Guard      │  Scan for Fed/CPI/War keywords       │
│  3. Position Manager │  Check SL/TP, time decay, sync       │
│  4. News Aggregator  │  Fetch & filter RSS news             │
│  5. Technical Analyzer│ Compute RSI, EMA, MACD              │
│  6. Fusion Brain     │  AI decision (Gemini 1.5 Flash)      │
│  7. Order Executor   │  Execute with dual stop-loss         │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
fusionbot/
├── src/
│   ├── config/           # Settings & constants
│   ├── core/             # Domain models, enums, exceptions
│   ├── infrastructure/   # Database, Exchange, API clients
│   ├── services/         # Business logic services
│   └── strategies/       # Trading strategies
├── scripts/              # Utility scripts
├── data/                 # Database files
├── logs/                 # Log files
├── main.py               # Entry point
└── requirements.txt      # Dependencies
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL (or SQLite for testing)
- Binance account (testnet for development)
- Google Gemini API key

### 2. Installation

```bash
# Clone the repository
cd ai-trading-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy the example environment file
cp env.example .env

# Edit with your credentials
nano .env
```

Required environment variables:
- `DATABASE_URL` - PostgreSQL connection string
- `BINANCE_API_KEY` / `BINANCE_API_SECRET` - Binance credentials
- `GOOGLE_API_KEY` - Gemini API key

### 4. Run in Paper Mode

```bash
# Start with paper trading (safe, no real money)
python main.py

# With verbose output
python main.py --verbose

# Check status
python main.py --status
```

### 5. Run Infrastructure Tests

```bash
python scripts/test_infrastructure.py
```

## 📊 Trading Strategy

### Entry Conditions (ALL must be true)
- ✅ Positive news sentiment detected
- ✅ RSI < 70 (not overbought)
- ✅ Bullish trend (price > EMA50)
- ✅ AI confidence > 70%
- ✅ No macro danger detected
- ✅ Price hasn't moved > 1.5% since news

### Exit Conditions (ANY triggers exit)
- 📉 Virtual Stop Loss hit (-2%)
- 📈 Virtual Take Profit hit (+4%)
- ⏰ Time decay (> 4 hours)
- 🛡️ Defensive mode triggered
- 💥 Catastrophe stop hit (-10%)

## ⚙️ Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `TRADING_MODE` | `paper` | `paper` or `live` |
| `MAX_RISK_PER_TRADE` | `0.02` | Risk 2% per trade |
| `VIRTUAL_STOP_LOSS_PCT` | `-0.02` | -2% stop loss |
| `VIRTUAL_TAKE_PROFIT_PCT` | `0.04` | +4% take profit |
| `CATASTROPHE_STOP_LOSS_PCT` | `-0.10` | -10% disaster stop |
| `MAX_TRADE_DURATION_HOURS` | `4` | Zombie trade limit |
| `MIN_CONFIDENCE_THRESHOLD` | `70` | AI confidence minimum |

## 🛡️ Safety Features

1. **Position Limits**: Max 1 concurrent position by default
2. **Defensive Mode**: Auto-pauses trading on macro risk detection
3. **Dual Stop-Loss**: Virtual (optimal) + Catastrophe (disaster insurance)
4. **Chase Prevention**: Won't buy if price moved > 1.5% since news
5. **Volatility Guard**: Rejects trades in high-ATR conditions
6. **Dry Run Mode**: Log without executing for testing

## 📈 Performance Monitoring

Check current status:
```bash
python main.py --status
```

View logs:
```bash
tail -f logs/fusionbot.log
```

## ⚠️ Risk Disclaimer

**TRADING CRYPTOCURRENCIES INVOLVES SUBSTANTIAL RISK OF LOSS.**

- Never trade with money you cannot afford to lose
- Always start with paper trading for at least 4 weeks
- Past performance does not guarantee future results
- This software is provided "as-is" without warranty

## 📝 License

MIT License - See LICENSE file for details.

---

Built with ❤️ for capital preservation.

