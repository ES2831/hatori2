#!/usr/bin/env python3
"""
Debug validation issues in the backend
"""

import asyncio
import httpx
import json

BACKEND_URL = "https://16404ca9-aa38-4e91-b36e-9fbc10b4f2ad.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

async def debug_validation():
    client = httpx.AsyncClient(timeout=30.0)
    
    # Test invalid buy range
    test_config = {
        "api_key": "test_key_123",
        "secret_key": "test_secret_456", 
        "symbol": "BTCUSDT",
        "buy_quantity": 0.001,
        "sell_quantity": 0.001,
        "buy_price_min": 50000.0,
        "buy_price_max": 49000.0,  # Invalid: max < min
        "sell_price_min": 52000.0,
        "sell_price_max": 53000.0
    }
    
    print("Testing invalid buy range validation...")
    response = await client.post(f"{API_BASE}/start-bot", json=test_config)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    # Test negative price
    negative_config = {
        "api_key": "test_key_123",
        "secret_key": "test_secret_456",
        "symbol": "BTCUSDT",
        "buy_quantity": 0.001,
        "sell_quantity": 0.001,
        "buy_price_min": -100.0,  # Negative price
        "buy_price_max": 49000.0,
        "sell_price_min": 51000.0,
        "sell_price_max": 52000.0
    }
    
    print("\nTesting negative price validation...")
    response = await client.post(f"{API_BASE}/start-bot", json=negative_config)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(debug_validation())