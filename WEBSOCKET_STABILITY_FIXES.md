# WebSocket Stability Fixes

## Problem Summary
The Twitch miner was experiencing cascading WebSocket failures with 467 streamers (~40 WebSocket connections):

### Errors Observed:
- `BrokenPipeError: [Errno 32] Broken pipe` - connections dying while sending PINGs
- `WebSocket error: ping pong failed` - Twitch closing connections due to failed keep-alive
- `ssl.SSLError: [SSL: BAD_LENGTH]` - SSL/TLS corruption from network congestion
- Thread crashes from unhandled exceptions

### Root Causes:
1. **Ping Storm**: 40+ WebSockets pinging every 25-30 seconds = 80-96 pings/minute
2. **No Error Handling**: Unhandled BrokenPipeError and SSL errors crashed threads
3. **Synchronized Operations**: All WebSockets starting/reconnecting simultaneously
4. **Network Congestion**: Overwhelming Fly.io's network stack with concurrent connections

## Solutions Implemented

### 1. Enhanced Error Handling (`TwitchWebSocket.py`)
**Before:**
```python
def ping(self):
    self.send({"type": "PING"})
    self.last_ping = time.time()

def send(self, request):
    try:
        super().send(request_str)
    except WebSocketConnectionClosedException:
        self.is_closed = True
```

**After:**
```python
def ping(self):
    try:
        self.send({"type": "PING"})
        self.last_ping = time.time()
    except Exception as e:
        logger.warning(f"Failed to send PING: {e}")
        self.is_closed = True

def send(self, request):
    try:
        super().send(request_str)
    except WebSocketConnectionClosedException:
        self.is_closed = True
    except BrokenPipeError:
        self.is_closed = True
    except OSError as e:  # SSL errors, connection reset
        self.is_closed = True
    except Exception as e:
        self.is_closed = True
```

**Impact:** Prevents thread crashes, enables graceful recovery

### 2. Reduced Ping Frequency (`WebSocketsPool.py`)
**Before:** 25-30 seconds (aggressive)
**After:** 120-180 seconds (2-3 minutes)

**Rationale:**
- Twitch allows up to 5 minutes between PONGs before disconnect
- With 40 connections: 25s = 96 pings/min → 180s = 13 pings/min (86% reduction)
- Reduces network congestion while maintaining connection stability

### 3. Staggered WebSocket Startup (`WebSocketsPool.py`)
**Before:** All WebSockets start immediately
**After:** Each connection delayed by (index × 5) seconds, max 30s

**Impact:**
- Spreads initial PING load over 30+ seconds instead of simultaneous burst
- Prevents "thundering herd" problem on application start

### 4. Randomized Reconnection Delays (`WebSocketsPool.py`)
**Before:** All failed connections reconnect after exactly 60 seconds
**After:** Random delay between 45-75 seconds, with randomized topic resubscription

**Impact:**
- Prevents all failed connections from reconnecting simultaneously
- Avoids "reconnection storms" when multiple connections fail together

## Expected Results

### Immediate Benefits:
✅ **No more thread crashes** - All errors properly handled
✅ **86% reduction in ping traffic** - From 96 to 13 pings/minute
✅ **Smoother network usage** - Operations spread over time instead of synchronized bursts
✅ **Graceful degradation** - Connections fail cleanly instead of cascading

### Monitoring:
After deploying, watch for:
- Fewer "ping pong failed" errors
- No more `ssl.SSLError` crashes
- Connections staying alive longer (2-3 min between pings)
- Staggered reconnection messages instead of simultaneous bursts

### Logs to Monitor:
```bash
# Good signs:
"Staggering WebSocket start by Xs"
"Reconnecting to Twitch PubSub server in ~Xs seconds" (varying X values)

# Should disappear:
"ssl.SSLError: [SSL: BAD_LENGTH]"
"Exception in thread Thread-XXX"
Multiple "BrokenPipeError" at same timestamp
```

## Deployment

### 1. Commit Changes:
```bash
cd "/Users/nathan/Twitch Miner/Twitch-miner-master"
git add TwitchChannelPointsMiner/classes/TwitchWebSocket.py
git add TwitchChannelPointsMiner/classes/WebSocketsPool.py
git commit -m "Fix WebSocket stability issues: better error handling, reduced ping frequency, staggered operations"
```

### 2. Deploy to Fly.io:
```bash
fly deploy -a twitch-miner
```

### 3. Monitor Logs:
```bash
fly logs -a twitch-miner
```

## Rollback Plan
If issues persist:
```bash
git revert HEAD
fly deploy -a twitch-miner
```

## Additional Recommendations

### If issues continue:
1. **Reduce streamer count**: Try with 200-300 streamers to confirm it's a scaling issue
2. **Increase Fly.io resources**: Upgrade machine type if network bandwidth is limited
3. **Monitor system resources**: Check CPU/memory usage with `fly status -a twitch-miner`
4. **Consider connection pooling**: Implement topic consolidation to reduce WebSocket count

### Configuration tunables (if needed):
- Ping interval: Currently 120-180s, can increase to 180-240s if needed
- Stagger delay: Currently 5s per connection, can increase to 10s
- Reconnection randomization: Currently 45-75s, can widen to 30-90s

## Technical Notes

### Why these specific values?
- **120-180s ping interval**: Twitch tolerates up to 5min, this provides 2x safety margin
- **5s stagger per connection**: With 40 connections = 200s total spread (3.3 min)
- **45-75s reconnection**: Centers around 60s but prevents synchronization
- **15-45s topic resubscription**: Allows connection to stabilize before load

### WebSocket connection count calculation:
- 467 streamers × ~6 topics/streamer = ~2,800 topics
- 50 topics/WebSocket max = ~56 WebSocket connections needed
- Each connection has its own thread pinging independently

This is a **significant network load**, explaining the instability.
