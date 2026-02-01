# Bindu Edge Gateway - Current State (After Phase 5)

## **What's Working**

A production-ready **reverse tunnel edge gateway** that routes public HTTP traffic through private WebSocket tunnels with full authentication and multi-pod coordination.

## **How It Works**

### **1. Agent Connection (WebSocket Tunnel)**
- Agent connects to `/ws/{tunnel_id}` with `X-Tunnel-Token` header
- Edge validates token with Control Plane **before** accepting
- Only active, non-expired, non-revoked tunnels allowed
- Connection registered in Redis + local memory
- Heartbeat keeps connection alive (ping/pong every 10s)

### **2. HTTP Request Routing**
- Public request arrives at `/local_tunnel/{slug}/{path}`
- Edge checks Redis cache for slug → tunnel_id mapping
- If cache miss: calls Control Plane to resolve slug
- Result cached for 60 seconds
- Request forwarded through correct WebSocket tunnel as JSON
- Agent processes locally, sends response back
- Edge returns response to public client

### **3. Multi-Pod Coordination (Redis)**
- Each pod has unique ID: `hostname-uuid`
- Redis stores: `tunnel:{tunnel_id} → pod_id`
- Prevents same tunnel connecting to multiple pods
- Pods clean up their tunnels on shutdown

### **4. Security (Phase 5)**
- ✅ Token validation via Control Plane
- ✅ Expired/revoked tunnels rejected
- ✅ Missing tokens rejected  
- ✅ Invalid credentials rejected
- ✅ All attempts logged with structured context

### **5. Protocol Features**
- Max payload size: 64KB
- Request timeout: 30 seconds
- Strict message schema: request/response/ping/pong
- Auto-cleanup of dead connections

## **Current Capabilities**

✅ Single-pod tunneling works perfectly  
✅ Multi-pod ready (Redis coordination)  
✅ Slug-based routing via Control Plane  
✅ Authenticated tunnel connections  
✅ Status enforcement (active/expired/revoked)  
⚠️ Multi-pod routing **not yet implemented** (returns 503 if tunnel on different pod)  

## **Architecture Overview**

```
┌─────────────┐
│   Public    │
│   Client    │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────────────────────────┐
│      Edge Gateway (Pod)         │
│  ┌──────────────────────────┐   │
│  │  HTTP Endpoint           │   │
│  │  /local_tunnel/{slug}/   │   │
│  └──────────┬───────────────┘   │
│             │                   │
│  ┌──────────▼───────────────┐   │
│  │  Slug Resolution         │   │
│  │  (Control Plane + Cache) │   │
│  └──────────┬───────────────┘   │
│             │                   │
│  ┌──────────▼───────────────┐   │
│  │  WebSocket Tunnel        │   │
│  │  (Validated Connection)  │   │
│  └──────────┬───────────────┘   │
└─────────────┼───────────────────┘
              │ WS
              ▼
       ┌─────────────┐
       │   Agent     │
       │  (Private)  │
       └─────────────┘

External Dependencies:
├── Redis (Multi-pod coordination)
└── Control Plane (Slug resolution + Auth)
```

## **Components**

### **Core Services**
- `tunnel_manager.py` - Local tunnel state + request routing
- `tunnel_registry.py` - Redis coordination layer
- `control_plane_client.py` - Slug resolution + validation

### **API Endpoints**
- `/ws/{tunnel_id}` - WebSocket tunnel connection (validated)
- `/local_tunnel/{slug}/{path}` - Public HTTP routing
- `/health/live` - Liveness probe
- `/health/ready` - Readiness probe

### **Configuration**
- Redis: localhost:6379
- Control Plane: localhost:8000
- Edge Gateway: localhost:8080
- Configurable via environment variables

## **Testing**

All Phase 5 tests passing (6/6):
- ✅ Valid token connection accepted
- ✅ Invalid token rejected
- ✅ Missing token rejected
- ✅ Expired tunnel rejected
- ✅ Revoked tunnel rejected
- ✅ Full end-to-end flow working

## **Next Steps**

**Phase 6** - Security Protections:
- Rate limiting (per-tunnel)
- Request body size limits
- Global connection caps
- Per-request timeout enforcement
- HTTP method filtering

**Phase 7** - Observability:
- Prometheus metrics
- Request latency tracking
- Active tunnel gauges
- Structured logging enhancements

**Phase 8** - Multi-Pod Routing:
- Inter-pod messaging (Redis pub/sub or NATS)
- Route requests to tunnels on other pods
- Horizontal scaling behind load balancer
