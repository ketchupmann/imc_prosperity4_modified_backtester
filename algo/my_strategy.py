"""
Copy the logger class and paste it before your code.
"""

from typing import List, Dict
import jsonpickle

import json
from typing import Any

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""

        while lo <= hi:
            mid = (lo + hi) // 2

            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."

            encoded_candidate = json.dumps(candidate)

            if len(encoded_candidate) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return out


logger = Logger()

"""
Prosperity 4 — Round 0

EMERALDS : Same as 11. Market Making.
TOMATOES : Z-Score Mean Reversion & Market Making (PASSIVE SKEW ONLY)
           Window=10. Thresholds = +/- 1.5 for entry, +/- 0.1 for exit.
           - We no longer cross the spread to enter trades, as that pays 
             13 ticks of edge and destroys PnL! 
           - Instead, we skew our passive quotes aggressively.
           - We use state.traderData to save 10-tick rolling mid-price.
"""

from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import jsonpickle

FAIR          = 10_000
E_LIMIT       = 80
E_FLATTEN     = 70
E_FLATTEN_VOL = 15

T_LIMIT       = 80
T_FLATTEN     = 70
T_FLATTEN_VOL = 15

class Trader:

    def bid(self):
        return 13

    def run(self, state: TradingState):
        try:
            s = jsonpickle.decode(state.traderData) if state.traderData else {}
        except Exception:
            s = {}

        if "TOMATOES_HISTORY" not in s:
            s["TOMATOES_HISTORY"] = []

        result: Dict[str, List[Order]] = {}

        # ═════════════════════════════════════════════════════════════════════
        # EMERALDS — TOMATOES-style MM at market_best+1 / market_best-1
        # ═════════════════════════════════════════════════════════════════════
        if "EMERALDS" in state.order_depths:
            od  = state.order_depths["EMERALDS"]
            pos = state.position.get("EMERALDS", 0)
            orders: List[Order] = []

            best_bid = max(od.buy_orders.keys(),  default=None)
            best_ask = min(od.sell_orders.keys(), default=None)

            if best_bid is not None and best_ask is not None:
                buy_cap  = E_LIMIT - pos
                sell_cap = E_LIMIT + pos

                bid_px = best_bid + 1   # 9993 (market bid 9992 + 1)
                ask_px = best_ask - 1   # 10007 (market ask 10008 - 1)

                bid_px = min(bid_px, best_ask - 1)
                ask_px = max(ask_px, best_bid + 1)

                if pos >= E_FLATTEN and sell_cap > 0:
                    fvol = min(E_FLATTEN_VOL, sell_cap, abs(od.buy_orders.get(best_bid, 0)))
                    if fvol > 0:
                        orders.append(Order("EMERALDS", best_bid, -fvol))
                        sell_cap -= fvol

                elif pos <= -E_FLATTEN and buy_cap > 0:
                    fvol = min(E_FLATTEN_VOL, buy_cap, abs(od.sell_orders.get(best_ask, 0)))
                    if fvol > 0:
                        orders.append(Order("EMERALDS", best_ask, fvol))
                        buy_cap -= fvol

                if bid_px < ask_px:
                    if buy_cap > 0:
                        orders.append(Order("EMERALDS", bid_px, buy_cap))
                    if sell_cap > 0:
                        orders.append(Order("EMERALDS", ask_px, -sell_cap))
                else:
                    if buy_cap > 0:
                        orders.append(Order("EMERALDS", best_bid, buy_cap))
                    if sell_cap > 0:
                        orders.append(Order("EMERALDS", best_ask, -sell_cap))

            result["EMERALDS"] = orders

        # ═════════════════════════════════════════════════════════════════════
        # TOMATOES — Z-Score Mean Reversion & Market Making (PASSIVE ONLY)
        # ═════════════════════════════════════════════════════════════════════
        if "TOMATOES" in state.order_depths:
            od  = state.order_depths["TOMATOES"]
            pos = state.position.get("TOMATOES", 0)
            orders: List[Order] = []

            best_bid = max(od.buy_orders.keys(),  default=None)
            best_ask = min(od.sell_orders.keys(), default=None)

            if best_bid is not None and best_ask is not None:
                buy_cap  = T_LIMIT - pos
                sell_cap = T_LIMIT + pos
                quote_buy = buy_cap
                quote_sell = sell_cap
                
                mid_price = (best_bid + best_ask) / 2.0
                history = s["TOMATOES_HISTORY"]
                history.append(mid_price)
                if len(history) > 10:
                    history.pop(0)
                
                s["TOMATOES_HISTORY"] = history
                
                z_score = 0.0
                if len(history) == 10:
                    mean = sum(history) / 10.0
                    variance = sum((x - mean) ** 2 for x in history) / 10.0
                    std = variance ** 0.5
                    if std > 0:
                        z_score = (mid_price - mean) / std

                # Default passive quotes
                bid_px = best_bid + 1
                ask_px = best_ask - 1

                # Z-Score Alpha Passive Quote Skewing
                # We do NOT cross the spread for these signals, as paying 13 ticks 
                # spread edge ruins PnL. We earn the spread instead.
                
                if z_score <= -1.5:
                    # Undervalued -> want to buy. Quote aggressive bid, defensive ask.
                    bid_px = best_ask - 1
                    ask_px = best_ask + 2
                
                elif z_score >= 1.5:
                    # Overvalued -> want to sell. Quote defensive bid, aggressive ask.
                    ask_px = best_bid + 1
                    bid_px = best_bid - 2
                    
                elif abs(z_score) <= 0.1:
                    # Mean Reverted -> exit positions if holding.
                    if pos > 0:
                        ask_px = best_bid + 1
                        bid_px = best_bid - 2
                    elif pos < 0:
                        bid_px = best_ask - 1
                        ask_px = best_ask + 2

                # Enforce safe pricing bounds so we don't accidentally hit the market
                bid_px = min(bid_px, best_ask - 1)
                ask_px = max(ask_px, best_bid + 1)

                # Hard flatten logic still crosses the spread as an absolute safety 
                # limit (same as 11.py to avoid breaching position limits)
                if pos >= T_FLATTEN and sell_cap > 0:
                    fvol = min(T_FLATTEN_VOL, sell_cap, abs(od.buy_orders.get(best_bid, 0)))
                    if fvol > 0:
                        orders.append(Order("TOMATOES", best_bid, -fvol))
                        sell_cap -= fvol
                        quote_sell -= fvol

                elif pos <= -T_FLATTEN and buy_cap > 0:
                    fvol = min(T_FLATTEN_VOL, buy_cap, abs(od.sell_orders.get(best_ask, 0)))
                    if fvol > 0:
                        orders.append(Order("TOMATOES", best_ask, fvol))
                        buy_cap -= fvol
                        quote_buy -= fvol

                # Post passive quotes 
                if bid_px < ask_px:
                    if quote_buy > 0:
                        orders.append(Order("TOMATOES", bid_px, quote_buy))
                    if quote_sell > 0:
                        orders.append(Order("TOMATOES", ask_px, -quote_sell))
                else:
                    if quote_buy > 0:
                        orders.append(Order("TOMATOES", best_bid, quote_buy))
                    if quote_sell > 0:
                        orders.append(Order("TOMATOES", best_ask, -quote_sell))

            result["TOMATOES"] = orders

            ## make sure these lines make it into your script while testing
            encoded_trader_data = jsonpickle.encode(s)

            # IMPORTANT: Add this line to format the data for the visualizer
            logger.flush(state, result, 0, encoded_trader_data)
        
            return result, 0, encoded_trader_data