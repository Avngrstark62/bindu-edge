#!/usr/bin/env python3
"""
Phase 5 Integration Test Script

Tests tunnel validation on WebSocket connect:
1. Agent connects with valid token → accepted
2. Agent connects with invalid token → rejected
3. Agent connects with missing token → rejected
4. Agent connects with expired/revoked tunnel → rejected
5. Full flow: connect with valid token, serve HTTP request

Prerequisites:
- Redis running on localhost:6379
- Mock Control Plane running on localhost:8000 (with Phase 5 endpoints)
- Edge Gateway running on localhost:8080
"""
import asyncio
import httpx
import json
import websockets
from datetime import datetime

# Test configuration
CONTROL_PLANE_URL = "http://localhost:8000"
EDGE_GATEWAY_URL = "http://localhost:8080"
EDGE_WS_URL = "ws://localhost:8080"


async def test_valid_token():
    """Test 1: Agent connects with valid token - should succeed."""
    print(f"\n{'='*60}")
    print("TEST 1: Valid Token Connection")
    print(f"{'='*60}")
    
    tunnel_id = "tunnel_test123"
    token = "valid_token_123"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔌 Attempting connection with valid token...")
    
    try:
        async with websockets.connect(
            f"{EDGE_WS_URL}/ws/{tunnel_id}",
            additional_headers={"X-Tunnel-Token": token}
        ) as ws:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Connection ACCEPTED (as expected)")
            
            # Send a ping to verify connection works
            await ws.send(json.dumps({"type": "ping"}))
            response = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(response)
            
            if data["type"] == "pong":
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Ping/Pong successful")
            
            return True
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Connection REJECTED (unexpected): {e}")
        return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {e}")
        return False


async def test_invalid_token():
    """Test 2: Agent connects with invalid token - should be rejected."""
    print(f"\n{'='*60}")
    print("TEST 2: Invalid Token Connection")
    print(f"{'='*60}")
    
    tunnel_id = "tunnel_test123"
    token = "wrong_token"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔌 Attempting connection with invalid token...")
    
    try:
        async with websockets.connect(
            f"{EDGE_WS_URL}/ws/{tunnel_id}",
            additional_headers={"X-Tunnel-Token": token}
        ) as ws:
            # Connection opened, but it should be closed immediately
            # Try to receive a message - should get ConnectionClosedError
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Connection ACCEPTED (unexpected - should be rejected)")
                return False
            except websockets.exceptions.ConnectionClosedError as e:
                if e.code == 1008:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Connection REJECTED (as expected): {e.reason}")
                    return True
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Connection rejected with unexpected code {e.code}: {e}")
                    return False
    except websockets.exceptions.ConnectionClosedError as e:
        if e.code == 1008:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Connection REJECTED (as expected): {e.reason}")
            return True
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Connection rejected with unexpected code {e.code}: {e}")
            return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Unexpected error: {e}")
        return False


async def test_missing_token():
    """Test 3: Agent connects without token - should be rejected."""
    print(f"\n{'='*60}")
    print("TEST 3: Missing Token Connection")
    print(f"{'='*60}")
    
    tunnel_id = "tunnel_test123"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔌 Attempting connection without token...")
    
    try:
        async with websockets.connect(
            f"{EDGE_WS_URL}/ws/{tunnel_id}"
        ) as ws:
            # Connection opened, but it should be closed immediately
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Connection ACCEPTED (unexpected - should be rejected)")
                return False
            except websockets.exceptions.ConnectionClosedError as e:
                if e.code == 1008:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Connection REJECTED (as expected): {e.reason}")
                    return True
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Connection rejected with unexpected code {e.code}: {e}")
                    return False
    except websockets.exceptions.ConnectionClosedError as e:
        if e.code == 1008:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Connection REJECTED (as expected): {e.reason}")
            return True
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Connection rejected with unexpected code {e.code}: {e}")
            return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Unexpected error: {e}")
        return False


async def test_expired_tunnel():
    """Test 4: Agent connects with expired tunnel - should be rejected."""
    print(f"\n{'='*60}")
    print("TEST 4: Expired Tunnel Connection")
    print(f"{'='*60}")
    
    tunnel_id = "tunnel_expired"
    token = "expired_token"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔌 Attempting connection with expired tunnel...")
    
    try:
        async with websockets.connect(
            f"{EDGE_WS_URL}/ws/{tunnel_id}",
            additional_headers={"X-Tunnel-Token": token}
        ) as ws:
            # Connection opened, but it should be closed immediately
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Connection ACCEPTED (unexpected - should be rejected)")
                return False
            except websockets.exceptions.ConnectionClosedError as e:
                if e.code == 1008:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Connection REJECTED (as expected): {e.reason}")
                    return True
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Connection rejected with unexpected code {e.code}: {e}")
                    return False
    except websockets.exceptions.ConnectionClosedError as e:
        if e.code == 1008:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Connection REJECTED (as expected): {e.reason}")
            return True
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Connection rejected with unexpected code {e.code}: {e}")
            return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Unexpected error: {e}")
        return False


