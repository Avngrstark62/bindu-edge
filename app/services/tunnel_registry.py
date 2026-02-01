"""
Phase 3: Redis-backed tunnel registry for multi-pod coordination.

Stores mappings:
- tunnel:{tunnel_id} -> pod_id
- pod:{pod_id}:tunnels -> set(tunnel_ids)

Phase 4: Slug cache for Control Plane resolution
- slug:{slug} -> tunnel_id (with TTL)
"""
import logging
from typing import Optional
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class TunnelRegistry:
    """Redis-backed registry tracking which pod owns which tunnel."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._pod_id: Optional[str] = None

    async def connect(self, pod_id: str):
        """Initialize Redis connection and set pod_id."""
        self._pod_id = pod_id
        self._redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )
        await self._redis.ping()
        logger.info("Redis tunnel registry connected", extra={"pod_id": pod_id})

    async def disconnect(self):
        """Close Redis connection and cleanup pod tunnels."""
        if self._redis and self._pod_id:
            # Remove all tunnels for this pod
            tunnel_ids = await self._redis.smembers(f"pod:{self._pod_id}:tunnels")
            if tunnel_ids:
                pipeline = self._redis.pipeline()
                for tunnel_id in tunnel_ids:
                    pipeline.delete(f"tunnel:{tunnel_id}")
                pipeline.delete(f"pod:{self._pod_id}:tunnels")
                await pipeline.execute()
                logger.info("Cleaned up pod tunnels", extra={"pod_id": self._pod_id, "count": len(tunnel_ids)})
            
            await self._redis.close()

    async def register_tunnel(self, tunnel_id: str) -> bool:
        """
        Register tunnel as owned by this pod.
        
        Returns True if registered successfully, False if already owned by another pod.
        """
        if not self._redis or not self._pod_id:
            raise RuntimeError("TunnelRegistry not connected")

        # Use SET NX (only set if doesn't exist) for atomic registration
        tunnel_key = f"tunnel:{tunnel_id}"
        was_set = await self._redis.set(
            tunnel_key,
            self._pod_id,
            nx=True,
            ex=settings.TUNNEL_REGISTRY_TTL,
        )

        if was_set:
            # Add to pod's tunnel set
            await self._redis.sadd(f"pod:{self._pod_id}:tunnels", tunnel_id)
            logger.info("Tunnel registered", extra={"tunnel_id": tunnel_id, "pod_id": self._pod_id})
            return True
        else:
            existing_pod = await self._redis.get(tunnel_key)
            logger.warning(
                "Tunnel already registered",
                extra={"tunnel_id": tunnel_id, "existing_pod": existing_pod, "this_pod": self._pod_id}
            )
            return False

    async def remove_tunnel(self, tunnel_id: str):
        """Remove tunnel registration."""
        if not self._redis or not self._pod_id:
            return

        pipeline = self._redis.pipeline()
        pipeline.delete(f"tunnel:{tunnel_id}")
        pipeline.srem(f"pod:{self._pod_id}:tunnels", tunnel_id)
        await pipeline.execute()
        logger.info("Tunnel unregistered", extra={"tunnel_id": tunnel_id, "pod_id": self._pod_id})

    async def get_tunnel_pod(self, tunnel_id: str) -> Optional[str]:
        """Get which pod owns the given tunnel."""
        if not self._redis:
            return None
        return await self._redis.get(f"tunnel:{tunnel_id}")

    async def refresh_tunnel_ttl(self, tunnel_id: str):
        """Refresh the TTL for a tunnel registration."""
        if not self._redis:
            return
        await self._redis.expire(f"tunnel:{tunnel_id}", settings.TUNNEL_REGISTRY_TTL)

    @property
    def pod_id(self) -> Optional[str]:
        """Current pod ID."""
        return self._pod_id

    # Phase 4: Slug cache methods
    async def cache_slug_resolution(self, slug: str, tunnel_id: str):
        """Cache slug -> tunnel_id mapping with TTL."""
        if not self._redis:
            return
        
        await self._redis.set(
            f"slug:{slug}",
            tunnel_id,
            ex=settings.SLUG_CACHE_TTL,
        )
        logger.debug("Slug cached", extra={"slug": slug, "tunnel_id": tunnel_id})

    async def get_cached_slug(self, slug: str) -> Optional[str]:
        """Get cached tunnel_id for slug."""
        if not self._redis:
            return None
        
        tunnel_id = await self._redis.get(f"slug:{slug}")
        if tunnel_id:
            logger.debug("Slug cache hit", extra={"slug": slug, "tunnel_id": tunnel_id})
        return tunnel_id


# Global instance
tunnel_registry = TunnelRegistry()
