from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import websockets
import json
import hmac
import hashlib
import time
import httpx
from decimal import Decimal
from typing import Dict, Optional, Any, List
from enum import Enum
import logging
import os
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MEXC Trading Bot", description="Automated trading bot for MEXC Exchange")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get('FRONTEND_URL', 'http://localhost:3000')],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enums and Data Classes
class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    LIMIT = "LIMIT"

class OrderStatus(str, Enum):
    NEW = "NEW"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"

@dataclass
class OrderBookEntry:
    price: Decimal
    quantity: Decimal

@dataclass
class OrderBook:
    symbol: str
    bids: List[OrderBookEntry] = None
    asks: List[OrderBookEntry] = None
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    best_bid_qty: Optional[Decimal] = None
    best_ask_qty: Optional[Decimal] = None

    def __post_init__(self):
        if self.bids is None:
            self.bids = []
        if self.asks is None:
            self.asks = []

# Enhanced Pydantic Models with Price Ranges
class TradingConfig(BaseModel):
    api_key: str
    secret_key: str
    symbol: str
    buy_quantity: float
    sell_quantity: float
    # NEW: Price range configuration
    buy_price_min: float  # Минимальная цена для покупки (например, 100)
    buy_price_max: float  # Максимальная цена для покупки (например, 102)
    sell_price_min: float  # Минимальная цена для продажи (например, 108) 
    sell_price_max: float  # Максимальная цена для продажи (например, 110)
    max_price_deviation: float = 0.05  # 5% max deviation from initial price
    min_competitor_size_usdt: float = 10.0  # Minimum competitor size to beat in USDT

class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    quantity: float
    price: float

