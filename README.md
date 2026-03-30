# IMC Prosperity 4 — Stochastic Backtesting Engine

An advanced, custom-built backtesting framework designed for the [IMC Prosperity 4 challenge](https://prosperity.imc.com/).

**Attribution & Origins:** This repository is a heavily modified and mathematically enhanced fork of [Kevin Fu's Prosperity 4 Backtester](https://github.com/kevin-fu1/imc-prosperity-4-backtester) (which was originally inspired by `jmerle/imc-prosperity-3-backtester`). We have retained the excellent Object-Oriented Programming (OOP) architecture from Kevin's build, but restructured the data ingestion for modular team development and replaced the default deterministic matching engine with a custom Stochastic Fill Model.

**License:** MIT License

---

## The Quant Philosophy: Why We Built This

Standard open-source backtesters rely on **Deterministic Matching** (Price-Time Priority). If a passive limit order touches the market's mid-price, the engine assumes a 100% fill rate. In high-frequency market making, this is a dangerous assumption that leads to overfitted PnL and ignores **Adverse Selection** (getting filled exactly when the market is crashing through your price level).

### Our Solution: The Stochastic Fill Engine
To simulate realistic market microstructure, this engine evaluates passive limit orders using a probabilistic Monte Carlo execution model at every time step. We model the probability of execution `P(fill)` using two primary microstructural features:

* **Volume Imbalance (Order Book Pressure):** `Imbalance = V_bid / (V_bid + V_ask)`
  If Imbalance approaches 1.0 (heavy buy pressure), passive **Sell** orders receive a massive probability multiplier, simulating an aggressive market buyer crossing the spread.
* **Spatial Decay (Distance to Mid-Price):** `Distance Penalty = e^(-0.5 * |P_mid - P_order|)`
  Simulates the Poisson arrival of market orders. Deep out-of-the-money limit orders have exponentially lower probabilities of being reached by liquidity-taking flow.

---

## Overall Structure & Execution Flow

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

## Running the Simulation (Team Setup)

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
## Algorithm Boilerplate (Required for Visualizer)

In order for the community visualizer to parse our backtest logs, **every algorithm file must include the custom Logger class** and properly flush its data at the end of the `run` method.

Please copy and paste this exact layout when creating a new strategy in `algo/my_strategy.py`:

```python
import json
import jsonpickle
from typing import Any, List, Dict
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

# ==========================================
# VISUALIZER LOGGER BOILERPLATE (DO NOT EDIT)
# ==========================================
class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(self.to_json([
            self.compress_state(state, ""),
            self.compress_orders(orders),
            conversions, "", "",
        ]))

        max_item_length = (self.max_log_length - base_length) // 3

        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp, trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        return {s: [od.buy_orders, od.sell_orders] for s, od in order_depths.items()}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        return [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp] for arr in trades.values() for t in arr]

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {p: [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff, o.importTariff, o.sugarPrice, o.sunlightIndex] for p, o in observations.conversionObservations.items()}
        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for arr in orders.values() for o in arr]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = value[:mid]
            if len(candidate) < len(value): candidate += "..."
            if len(json.dumps(candidate)) <= max_length:
                out = candidate
                lo = mid + 1
            else: hi = mid - 1
        return out

logger = Logger()

# ==========================================
# YOUR TRADING ALGORITHM
# ==========================================
class Trader:
    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        result = {}
        conversions = 0
        trader_data = ""

        # --- TODO: ADD YOUR STRATEGY LOGIC HERE ---
        
        # Example dummy state output for formatting
        s = "dummy_data" 
        
        # --- END STRATEGY LOGIC ---

        # ----------------------------------------------------
        # CRITICAL: Format data for the visualizer before returning
        # ----------------------------------------------------
        encoded_trader_data = jsonpickle.encode(s)
        logger.flush(state, result, conversions, encoded_trader_data)
        
        return result, conversions, encoded_trader_data
```

---

## Visualizing Results

After a successful run, the engine generates a timestamped `.log` file in the `backtests/` directory.

We integrate directly with the open-source community visualizer to analyze PnL, inventory risk, and trade execution:
1. Navigate to: [IMC Prosperity 4 Visualizer](https://kevin-fu1.github.io/imc-prosperity-4-visualizer/)
2. Drag and drop your `.log` file into the browser.