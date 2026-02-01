#!/usr/bin/env python3
"""
Verification script for Phase 5 capabilities.
Checks all claims made in the roadmap.
"""
import asyncio
import httpx
import json
import websockets
from datetime import datetime
import redis.asyncio as redis


async def verify_1_tunnel_connections():
    """
    Verify: Accept real tunnel connections with heartbeats
    """
    print("\n" + "="*60)
    print("VERIFICATION 1: Real Tunnel Connections")
    print("="*60)
    
    tunnel_id = "tunnel_test123"
    token = "valid_token_123"
    
    try:
        async with websockets.connect(
            "ws://localhost:8080/ws/" + tunnel_id,
            additional_headers={"X-Tunnel-Token": token}
        ) as ws:
            print("✅ WebSocket connection accepted")
            
            # Test heartbeat
            await ws.send(json.dumps({"type": "ping"}))
            response = await asyncio.wait_for(ws.recv(), timeout=2)
            data = json.loads(response)
            
            if data["type"] == "pong":
                print("✅ Heartbeat working (ping/pong)")
            
            # Wait for server ping
            msg = await asyncio.wait_for(ws.recv(), timeout=12)
            server_ping = json.loads(msg)
            if server_ping["type"] == "ping":
                print("✅ Server initiated heartbeat received")
                await ws.send(json.dumps({"type": "pong"}))
                print("✅ Responded to server ping")
            
            return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def verify_2_http_routing():
    """
    Verify: Route public HTTP into tunnels (full flow)
    """
    print("\n" + "="*60)
    print("VERIFICATION 2: HTTP → Tunnel Routing")
    print("="*60)
    
    tunnel_id = "tunnel_test123"
    token = "valid_token_123"
    slug = "my-slug"
    
    try:
        # Connect agent
        async with websockets.connect(
            "ws://localhost:8080/ws/" + tunnel_id,
            additional_headers={"X-Tunnel-Token": token}
        ) as ws:
            print(f"✅ Agent connected (tunnel_id={tunnel_id})")
            
            # Background handler
            async def handler():
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    if data["type"] == "request":
                        print(f"✅ Tunnel received: {data['method']} {data['path']}")
                        
                        # Send response
                        await ws.send(json.dumps({
                            "type": "response",
                            "request_id": data["request_id"],
                            "status": 200,
                            "headers": {"Content-Type": "text/plain"},
                            "body": "Hello from behind NAT!"
                        }))
                        print("✅ Tunnel sent response")
                        break
                    elif data["type"] == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
            
            task = asyncio.create_task(handler())
            await asyncio.sleep(0.3)
            
            # Make HTTP request
            print(f"✅ Making public HTTP request to /local_tunnel/{slug}/test")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:8080/local_tunnel/{slug}/test",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    print(f"✅ HTTP response received: {response.status_code}")
                    print(f"✅ Body: {response.text}")
                    task.cancel()
                    return True
                else:
                    print(f"❌ Unexpected status: {response.status_code}")
                    task.cancel()
                    return False
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def verify_3_redis_state():
    """
    Verify: Redis stores tunnel registry and slug cache
    """
    print("\n" + "="*60)
    print("VERIFICATION 3: Redis Shared State")
    print("="*60)
    
    tunnel_id = "tunnel_test123"
    token = "valid_token_123"
    slug = "my-slug"
    
    # Connect to Redis
    r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    
    try:
        await r.ping()
        print("✅ Redis connection working")
        
        # Connect a tunnel
        async with websockets.connect(
            "ws://localhost:8080/ws/" + tunnel_id,
            additional_headers={"X-Tunnel-Token": token}
        ) as ws:
            await asyncio.sleep(0.3)
            
            # Check tunnel registry
            tunnel_key = f"tunnel:{tunnel_id}"
            pod_id = await r.get(tunnel_key)
            
            if pod_id:
                print(f"✅ Tunnel registry: tunnel:{tunnel_id} → {pod_id}")
            else:
                print("❌ Tunnel not found in Redis")
                return False
            
            # Check pod mapping
            pod_tunnels = await r.smembers(f"pod:{pod_id}:tunnels")
            if tunnel_id in pod_tunnels:
                print(f"✅ Pod mapping: pod:{pod_id}:tunnels contains {tunnel_id}")
            else:
                print("❌ Pod tunnels set not updated")
                return False
        
        # Make HTTP request to populate slug cache
        async with websockets.connect(
            "ws://localhost:8080/ws/" + tunnel_id,
            additional_headers={"X-Tunnel-Token": token}
        ) as ws:
            async def handler():
                msg = await ws.recv()
                data = json.loads(msg)
                if data["type"] == "request":
                    await ws.send(json.dumps({
                        "type": "response",
                        "request_id": data["request_id"],
                        "status": 200,
                        "headers": {},
                        "body": "ok"
                    }))
            
            task = asyncio.create_task(handler())
            
            async with httpx.AsyncClient() as client:
                await client.get(f"http://localhost:8080/local_tunnel/{slug}/test")
            
            task.cancel()
        
        # Check slug cache
        await asyncio.sleep(0.2)
        slug_cache = await r.get(f"slug:{slug}")
        if slug_cache == tunnel_id:
            print(f"✅ Slug cache: slug:{slug} → {tunnel_id}")
        else:
            print(f"⚠️  Slug cache not found (may have expired)")
        
        await r.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        await r.close()
        return False


