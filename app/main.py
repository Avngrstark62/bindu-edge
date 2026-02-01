import socket
import uuid
from fastapi import FastAPI
from app.api import health, http_tunnel, ws_tunnel
from app.core.config import settings
from app.core.logging import setup_logging
from app.services.tunnel_registry import tunnel_registry
from app.services.control_plane_client import control_plane_client
import logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME)

# Global pod_id (set at startup)
POD_ID: str = ""


def generate_pod_id() -> str:
    """Generate unique pod identifier: hostname-shortid"""
    hostname = socket.gethostname()
    short_id = str(uuid.uuid4())[:8]
    return f"{hostname}-{short_id}"


@app.on_event("startup")
async def startup_event():
    global POD_ID
    POD_ID = generate_pod_id()
    
    logger.info("Starting Edge Gateway", extra={"env": settings.ENV, "pod_id": POD_ID})
    
    # Initialize Redis tunnel registry
    try:
        await tunnel_registry.connect(POD_ID)
    except Exception as e:
        logger.error("Failed to connect to Redis", extra={"error": str(e)})
        raise
    
    # Initialize Control Plane client (Phase 4)
    try:
        await control_plane_client.connect()
    except Exception as e:
        logger.error("Failed to initialize Control Plane client", extra={"error": str(e)})
        raise


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Edge Gateway", extra={"pod_id": POD_ID})
    await tunnel_registry.disconnect()
    await control_plane_client.disconnect()

app.include_router(health.router)
app.include_router(ws_tunnel.router)
app.include_router(http_tunnel.router)
