import asyncio
import websockets
import json

# Phase 4: Now using tunnel_id instead of slug
TUNNEL_ID = "tunnel_test123"
EDGE_WS = f"ws://localhost:8080/ws/{TUNNEL_ID}"


async def run():
    async with websockets.connect(EDGE_WS) as ws:
        print("✓ Connected to edge")

        while True:
            msg = await ws.recv()
            data = json.loads(msg)

            if data["type"] == "request":
                print(f"→ Got request: {data['method']} {data['path']}")

                response = {
                    "type": "response",
                    "request_id": data["request_id"],
                    "status": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"message": "Hello from local agent", "path": data["path"]}
                }

                await ws.send(json.dumps(response))
                print(f"← Sent response")

            elif data["type"] == "ping":
                # Reply with pong
                await ws.send(json.dumps({"type": "pong"}))
                print("♥ Pong sent")


asyncio.run(run())