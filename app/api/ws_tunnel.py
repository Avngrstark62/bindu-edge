import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header
from typing import Optional
from app.services.tunnel_manager import tunnel_manager
from app.services.control_plane_client import control_plane_client
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


async def _heartbeat_loop(tunnel_id: str, websocket: WebSocket):
    """Application-level ping/pong loop. Sends 'ping' messages and expects 'pong'."""
    ping_interval = settings.WS_PING_INTERVAL_SECONDS
    pong_timeout = settings.WS_PONG_TIMEOUT_SECONDS
    while True:
        await asyncio.sleep(ping_interval)
        ping_msg = json.dumps({"type": "ping"})
        try:
            await websocket.send_text(ping_msg)
        except Exception:
            logger.warning("Failed to send ping, closing", extra={"tunnel_id": tunnel_id})
            try:
                await websocket.close()
            except Exception:
                pass
            return

        # wait for pong by checking last_pong timestamp
        await asyncio.sleep(pong_timeout)
        t = tunnel_manager.active_tunnels.get(tunnel_id)
        if not t:
            return
        if (asyncio.get_event_loop().time() - t.last_pong) > (ping_interval + pong_timeout):
            logger.warning("Pong timeout, closing connection", extra={"tunnel_id": tunnel_id})
            try:
                await websocket.close()
            except Exception:
                pass
            return


@router.websocket("/ws/{tunnel_id}")
async def websocket_tunnel(websocket: WebSocket, tunnel_id: str):
    """
    Phase 5: WebSocket endpoint with tunnel token validation.
    
    Requires X-Tunnel-Token header for authentication.
    Validates with Control Plane before accepting connection.
    """
    # Extract tunnel token from headers
    # WebSocket headers can be accessed via websocket.headers
    tunnel_token = websocket.headers.get("x-tunnel-token")
    
    if not tunnel_token:
        logger.warning(
            "Tunnel connection rejected - missing token",
            extra={"tunnel_id": tunnel_id}
        )
        # Must accept first to send proper close code
        await websocket.accept()
        await websocket.close(code=1008, reason="Missing X-Tunnel-Token header")
        return
    
    # Validate tunnel with Control Plane
    validation_result = await control_plane_client.validate_tunnel(tunnel_id, tunnel_token)
    
    if not validation_result:
        logger.error(
            "Tunnel validation failed - Control Plane unavailable",
            extra={"tunnel_id": tunnel_id}
        )
        await websocket.accept()
        await websocket.close(code=1011, reason="Control Plane unavailable")
        return
    
    if not validation_result.get("valid", False):
        status = validation_result.get("status", "invalid")
        logger.warning(
            "Tunnel connection rejected - invalid credentials",
            extra={"tunnel_id": tunnel_id, "status": status}
        )
        await websocket.accept()
        await websocket.close(code=1008, reason=f"Invalid tunnel credentials: {status}")
        return
    
    # Check tunnel status
    tunnel_status = validation_result.get("status")
    if tunnel_status not in ["active"]:
        logger.warning(
            "Tunnel connection rejected - inactive status",
            extra={"tunnel_id": tunnel_id, "status": tunnel_status}
        )
        await websocket.accept()
        await websocket.close(code=1008, reason=f"Tunnel status: {tunnel_status}")
        return
    
    # Token validated, accept connection
    await websocket.accept()
    
    try:
        tunnel = await tunnel_manager.register_tunnel(tunnel_id, websocket)
    except ValueError as e:
        logger.warning("Tunnel registration failed", extra={"tunnel_id": tunnel_id, "error": str(e)})
        await websocket.close(code=1008, reason=str(e))
        return
    
    logger.info(
        "Tunnel connected and validated",
        extra={"tunnel_id": tunnel_id, "expires_at": validation_result.get("expires_at")}
    )

    # start heartbeat task
    tunnel.heartbeat_task = asyncio.create_task(_heartbeat_loop(tunnel_id, websocket))

    try:
        while True:
            message = await websocket.receive_text()

            if not message:
                continue

            if len(message.encode("utf-8")) > settings.MAX_WS_PAYLOAD_BYTES:
                logger.warning("Payload too large, closing", extra={"tunnel_id": tunnel_id})
                await websocket.close(code=1009)
                break

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from tunnel", extra={"tunnel_id": tunnel_id})
                continue

            mtype = data.get("type")
            if mtype == "response":
                request_id = data.get("request_id")
                if request_id:
                    tunnel_manager.resolve_request(request_id, data)
            elif mtype == "pong":
                tunnel_manager.set_pong(tunnel_id)
            elif mtype == "ping":
                # reply with pong
                try:
                    await websocket.send_text(json.dumps({"type": "pong"}))
                except Exception:
                    pass
            else:
                logger.debug("Unhandled WS message type", extra={"tunnel_id": tunnel_id, "type": mtype})

    except WebSocketDisconnect:
        logger.info("Tunnel disconnected", extra={"tunnel_id": tunnel_id})
    finally:
        await tunnel_manager.remove_tunnel(tunnel_id)
