import json
import uuid
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from app.services.tunnel_manager import tunnel_manager
from app.services.tunnel_registry import tunnel_registry
from app.services.control_plane_client import control_plane_client
from app.core.config import settings
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)


@router.api_route("/local_tunnel/{slug}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def forward_request(slug: str, path: str, request: Request):
    """
    Phase 4: Routes HTTP requests through tunnels using slug resolution.
    
    Flow:
    1. Check Redis cache for slug -> tunnel_id
    2. If miss, call Control Plane to resolve
    3. Cache the result
    4. Forward request to tunnel
    """
    # Step 1: Check cache
    tunnel_id = await tunnel_registry.get_cached_slug(slug)
    
    # Step 2: If cache miss, resolve via Control Plane
    if not tunnel_id:
        cp_result = await control_plane_client.resolve_slug(slug)
        
        if not cp_result:
            raise HTTPException(status_code=404, detail="Slug not found")
        
        tunnel_id = cp_result.get("tunnel_id")
        status = cp_result.get("status")
        
        # Validate tunnel is active
        if status != "active":
            raise HTTPException(
                status_code=410,
                detail=f"Tunnel {status}"
            )
        
        # Step 3: Cache the resolution
        await tunnel_registry.cache_slug_resolution(slug, tunnel_id)
    
    # Step 4: Get tunnel websocket (using tunnel_id now)
    websocket = tunnel_manager.get_tunnel(tunnel_id)

    if not websocket:
        # Tunnel not connected to this pod
        # For Phase 4, we just return 503 (Phase 8 will add inter-pod routing)
        raise HTTPException(
            status_code=503,
            detail="Tunnel not connected to this pod"
        )

    request_id = str(uuid.uuid4())
    body = await request.body()

    payload = {
        "type": "request",
        "request_id": request_id,
        "method": request.method,
        "path": f"/{path}",
        "headers": dict(request.headers),
        "body": body.decode() if body else None,
    }

    payload_text = json.dumps(payload)
    if len(payload_text.encode("utf-8")) > settings.MAX_WS_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Request payload too large for tunnel")

    future = tunnel_manager.create_pending_request(request_id)

    try:
        await websocket.send_text(payload_text)
    except Exception:
        # Sending failed; cleanup and return 502
        tunnel_manager.pending_requests.pop(request_id, None)
        raise HTTPException(status_code=502, detail="Failed to send to tunnel")

    try:
        response_data = await asyncio.wait_for(
            future, timeout=settings.REQUEST_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        tunnel_manager.pending_requests.pop(request_id, None)
        raise HTTPException(status_code=504, detail="Tunnel timeout")

    # Get headers but remove Content-Length (will be recalculated by FastAPI)
    response_headers = response_data.get("headers", {})
    response_headers = {k: v for k, v in response_headers.items() 
                       if k.lower() not in ['content-length', 'transfer-encoding']}

    # Return raw response body (it's already properly formatted from local server)
    body = response_data.get("body", "")
    
    return Response(
        status_code=response_data.get("status", 200),
        content=body,
        headers=response_headers,
    )
