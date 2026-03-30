# IMC Prosperity 4 — Stochastic Backtesting Engine

An advanced, custom-built backtesting framework designed for the [IMC Prosperity 4 challenge](https://prosperity.imc.com/).

**Attribution & Origins:** This repository is a heavily modified and mathematically enhanced fork of [Kevin Fu's Prosperity 4 Backtester](https://github.com/kevin-fu1/imc-prosperity-4-backtester) (which was originally inspired by `jmerle/imc-prosperity-3-backtester`). We have retained the excellent Object-Oriented Programming (OOP) architecture from Kevin's build, but restructured the data ingestion for modular team development and replaced the default deterministic matching engine with a custom Stochastic Fill Model.

**License:** MIT License

---

## 1. The Quant Philosophy: Why We Built This

Standard open-source backtesters rely on **Deterministic Matching** (Price-Time Priority). If a passive limit order touches the market's mid-price, the engine assumes a 100% fill rate. In high-frequency market making, this is a dangerous assumption that leads to overfitted PnL and ignores **Adverse Selection** (getting filled exactly when the market is crashing through your price level).

### Our Solution: The Stochastic Fill Engine
To simulate realistic market microstructure, this engine evaluates passive limit orders using a probabilistic Monte Carlo execution model at every time step. We model the probability of execution `P(fill)` using two primary microstructural features:

* **Volume Imbalance (Order Book Pressure):** `Imbalance = V_bid / (V_bid + V_ask)`
  If Imbalance approaches 1.0 (heavy buy pressure), passive **Sell** orders receive a massive probability multiplier, simulating an aggressive market buyer crossing the spread.
* **Spatial Decay (Distance to Mid-Price):** `Distance Penalty = e^(-0.5 * |P_mid - P_order|)`
  Simulates the Poisson arrival of market orders. Deep out-of-the-money limit orders have exponentially lower probabilities of being reached by liquidity-taking flow.

---

## 2. Overall Structure & Execution Flow

The architecture of the program is modularized to cleanly separate data loading, simulation execution, and order matching. 

### Component Breakdown
#### 1. The `BackTester` (Main Controller)
This is the top-level driver of the simulation:
* **Initialization:** Ingests your trading logic via the CLI.
* **Iteration:** Iterates through a nested loop for each requested round and day. For every day, it executes the `TestRunner` and appends the daily output to a results list.
* **Completion:** Once all rounds are processed, it merges the data and produces a consolidated log file (e.g., `2026-03-30_08-35-51.log`).

#### 2. The `TestRunner` (Daily Simulator)
Responsible for simulating the market environment for a single day:
* **Read Data:** Triggers the `BackDataReader` to ingest CSV price and trade files, returning a `BacktestData` object.
* **Timestamp Loop:** For each timestamp:
    1. **Initialize State:** Prepares the `TradingState` object.
    2. **Algorithm Execution:** Passes the state into your custom `Trader` class. Your algorithm processes the state and returns proposed orders.
    3. **Create Activity Logs:** Records the actions, standard output (`lambda_log`), and market state.
    4. **Match Orders:** Passes proposed orders to the `OrderMatchMaker`. **[UPGRADED]** This is where our Stochastic Engine evaluates the order book imbalance and spatial distance to probabilistically fill orders against historical data.

#### 3. Explanation of Data Models
The backtester relies on specific data models to process information cleanly. 
* **`datamodel.py`**: Contains the core data models shared between the engine and your custom Algorithm. **(CRITICAL: Do not change this file. Modifying it will break compatibility with the official Prosperity submission environment).**
* **`models/input.py`**: Captures raw market data from CSVs (`PriceRow`, `TradeRow`) and structures it into the `BacktestData` source model.
* **`models/output.py`**: Captures the generated test results (`BacktestResult`) which are eventually written to the final output `.log` file.

---

## 3. 🚀 Running the Simulation (Team Setup)

### Initial Setup
Do not install dependencies globally. Use a virtual environment.
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt

We use a custom Typer CLI to run experiments cleanly.

**Syntax:** `python main.py [ALGO_PATH] [ROUND] --data [DATA_DIR] --match-trades [MODE]`

**Run with realistic probabilistic matching (Recommended):**
This mode simulates adverse selection and order book queueing.
```bash
python main.py algo/strategy_v1.py 0 --data data/ --match-trades probabilistic

**Develop & Commit:** Write your code in the `algo/` folder, then stage and commit.
```bash
git add algo/tomatoes.py
git commit -m "Implement rolling Z-score for Tomatoes"