# MEXC API Authentication
class MexcAuthenticator:
    def __init__(self, api_key: str, secret_key: str):
        # Clean up API keys by removing whitespace
        self.api_key = api_key.strip()
        self.secret_key = secret_key.strip().encode('utf-8')

    def generate_signature(self, method: str, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, str]:
        timestamp = int(time.time() * 1000)
        query_string = ""
        
        if params:
            filtered_params = {k: str(v) for k, v in params.items() if v is not None}
            query_string = "&".join([f"{k}={v}" for k, v in sorted(filtered_params.items())])
            
        if query_string:
            query_string += f"&timestamp={timestamp}"
        else:
            query_string = f"timestamp={timestamp}"

        signature = hmac.new(
            self.secret_key,
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        query_string += f"&signature={signature}"

        return {
            'X-MEXC-APIKEY': self.api_key,
            'timestamp': str(timestamp),
            'signature': signature,
            'query_string': query_string
        }

# Order Management
class OrderManager:
    def __init__(self, authenticator: MexcAuthenticator):
        self.authenticator = authenticator
        self.base_url = "https://api.mexc.com"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.active_orders: Dict[str, Dict] = {}

    async def place_order(self, symbol: str, side: OrderSide, quantity: float, price: float) -> Dict[str, Any]:
        try:
            params = {
                'symbol': symbol,
                'side': side.value,
                'type': OrderType.LIMIT.value,
                'quantity': str(quantity),
                'price': str(price)
            }

            auth_data = self.authenticator.generate_signature('POST', '/api/v3/order', params)
            
            response = await self.client.post(
                f"{self.base_url}/api/v3/order?{auth_data['query_string']}",
                headers={'X-MEXC-APIKEY': auth_data['X-MEXC-APIKEY']}
            )

            if response.status_code == 200:
                result = response.json()
                if 'orderId' in result:
                    self.active_orders[result['orderId']] = {
                        'symbol': symbol,
                        'side': side,
                        'quantity': quantity,
                        'price': price,
                        'order_id': result['orderId']
                    }
                    logger.info(f"Order placed: {result}")
                    return result
            else:
                logger.error(f"Order placement failed: {response.status_code} - {response.text}")
                raise HTTPException(status_code=400, detail=f"Order placement failed: {response.text}")

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        try:
            params = {
                'symbol': symbol,
                'orderId': order_id
            }

            auth_data = self.authenticator.generate_signature('DELETE', '/api/v3/order', params)
            
            response = await self.client.delete(
                f"{self.base_url}/api/v3/order?{auth_data['query_string']}",
                headers={'X-MEXC-APIKEY': auth_data['X-MEXC-APIKEY']}
            )

            if response.status_code == 200:
                result = response.json()
                if order_id in self.active_orders:
                    del self.active_orders[order_id]
                logger.info(f"Order canceled: {result}")
                return result
            else:
                logger.error(f"Order cancellation failed: {response.status_code} - {response.text}")
                raise HTTPException(status_code=400, detail=f"Order cancellation failed: {response.text}")

        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            raise HTTPException(status_code=500, detail=str(e))

# Enhanced WebSocket Order Book Monitor with Full Depth
class OrderBookMonitor:
    def __init__(self):
        self.order_books: Dict[str, OrderBook] = {}
        self.callbacks: List = []
        self.connection = None
        self.running = False

    async def connect(self):
        try:
            self.connection = await websockets.connect(
                'wss://wbs.mexc.com/ws',
                ping_interval=10,  # Increased frequency
                ping_timeout=5
            )
            self.running = True
            logger.info("WebSocket connected to MEXC")
            asyncio.create_task(self._process_messages())

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            raise

    async def subscribe_symbol(self, symbol: str):
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol=symbol)

        # Subscribe to both ticker and depth with correct MEXC format
        subscriptions = [
            {
                "method": "SUBSCRIPTION",
                "params": [f"spot@public.bookTicker.v3.api@{symbol}"]
            },
            {
                "method": "SUBSCRIPTION",
                "params": [f"spot@public.limit.depth.v3.api@{symbol}@20"]
            }
        ]

        if self.connection:
            for subscription in subscriptions:
                await self.connection.send(json.dumps(subscription))
                await asyncio.sleep(0.1)  # Small delay between subscriptions

            logger.info(f"Subscribed to ticker and depth for {symbol}")

    def add_callback(self, callback):
        self.callbacks.append(callback)

    async def _process_messages(self):
        try:
            async for message in self.connection:
                data = json.loads(message)
                await self._handle_message(data)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.running = False
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
            self.running = False

    async def _handle_message(self, message: dict):
        if 'c' in message and 'd' in message:
            channel = message['c']
            data = message['d']

            # Handle best bid/ask updates
            if 'bookTicker' in channel:
                parts = channel.split('@')
                if len(parts) >= 3:
                    symbol = parts[2]
                    if symbol in self.order_books:
                        order_book = self.order_books[symbol]
                        if 'b' in data and 'B' in data:
                            order_book.best_bid = Decimal(str(data['b']))
                            order_book.best_bid_qty = Decimal(str(data['B']))
                        if 'a' in data and 'A' in data:
                            order_book.best_ask = Decimal(str(data['a']))
                            order_book.best_ask_qty = Decimal(str(data['A']))

            # Handle full depth updates
            elif 'limit.depth' in channel:
                parts = channel.split('@')
                if len(parts) >= 3:
                    symbol = parts[3]
                    if symbol in self.order_books:
                        order_book = self.order_books[symbol]
                        
                        # Update bids and asks with full depth
                        if 'bids' in data:
                            order_book.bids = [
                                OrderBookEntry(Decimal(str(bid[0])), Decimal(str(bid[1])))
                                for bid in data['bids']
                            ]
                        if 'asks' in data:
                            order_book.asks = [
                                OrderBookEntry(Decimal(str(ask[0])), Decimal(str(ask[1])))
                                for ask in data['asks']
                            ]

            # Notify callbacks with higher frequency
            for callback in self.callbacks:
                try:
                    await callback(self.order_books.get(symbol))
                except Exception as e:
                    logger.error(f"Error in callback: {e}")

