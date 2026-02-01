#!/usr/bin/env python3
"""
Phase 4 Integration Test Script

Tests the complete slug resolution flow:
1. Agent connects via tunnel_id
2. HTTP request comes in with slug
3. Edge resolves slug → tunnel_id via Control Plane
4. Request routed through tunnel
5. Response returned

Prerequisites:
- Redis running on localhost:6379
- Mock Control Plane running on localhost:8000
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
TUNNEL_ID = "tunnel_test123"
SLUG = "my-slug"


async def test_agent_simulation():
    """Simulates an agent connecting and responding to requests."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔌 Agent connecting to {EDGE_WS_URL}/ws/{TUNNEL_ID}")
    
    async with websockets.connect(f"{EDGE_WS_URL}/ws/{TUNNEL_ID}") as ws:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Agent connected (tunnel_id={TUNNEL_ID})")
        
        # Handle one request then close
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
                    "message": "Hello from Phase 4!",
                    "tunnel_id": TUNNEL_ID,
                    "path": data["path"]
                }
            }
            
            await ws.send(json.dumps(response))
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📤 Agent sent response")


async def test_http_request():
    """Tests HTTP request through tunnel using slug."""
    await asyncio.sleep(1)  # Give agent time to connect
    
    url = f"{EDGE_GATEWAY_URL}/local_tunnel/{SLUG}/api/test"
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🌐 Making HTTP request to {url}")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 Response status: {response.status_code}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📄 Response body: {response.json()}")
        
        if response.status_code == 200:
            print(f"\n✅ Phase 4 test PASSED!")
        else:
            print(f"\n❌ Phase 4 test FAILED!")


async def verify_prerequisites():
    """Verify all required services are running."""
    print("🔍 Verifying prerequisites...\n")
    
    # Check Control Plane
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{CONTROL_PLANE_URL}/health", timeout=2.0)
            if resp.status_code == 200:
                print(f"✅ Control Plane running at {CONTROL_PLANE_URL}")
            else:
                print(f"❌ Control Plane returned {resp.status_code}")
                return False
    except Exception as e:
        print(f"❌ Control Plane not reachable: {e}")
        print(f"   Start with: python mock_control_plane.py")
        return False
    
    # Check Edge Gateway
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{EDGE_GATEWAY_URL}/health/live", timeout=2.0)
            if resp.status_code == 200:
                print(f"✅ Edge Gateway running at {EDGE_GATEWAY_URL}")
            else:
                print(f"❌ Edge Gateway returned {resp.status_code}")
                return False
    except Exception as e:
        print(f"❌ Edge Gateway not reachable: {e}")
        print(f"   Start with: uvicorn app.main:app --host 0.0.0.0 --port 8080")
        return False
    
    # Check slug resolution endpoint
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{CONTROL_PLANE_URL}/api/tunnels/resolve/{SLUG}", timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ Slug '{SLUG}' resolves to tunnel_id='{data.get('tunnel_id')}'")
            else:
                print(f"❌ Slug resolution failed: {resp.status_code}")
                return False
    except Exception as e:
        print(f"❌ Slug resolution error: {e}")
        return False
    
    print("\n" + "="*60)
    return True


async def main():
    """Run the complete test."""
    print("\n🧪 Phase 4 Integration Test\n")
    
    if not await verify_prerequisites():
        print("\n❌ Prerequisites not met. Please start required services.\n")
        return
    
    print("\n▶️  Starting test...\n")
    
    # Run agent and HTTP request concurrently
    await asyncio.gather(
        test_agent_simulation(),
        test_http_request()
    )
    
    print("\n" + "="*60)
    print("\n📋 What just happened:")
    print("1. Agent connected to Edge via tunnel_id")
    print("2. HTTP request sent to Edge with slug")
    print("3. Edge resolved slug → tunnel_id via Control Plane")
    print("4. Edge cached the result in Redis")
    print("5. Request routed through tunnel")
    print("6. Response returned to client\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
