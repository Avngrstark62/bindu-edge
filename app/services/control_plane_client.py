"""
Phase 4: Control Plane client for slug resolution.

Communicates with Bindu Control Plane to resolve slugs to tunnel_ids
and validate tunnel metadata.
"""
import logging
from typing import Optional
from datetime import datetime
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class ControlPlaneClient:
    """Client for communicating with Bindu Control Plane."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self):
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=settings.CONTROL_PLANE_URL,
            timeout=httpx.Timeout(10.0),
        )
        logger.info("Control Plane client initialized", extra={"base_url": settings.CONTROL_PLANE_URL})

    async def disconnect(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()

    async def resolve_slug(self, slug: str) -> Optional[dict]:
        """
        Resolve slug to tunnel metadata.
        
        Returns:
            {
                "tunnel_id": str,
                "expires_at": str (ISO format),
                "status": str ("active" | "expired" | "revoked")
            }
            or None if not found
        """
        if not self._client:
            raise RuntimeError("ControlPlaneClient not connected")

        try:
            response = await self._client.get(f"/api/tunnels/resolve/{slug}")
            
            if response.status_code == 404:
                logger.info("Slug not found in Control Plane", extra={"slug": slug})
                return None
            
            if response.status_code != 200:
                logger.error(
                    "Control Plane error",
                    extra={"slug": slug, "status_code": response.status_code}
                )
                return None
            
            data = response.json()
            logger.info("Slug resolved", extra={"slug": slug, "tunnel_id": data.get("tunnel_id")})
            return data
        
        except httpx.TimeoutException:
            logger.error("Control Plane timeout", extra={"slug": slug})
            return None
        except Exception as e:
            logger.error("Control Plane request failed", extra={"slug": slug, "error": str(e)})
            return None

    async def validate_tunnel(self, tunnel_id: str, token: str) -> Optional[dict]:
        """
        Validate tunnel credentials with Control Plane.
        
        Phase 5: Validates that the tunnel_id and token are authorized
        to establish a connection.
        
        Args:
            tunnel_id: The tunnel identifier
            token: The tunnel authentication token
            
        Returns:
            {
                "valid": bool,
                "tunnel_id": str,
                "status": str ("active" | "expired" | "revoked"),
                "expires_at": str (ISO format),
            }
            or None if validation request fails
        """
        if not self._client:
            raise RuntimeError("ControlPlaneClient not connected")

        try:
            response = await self._client.post(
                "/api/tunnels/validate",
                json={"tunnel_id": tunnel_id, "token": token}
            )
            
            if response.status_code == 401:
                logger.warning(
                    "Tunnel validation failed - unauthorized",
                    extra={"tunnel_id": tunnel_id}
                )
                return {"valid": False, "tunnel_id": tunnel_id, "status": "unauthorized"}
            
            if response.status_code == 404:
                logger.warning(
                    "Tunnel validation failed - not found",
                    extra={"tunnel_id": tunnel_id}
                )
                return {"valid": False, "tunnel_id": tunnel_id, "status": "not_found"}
            
            if response.status_code != 200:
                logger.error(
                    "Control Plane error during validation",
                    extra={"tunnel_id": tunnel_id, "status_code": response.status_code}
                )
                return None
            
            data = response.json()
            logger.info(
                "Tunnel validation completed",
                extra={"tunnel_id": tunnel_id, "valid": data.get("valid")}
            )
            return data
        
        except httpx.TimeoutException:
            logger.error("Control Plane timeout during validation", extra={"tunnel_id": tunnel_id})
            return None
        except Exception as e:
            logger.error(
                "Control Plane validation request failed",
                extra={"tunnel_id": tunnel_id, "error": str(e)}
            )
            return None


# Global instance
control_plane_client = ControlPlaneClient()
