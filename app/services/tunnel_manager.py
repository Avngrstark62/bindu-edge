import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional
from fastapi import WebSocket
from app.services.tunnel_registry import tunnel_registry


@dataclass
class Tunnel:
    tunnel_id: str  # Phase 4: Use tunnel_id instead of slug
    websocket: WebSocket
    last_pong: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    heartbeat_task: Optional[asyncio.Task] = None


class TunnelManager:
    """
    Manages local websocket connections and coordinates with Redis registry.
    
    Phase 4: Now uses tunnel_id as the primary identifier instead of slug.
    
    Local state: tunnel_id -> Tunnel (with websocket)
    Redis state: tunnel:{tunnel_id} -> pod_id (shared across pods)
    """

    def __init__(self):
        self.active_tunnels: Dict[str, Tunnel] = {}  # tunnel_id -> Tunnel
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def register_tunnel(self, tunnel_id: str, websocket: WebSocket) -> Tunnel:
        """Register tunnel locally and in Redis using tunnel_id."""
        async with self._lock:
            # Register in Redis first
            registered = await tunnel_registry.register_tunnel(tunnel_id)
            if not registered:
                raise ValueError(f"Tunnel {tunnel_id} already registered on another pod")
            
            # Store locally
            tunnel = Tunnel(tunnel_id=tunnel_id, websocket=websocket)
            self.active_tunnels[tunnel_id] = tunnel
            return tunnel

    async def remove_tunnel(self, tunnel_id: str):
        """Remove tunnel from local state and Redis."""
        async with self._lock:
            tunnel = self.active_tunnels.pop(tunnel_id, None)
            if tunnel and tunnel.heartbeat_task:
                tunnel.heartbeat_task.cancel()
            
            # Remove from Redis
            await tunnel_registry.remove_tunnel(tunnel_id)

    def get_tunnel(self, tunnel_id: str) -> Optional[WebSocket]:
        """Get local tunnel websocket if exists."""
        t = self.active_tunnels.get(tunnel_id)
        return t.websocket if t else None

    async def get_tunnel_pod(self, tunnel_id: str) -> Optional[str]:
        """Query Redis to find which pod owns this tunnel."""
        return await tunnel_registry.get_tunnel_pod(tunnel_id)

    def create_pending_request(self, request_id: str) -> asyncio.Future:
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.pending_requests[request_id] = future
        return future

    def resolve_request(self, request_id: str, data):
        future = self.pending_requests.pop(request_id, None)
        if future and not future.done():
            future.set_result(data)

    def set_pong(self, tunnel_id: str):
        """Update last pong time for tunnel."""
        t = self.active_tunnels.get(tunnel_id)
        if t:
            t.last_pong = asyncio.get_event_loop().time()


tunnel_manager = TunnelManager()
