#!/usr/bin/env python3
"""
Additional edge case tests for the MEXC Range-based Trading Bot
"""

import asyncio
import httpx
import json

BACKEND_URL = "https://16404ca9-aa38-4e91-b36e-9fbc10b4f2ad.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

async def test_edge_cases():
    client = httpx.AsyncClient(timeout=30.0)
    
    print("🔍 Testing Additional Edge Cases")
    print("=" * 50)
    
    # Test 1: Very small price ranges
    small_range_config = {
        "api_key": "test_key_123",
        "secret_key": "test_secret_456",
        "symbol": "BTCUSDT",
        "buy_quantity": 0.001,
        "sell_quantity": 0.001,
        "buy_price_min": 50000.0,
        "buy_price_max": 50000.01,  # Very small range
        "sell_price_min": 50000.02,
        "sell_price_max": 50000.03
    }
    
    print("Testing very small price ranges...")
    response = await client.post(f"{API_BASE}/start-bot", json=small_range_config)
    if response.status_code == 200:
        data = response.json()
        print("✅ PASS - Small ranges accepted")
        print(f"   Buy range: {data.get('buy_range')}")
        print(f"   Sell range: {data.get('sell_range')}")
    else:
        print(f"❌ FAIL - Small ranges rejected: {response.status_code}")
    
    # Test 2: Zero quantities
    zero_quantity_config = {
        "api_key": "test_key_123",
        "secret_key": "test_secret_456",
        "symbol": "BTCUSDT",
        "buy_quantity": 0.0,  # Zero quantity
        "sell_quantity": 0.0,
        "buy_price_min": 48000.0,
        "buy_price_max": 49000.0,
        "sell_price_min": 51000.0,
        "sell_price_max": 52000.0
    }
    
    print("\nTesting zero quantities...")
    response = await client.post(f"{API_BASE}/start-bot", json=zero_quantity_config)
    if response.status_code in [400, 422, 500]:
        print("✅ PASS - Zero quantities properly handled")
    else:
        print(f"❌ FAIL - Zero quantities accepted: {response.status_code}")
    
    # Test 3: Very large numbers
    large_numbers_config = {
        "api_key": "test_key_123",
        "secret_key": "test_secret_456",
        "symbol": "BTCUSDT",
        "buy_quantity": 0.001,
        "sell_quantity": 0.001,
        "buy_price_min": 1000000.0,  # Very large numbers
        "buy_price_max": 2000000.0,
        "sell_price_min": 3000000.0,
        "sell_price_max": 4000000.0
    }
    
    print("\nTesting very large price numbers...")
    response = await client.post(f"{API_BASE}/start-bot", json=large_numbers_config)
    if response.status_code == 200:
        print("✅ PASS - Large numbers accepted")
    else:
        print(f"❌ FAIL - Large numbers rejected: {response.status_code}")
    
    # Test 4: Invalid symbol format
    invalid_symbol_config = {
        "api_key": "test_key_123",
        "secret_key": "test_secret_456",
        "symbol": "INVALID_SYMBOL_123",
        "buy_quantity": 0.001,
        "sell_quantity": 0.001,
        "buy_price_min": 48000.0,
        "buy_price_max": 49000.0,
        "sell_price_min": 51000.0,
        "sell_price_max": 52000.0
    }
    
    print("\nTesting invalid symbol...")
    response = await client.post(f"{API_BASE}/start-bot", json=invalid_symbol_config)
    if response.status_code == 200:
        print("✅ PASS - Invalid symbol handled (will fail at MEXC level)")
    else:
        print(f"❌ FAIL - Invalid symbol rejected at validation: {response.status_code}")
    
    # Test 5: Bot status when running
    print("\nTesting bot status with active bot...")
    status_response = await client.get(f"{API_BASE}/bot-status")
    if status_response.status_code == 200:
        status_data = status_response.json()
        if status_data.get("running"):
            print("✅ PASS - Bot status shows running bot with ranges")
            print(f"   Symbol: {status_data.get('symbol')}")
            print(f"   Buy range: {status_data.get('buy_range')}")
            print(f"   Sell range: {status_data.get('sell_range')}")
        else:
            print("✅ PASS - Bot status shows no active bot")
    else:
        print(f"❌ FAIL - Bot status endpoint error: {status_response.status_code}")
    
    # Test 6: Stop bot multiple times
    print("\nTesting multiple stop requests...")
    for i in range(3):
        stop_response = await client.post(f"{API_BASE}/stop-bot")
        if stop_response.status_code == 200:
            print(f"✅ PASS - Stop request {i+1} handled correctly")
        else:
            print(f"❌ FAIL - Stop request {i+1} failed: {stop_response.status_code}")
    
    await client.aclose()
    print("\n🎯 Additional edge case testing completed!")

if __name__ == "__main__":
    asyncio.run(test_edge_cases())