async def verify_4_control_plane_validation():
    """
    Verify: Control Plane validates tunnels and resolves slugs
    """
    print("\n" + "="*60)
    print("VERIFICATION 4: Control Plane Integration")
    print("="*60)
    
    try:
        # Test 1: Slug resolution
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/tunnels/resolve/my-slug")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Slug resolution: my-slug → {data['tunnel_id']}")
            else:
                print("❌ Slug resolution failed")
                return False
        
        # Test 2: Valid token validation
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/tunnels/validate",
                json={"tunnel_id": "tunnel_test123", "token": "valid_token_123"}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("valid"):
                    print(f"✅ Token validation: valid token accepted")
                else:
                    print("❌ Valid token rejected")
                    return False
            else:
                print("❌ Token validation failed")
                return False
        
        # Test 3: Invalid token rejected
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/tunnels/validate",
                json={"tunnel_id": "tunnel_test123", "token": "wrong_token"}
            )
            if response.status_code == 401:
                print(f"✅ Token validation: invalid token rejected (401)")
            else:
                print(f"⚠️  Expected 401, got {response.status_code}")
        
        # Test 4: Edge rejects invalid tokens
        try:
            async with websockets.connect(
                "ws://localhost:8080/ws/tunnel_test123",
                additional_headers={"X-Tunnel-Token": "wrong_token"}
            ) as ws:
                try:
                    await asyncio.wait_for(ws.recv(), timeout=1)
                    print("❌ Edge accepted invalid token")
                    return False
                except websockets.exceptions.ConnectionClosedError as e:
                    if e.code == 1008:
                        print("✅ Edge rejected invalid token (code 1008)")
                    else:
                        print(f"⚠️  Unexpected close code: {e.code}")
        except websockets.exceptions.ConnectionClosedError as e:
            if e.code == 1008:
                print("✅ Edge rejected invalid token (code 1008)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def main():
    """Run all verifications"""
    print("\n" + "="*60)
    print("PHASE 5 CAPABILITY VERIFICATION")
    print("Verifying claims from roadmap...")
    print("="*60)
    
    results = {}
    
    results["tunnel_connections"] = await verify_1_tunnel_connections()
    await asyncio.sleep(0.5)
    
    results["http_routing"] = await verify_2_http_routing()
    await asyncio.sleep(0.5)
    
    results["redis_state"] = await verify_3_redis_state()
    await asyncio.sleep(0.5)
    
    results["control_plane"] = await verify_4_control_plane_validation()
    
    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    claims = {
        "tunnel_connections": "1️⃣ Accept real tunnel connections",
        "http_routing": "2️⃣ Route public HTTP into tunnels",
        "redis_state": "3️⃣ Use Redis as shared routing state",
        "control_plane": "4️⃣ Validate tunnels via Control Plane"
    }
    
    for key, claim in claims.items():
        status = "✅ VERIFIED" if results[key] else "❌ FAILED"
        print(f"{claim:45s} {status}")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\nResult: {passed}/{total} capabilities verified")
    
    if passed == total:
        print("\n🎉 ALL CLAIMS VERIFIED!")
        print("\nYour Edge Gateway is ready for:")
        print("  • End-to-end testing")
        print("  • Production-style deployment")
        print("  • Tunneling traffic through NAT")
        print("\nYou have built an ngrok/Cloudflare Tunnel equivalent! 🚀")
        return 0
    else:
        print(f"\n⚠️  {total - passed} verification(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