# Enhanced Trading Bot with Price Range Support
class TradingBot:
    def __init__(self, config: TradingConfig):
        self.config = config
        self.authenticator = MexcAuthenticator(config.api_key, config.secret_key)
        self.order_manager = OrderManager(self.authenticator)
        self.order_book_monitor = OrderBookMonitor()
        self.current_buy_order = None
        self.current_sell_order = None
        self.running = False
        self.initial_price = None
        self.update_frequency = 0.1  # 100ms update frequency for aggressive trading

        # NEW: Convert price ranges to Decimal for precise calculations
        self.buy_range_min = Decimal(str(config.buy_price_min))
        self.buy_range_max = Decimal(str(config.buy_price_max))
        self.sell_range_min = Decimal(str(config.sell_price_min))
        self.sell_range_max = Decimal(str(config.sell_price_max))

    async def start(self):
        self.running = True
        await self.order_book_monitor.connect()
        await self.order_book_monitor.subscribe_symbol(self.config.symbol)
        self.order_book_monitor.add_callback(self._on_order_book_update)
        
        # Start aggressive monitoring loop
        asyncio.create_task(self._aggressive_monitoring_loop())
        
        logger.info(f"Trading bot started for {self.config.symbol} with price ranges: "
                   f"Buy {self.buy_range_min}-{self.buy_range_max}, "
                   f"Sell {self.sell_range_min}-{self.sell_range_max}")

    async def stop(self):
        self.running = False
        
        # Cancel active orders
        if self.current_buy_order:
            try:
                await self.order_manager.cancel_order(self.config.symbol, self.current_buy_order['orderId'])
            except:
                pass
                
        if self.current_sell_order:
            try:
                await self.order_manager.cancel_order(self.config.symbol, self.current_sell_order['orderId'])
            except:
                pass
                
        logger.info("Trading bot stopped")

    async def _aggressive_monitoring_loop(self):
        """High-frequency monitoring for aggressive competition beating within price ranges"""
        while self.running:
            try:
                symbol = self.config.symbol
                if symbol in self.order_book_monitor.order_books:
                    order_book = self.order_book_monitor.order_books[symbol]
                    await self._aggressive_update_orders(order_book)
                
                await asyncio.sleep(self.update_frequency)  # 100ms updates
                
            except Exception as e:
                logger.error(f"Error in aggressive monitoring: {e}")
                await asyncio.sleep(1)

    async def _on_order_book_update(self, order_book: OrderBook):
        if not self.running or not order_book or not order_book.best_bid or not order_book.best_ask:
            return

        # Set initial price reference
        if self.initial_price is None:
            mid_price = (order_book.best_bid + order_book.best_ask) / 2
            self.initial_price = mid_price

    async def _aggressive_update_orders(self, order_book: OrderBook):
        if not order_book or not order_book.best_bid or not order_book.best_ask:
            return

        try:
            # Aggressive buy order updates within range
            await self._update_range_based_buy_order(order_book)
            
            # Aggressive sell order updates within range  
            await self._update_range_based_sell_order(order_book)
            
        except Exception as e:
            logger.error(f"Error in aggressive order updates: {e}")

    def _should_beat_competitor(self, competitor_price: Decimal, competitor_quantity: Decimal) -> bool:
        """Check if competitor order is large enough to warrant beating"""
        competitor_value_usdt = float(competitor_price * competitor_quantity)
        min_size = self.config.min_competitor_size_usdt
        should_beat = competitor_value_usdt >= min_size
        
        logger.info(f"Competitor: {competitor_price} x {competitor_quantity} = ${competitor_value_usdt:.2f}, "
                   f"Min size: ${min_size}, Should beat: {should_beat}")
        return should_beat

    async def _update_range_based_buy_order(self, order_book: OrderBook):
        """Update buy order within the specified price range, beating competitors when necessary"""
        
        # Start with the best bid, but ensure it's within our buy range
        baseline_price = order_book.best_bid
        
        # Clamp baseline to our buy range
        if baseline_price < self.buy_range_min:
            target_price = self.buy_range_min
        elif baseline_price > self.buy_range_max:
            target_price = self.buy_range_max
        else:
            target_price = baseline_price + Decimal('0.00001')  # Just above best bid

        # If we have a current order, check for competitors above it within our range
        if self.current_buy_order:
            our_price = Decimal(str(self.current_buy_order.get('price', 0)))
            
            # Check if there are large enough orders above us that we should beat (within range)
            found_large_competitor = False
            if order_book.bids and len(order_book.bids) > 0:
                # Find competitors above our price that are worth beating and within our range
                for bid in order_book.bids:
                    if (bid.price > our_price and 
                        bid.price <= self.buy_range_max and  # NEW: Within our range
                        bid.price >= self.buy_range_min):
                        
                        # Check if this competitor is large enough to beat
                        if self._should_beat_competitor(bid.price, bid.quantity):
                            # Beat this large competitor by 0.005%, but stay within range
                            beat_margin = Decimal('1.00005')
                            potential_price = bid.price * beat_margin
                            
                            # Ensure we don't exceed our buy range
                            if potential_price <= self.buy_range_max:
                                target_price = potential_price
                                logger.info(f"Beating large buy competitor at {bid.price} "
                                          f"(${float(bid.price * bid.quantity):.2f}) with {target_price} "
                                          f"(within range {self.buy_range_min}-{self.buy_range_max})")
                                found_large_competitor = True
                                break
                            else:
                                # Competitor is too high, stay at range max
                                target_price = self.buy_range_max
                                logger.info(f"Competitor at {bid.price} would exceed buy range, "
                                          f"setting to max: {target_price}")
                                found_large_competitor = True
                                break
                        else:
                            logger.info(f"Ignoring small buy competitor at {bid.price} "
                                      f"(${float(bid.price * bid.quantity):.2f}) - too small")

            # If no large competitors found, maintain position based on best bid but within range
            if not found_large_competitor:
                if our_price < order_book.best_bid and order_book.best_bid <= self.buy_range_max:
                    target_price = min(order_book.best_bid + Decimal('0.00001'), self.buy_range_max)
                    logger.info(f"No large competitors, updating to stay above best bid: {target_price} "
                              f"(within range {self.buy_range_min}-{self.buy_range_max})")
                else:
                    # We're already in good position within range, no need to update
                    return

        # Ensure target price is within our specified buy range
        target_price = max(self.buy_range_min, min(target_price, self.buy_range_max))

        # Check if we need to update (more aggressive - update more frequently)
        should_update = False
        if self.current_buy_order is None:
            should_update = True
        else:
            current_price = Decimal(str(self.current_buy_order.get('price', 0)))
            
            # More aggressive threshold for updates
            price_diff = abs(target_price - current_price)
            if price_diff > Decimal('0.000005'):  # Even smaller threshold
                should_update = True
                logger.info(f"Price diff {price_diff} > threshold, updating buy order")

        if should_update:
            # Cancel existing order
            if self.current_buy_order:
                try:
                    await self.order_manager.cancel_order(self.config.symbol, self.current_buy_order['orderId'])
                    self.current_buy_order = None
                except Exception as e:
                    logger.error(f"Error canceling buy order: {e}")

            # Place new range-based order
            try:
                result = await self.order_manager.place_order(
                    self.config.symbol,
                    OrderSide.BUY,
                    self.config.buy_quantity,
                    float(target_price)
                )
                self.current_buy_order = result
                logger.info(f"Range-based buy order placed at {target_price} "
                          f"(range: {self.buy_range_min}-{self.buy_range_max})")
                
            except Exception as e:
                logger.error(f"Error placing range-based buy order: {e}")

    async def _update_range_based_sell_order(self, order_book: OrderBook):
        """Update sell order within the specified price range, beating competitors when necessary"""
        
        # Skip sell orders if we don't have a filled buy order to prevent "Oversold" errors
        if not self.current_buy_order:
            return

        # Start with the best ask, but ensure it's within our sell range
        baseline_price = order_book.best_ask
        
        # Clamp baseline to our sell range
        if baseline_price > self.sell_range_max:
            target_price = self.sell_range_max
        elif baseline_price < self.sell_range_min:
            target_price = self.sell_range_min
        else:
            target_price = baseline_price - Decimal('0.00001')  # Just below best ask

        # If we have a current order, check for competitors below it within our range
        if self.current_sell_order:
            our_price = Decimal(str(self.current_sell_order.get('price', 0)))
            
            # Check if there are large enough orders below us that we should beat (within range)
            found_large_competitor = False
            if order_book.asks and len(order_book.asks) > 0:
                # Find competitors below our price that are worth beating and within our range
                for ask in order_book.asks:
                    if (ask.price < our_price and 
                        ask.price >= self.sell_range_min and  # NEW: Within our range
                        ask.price <= self.sell_range_max):
                        
                        # Check if this competitor is large enough to beat
                        if self._should_beat_competitor(ask.price, ask.quantity):
                            # Beat this large competitor by 0.005%, but stay within range
                            beat_margin = Decimal('0.99995')  # Slightly lower for sell
                            potential_price = ask.price * beat_margin
                            
                            # Ensure we don't go below our sell range
                            if potential_price >= self.sell_range_min:
                                target_price = potential_price
                                logger.info(f"Beating large sell competitor at {ask.price} "
                                          f"(${float(ask.price * ask.quantity):.2f}) with {target_price} "
                                          f"(within range {self.sell_range_min}-{self.sell_range_max})")
                                found_large_competitor = True
                                break
                            else:
                                # Competitor is too low, stay at range min
                                target_price = self.sell_range_min
                                logger.info(f"Competitor at {ask.price} would go below sell range, "
                                          f"setting to min: {target_price}")
                                found_large_competitor = True
                                break
                        else:
                            logger.info(f"Ignoring small sell competitor at {ask.price} "
                                      f"(${float(ask.price * ask.quantity):.2f}) - too small")

            # If no large competitors found, maintain position based on best ask but within range
            if not found_large_competitor:
                if our_price > order_book.best_ask and order_book.best_ask >= self.sell_range_min:
                    target_price = max(order_book.best_ask - Decimal('0.00001'), self.sell_range_min)
                    logger.info(f"No large competitors, updating to stay below best ask: {target_price} "
                              f"(within range {self.sell_range_min}-{self.sell_range_max})")
                else:
                    # We're already in good position within range, no need to update
                    return
        else:
            # No current order, place within our sell range below best ask
            target_price = max(baseline_price - Decimal('0.00001'), self.sell_range_min)

        # Ensure target price is within our specified sell range
        target_price = max(self.sell_range_min, min(target_price, self.sell_range_max))

        # Check if we need to update
        should_update = False
        if self.current_sell_order is None:
            should_update = True
        else:
            current_price = Decimal(str(self.current_sell_order.get('price', 0)))
            
            # Update if price difference is significant (more aggressive threshold)
            if abs(target_price - current_price) > Decimal('0.000005'):
                should_update = True

        if should_update:
            # Cancel existing order
            if self.current_sell_order:
                try:
                    await self.order_manager.cancel_order(self.config.symbol, self.current_sell_order['orderId'])
                    self.current_sell_order = None
                except Exception as e:
                    logger.error(f"Error canceling sell order: {e}")

            # Place new range-based order
            try:
                result = await self.order_manager.place_order(
                    self.config.symbol,
                    OrderSide.SELL,
                    self.config.sell_quantity,
                    float(target_price)
                )
                self.current_sell_order = result
                logger.info(f"Range-based sell order placed at {target_price} "
                          f"(range: {self.sell_range_min}-{self.sell_range_max})")
                
            except Exception as e:
                logger.error(f"Error placing range-based sell order: {e}")
                # If oversold error, skip sell orders for a while
                if "Oversold" in str(e) or "30005" in str(e):
                    logger.info("Skipping sell orders due to insufficient balance")