async def test_revoked_tunnel():
    """Test 5: Agent connects with revoked tunnel - should be rejected."""
    print(f"\n{'='*60}")
    print("TEST 5: Revoked Tunnel Connection")
    print(f"{'='*60}")
    
    tunnel_id = "tunnel_revoked"
    token = "revoked_token"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔌 Attempting connection with revoked tunnel...")
    
    try:
        async with websockets.connect(
            f"{EDGE_WS_URL}/ws/{tunnel_id}",
            additional_headers={"X-Tunnel-Token": token}
        ) as ws:
            # Connection opened, but it should be closed immediately
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Connection ACCEPTED (unexpected - should be rejected)")
                return False
            except websockets.exceptions.ConnectionClosedError as e:
                if e.code == 1008:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Connection REJECTED (as expected): {e.reason}")
                    return True
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Connection rejected with unexpected code {e.code}: {e}")
                    return False
    except websockets.exceptions.ConnectionClosedError as e:
        if e.code == 1008:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Connection REJECTED (as expected): {e.reason}")
            return True
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Connection rejected with unexpected code {e.code}: {e}")
            return False
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  Unexpected error: {e}")
        return False


async def test_full_flow():
    """Test 6: Full end-to-end flow with validation."""
    print(f"\n{'='*60}")
    print("TEST 6: Full End-to-End Flow with Validation")
    print(f"{'='*60}")
    
    tunnel_id = "tunnel_test123"
    token = "valid_token_123"
    slug = "my-slug"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔌 Connecting agent with valid token...")
    
    try:
        async with websockets.connect(
            f"{EDGE_WS_URL}/ws/{tunnel_id}",
            additional_headers={"X-Tunnel-Token": token}
        ) as ws:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Agent connected")
            
            # Start agent handler in background
            async def agent_handler():
                while True:
                    try:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        if data["type"] == "request":
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📨 Agent received: {data['method']} {data['path']}")
                            
                            response = {
                                "type": "response",
                                "request_id": data["request_id"],
                                "status": 200,
                                "headers": {"Content-Type": "application/json"},
                                "body": {
                                    "message": "Hello from validated agent!",
                                    "tunnel_id": tunnel_id,
                                    "path": data["path"]
                                }
                            }
                            
                            await ws.send(json.dumps(response))
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📤 Agent sent response")
                            break
                        elif data["type"] == "ping":
                            await ws.send(json.dumps({"type": "pong"}))
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Agent error: {e}")
                        break
            
            handler_task = asyncio.create_task(agent_handler())
            
            # Give agent a moment to stabilize
            await asyncio.sleep(0.5)
            
            # Make HTTP request
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌐 Making HTTP request to /local_tunnel/{slug}/test")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{EDGE_GATEWAY_URL}/local_tunnel/{slug}/test",
                    timeout=10.0
                )
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 HTTP Response: {response.status_code}")
                
                if response.status_code == 200:
                    body = response.json()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📄 Response body: {json.dumps(body, indent=2)}")
                    
                    if body.get("tunnel_id") == tunnel_id:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Full flow successful!")
                        handler_task.cancel()
                        return True
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Unexpected status code")
            
            handler_task.cancel()
            return False
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Full flow failed: {e}")
        return False


async def main():
    """Run all Phase 5 tests."""
    print("\n" + "="*60)
    print("PHASE 5 INTEGRATION TESTS")
    print("Tunnel Validation on WebSocket Connect")
    print("="*60)
    
    results = {}
    
    # Run tests
    results["valid_token"] = await test_valid_token()
    await asyncio.sleep(0.5)
    
    results["invalid_token"] = await test_invalid_token()
    await asyncio.sleep(0.5)
    
    results["missing_token"] = await test_missing_token()
    await asyncio.sleep(0.5)
    
    results["expired_tunnel"] = await test_expired_tunnel()
    await asyncio.sleep(0.5)
    
    results["revoked_tunnel"] = await test_revoked_tunnel()
    await asyncio.sleep(0.5)
    
    results["full_flow"] = await test_full_flow()
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20s} {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All Phase 5 tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
