"""
Mock Control Plane server for testing Phase 4 and Phase 5.

This simulates the Control Plane API that Edge gateway calls
to resolve slugs to tunnel IDs and validate tunnel tokens.

Run with: python mock_control_plane.py
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
import uvicorn

app = FastAPI(title="Mock Control Plane")

SLUG_DATABASE = {
    "my-slug": {
        "tunnel_id": "tunnel_test123",
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
        "status": "active"
    },
    "test-slug": {
        "tunnel_id": "tunnel_abc456",
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "status": "active"
    },
    "expired-slug": {
        "tunnel_id": "tunnel_expired",
        "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        "status": "expired"
    },
}

# Phase 5: Tunnel token database
# In production, tokens would be cryptographically secure and stored in a database
TUNNEL_TOKENS = {
    "tunnel_test123": {
        "token": "valid_token_123",
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
        "status": "active"
    },
    "tunnel_abc456": {
        "token": "valid_token_456",
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "status": "active"
    },
    "tunnel_expired": {
        "token": "expired_token",
        "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        "status": "expired"
    },
    "tunnel_revoked": {
        "token": "revoked_token",
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "status": "revoked"
    },
}


class ValidateTunnelRequest(BaseModel):
    tunnel_id: str
    token: str


@app.get("/api/tunnels/resolve/{slug}")
async def resolve_slug(slug: str):
    """
    Resolve slug to tunnel metadata.
    
    Returns:
        200: {tunnel_id, expires_at, status}
        404: Slug not found
    """
    tunnel_info = SLUG_DATABASE.get(slug)
    
    if not tunnel_info:
        raise HTTPException(status_code=404, detail="Slug not found")
    
    return tunnel_info


@app.post("/api/tunnels/validate")
async def validate_tunnel(request: ValidateTunnelRequest):
    """
    Phase 5: Validate tunnel credentials.
    
    Checks if the provided tunnel_id and token are valid and active.
    
    Returns:
        200: {valid: true, tunnel_id, status, expires_at}
        401: Invalid token
        404: Tunnel not found
    """
    tunnel_info = TUNNEL_TOKENS.get(request.tunnel_id)
    
    if not tunnel_info:
        raise HTTPException(status_code=404, detail="Tunnel not found")
    
    # Check if token matches
    if tunnel_info["token"] != request.token:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Check tunnel status
    status = tunnel_info["status"]
    expires_at = tunnel_info["expires_at"]
    
    # Check if expired (even if status says active)
    if datetime.fromisoformat(expires_at) < datetime.utcnow():
        status = "expired"
    
    return {
        "valid": status == "active",
        "tunnel_id": request.tunnel_id,
        "status": status,
        "expires_at": expires_at
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    print("🚀 Starting Mock Control Plane on http://localhost:8000")
    print("\nAvailable slugs:")
    for slug, info in SLUG_DATABASE.items():
        print(f"  - {slug} → {info['tunnel_id']} ({info['status']})")
    print("\nPhase 5 - Available tunnels with tokens:")
    for tunnel_id, info in TUNNEL_TOKENS.items():
        print(f"  - {tunnel_id}")
        print(f"    Token: {info['token']}")
        print(f"    Status: {info['status']}")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