# Global bot instance
trading_bot = None

# API Endpoints
@app.post("/api/start-bot")
async def start_bot(config: TradingConfig):
    global trading_bot
    
    try:
        # Validate price ranges
        if config.buy_price_min >= config.buy_price_max:
            raise HTTPException(status_code=400, detail="buy_price_min должен быть меньше buy_price_max")
        if config.sell_price_min >= config.sell_price_max:
            raise HTTPException(status_code=400, detail="sell_price_min должен быть меньше sell_price_max")
        if config.buy_price_max >= config.sell_price_min:
            raise HTTPException(status_code=400, detail="Диапазон покупки не должен пересекаться с диапазоном продажи")
            
        if trading_bot and trading_bot.running:
            await trading_bot.stop()
            
        trading_bot = TradingBot(config)
        await trading_bot.start()
        
        return {
            "status": "success", 
            "message": f"Range-based trading bot started for {config.symbol}",
            "buy_range": f"{config.buy_price_min}-{config.buy_price_max}",
            "sell_range": f"{config.sell_price_min}-{config.sell_price_max}"
        }
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stop-bot")
async def stop_bot():
    global trading_bot
    
    try:
        if trading_bot:
            await trading_bot.stop()
            trading_bot = None
        return {"status": "success", "message": "Trading bot stopped"}
        
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bot-status")
async def get_bot_status():
    global trading_bot
    
    if not trading_bot:
        return {"running": False, "message": "Bot not initialized"}

    status = {
        "running": trading_bot.running,
        "symbol": trading_bot.config.symbol,
        "current_buy_order": trading_bot.current_buy_order,
        "current_sell_order": trading_bot.current_sell_order,
        "initial_price": str(trading_bot.initial_price) if trading_bot.initial_price else None,
        "update_frequency": f"{trading_bot.update_frequency}s",
        "min_competitor_size_usdt": trading_bot.config.min_competitor_size_usdt,
        # NEW: Price range information
        "buy_range": {
            "min": str(trading_bot.buy_range_min),
            "max": str(trading_bot.buy_range_max)
        },
        "sell_range": {
            "min": str(trading_bot.sell_range_min),
            "max": str(trading_bot.sell_range_max)
        }
    }

    if trading_bot.config.symbol in trading_bot.order_book_monitor.order_books:
        order_book = trading_bot.order_book_monitor.order_books[trading_bot.config.symbol]
        status.update({
            "best_bid": str(order_book.best_bid) if order_book.best_bid else None,
            "best_ask": str(order_book.best_ask) if order_book.best_ask else None,
            "spread": str(order_book.best_ask - order_book.best_bid) if order_book.best_ask and order_book.best_bid else None,
            "orderbook_depth": {
                "bids_count": len(order_book.bids),
                "asks_count": len(order_book.asks)
            }
        })

    return status

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "message": "MEXC Range-based Trading Bot API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)