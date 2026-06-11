# AgentOS Kernel Specification v0.1

## 1. Agent Process Model

An **Agent Process** is the fundamental unit of execution.

### States
```
CREATED → READY → RUNNING → BLOCKED → TERMINATED
                     ↑          ↓
                     └── READY ←┘
```

### Properties
- **PID**: Unique process identifier (u64)
- **Capabilities**: Set of granted capability tokens
- **Memory**: Isolated heap (no shared memory by default)
- **Priority**: SYSTEM(0) | INTERACTIVE(1) | NORMAL(2) | BACKGROUND(3)
- **State**: Process lifecycle state
- **Checkpoint**: Serializable state snapshot

### Signals
| Signal | Action |
|--------|--------|
| SIGTERM | Graceful shutdown (save checkpoint, cleanup) |
| SIGKILL | Immediate termination (no cleanup) |
| SIGUSR1 | Trigger checkpoint (save state to disk) |
| SIGUSR2 | Trigger cycle (run immediately) |

---

## 2. Scheduler

Multi-Level Feedback Queue (MLFQ):

| Level | Priority | Time Quantum | Use Case |
|-------|----------|-------------|----------|
| 0 | SYSTEM | 50ms | Kernel agents (watchdog, audit) |
| 1 | INTERACTIVE | 100ms | User-triggered actions |
| 2 | NORMAL | 200ms | Regular agent cycles |
| 3 | BACKGROUND | 500ms | Maintenance, learning |

### Rules
1. New processes enter NORMAL queue
2. If process uses full quantum → demote one level
3. If process yields early → promote one level
4. After 5 seconds without running → boost to INTERACTIVE (starvation prevention)
5. Max concurrent agents: configurable (default 4)
6. SYSTEM priority is never preempted

---

## 3. Inter-Process Communication (IPC)

### Channel-Based IPC (Fuchsia-inspired)
```
Channel = (Endpoint_A, Endpoint_B)

Endpoint.write(message: TypedMessage) → Result
Endpoint.read() → TypedMessage
Endpoint.wait(timeout) → Event
```

### Message Format
```
TypedMessage {
  header: {
    sender_pid: u64,
    type_id: u32,       // Schema-validated type
    timestamp: u64,
    msg_id: u64,
  },
  payload: bytes,       // Serialized data (MessagePack)
  capabilities: [Cap],  // Attached capability tokens
}
```

### Port Objects (Service Discovery)
```
Port.create(name: &str) → Port
Port.bind(handler: fn(Message)) → Result
Port.lookup(name: &str) → Option<Endpoint>
```

---

## 4. Capability System

### Zero Ambient Authority
Every resource access requires an explicit capability token. No default permissions.

### Capability Token
```
Capability {
  id: u64,
  resource: ResourceId,     // What it grants access to
  permissions: Permissions, // read | write | execute | create | destroy
  scope: Scope,            // Constraints (time, count, etc.)
  delegatable: bool,       // Can be passed to child processes
  revoked: bool,           // Immediately invalidates
}
```

### Operations
- **Grant**: Parent gives capability to child (with <= permissions)
- **Delegate**: Process passes capability to another (if delegatable)
- **Revoke**: Capability creator invalidates it (propagates to all copies)
- **Check**: Kernel validates capability on every resource access

---

## 5. Memory Management

### Per-Agent Memory Hierarchy
```
┌─────────────────────────────┐
│   Working Memory (fast)     │  In-process, volatile
│   - Current context         │  Cleared per cycle
│   - Active computation      │
├─────────────────────────────┤
│   Session Memory (durable)  │  Persisted per-session
│   - Conversation history    │  SQLite / Redis
│   - Decision log            │
├─────────────────────────────┤
│   Long-Term Memory          │  Persistent, searchable
│   - Learned patterns        │  Vector DB / SQLite
│   - User preferences        │
│   - Entity relationships    │
└─────────────────────────────┘
```

### Limits
- Working: 10MB per agent (configurable)
- Session: 100MB per agent
- Long-Term: 1GB per agent (shared pool)
- Swap: Overflow to disk (SQLite)

### GC
- Working: cleared after each cycle
- Session: evicted after 24h idle
- Long-Term: LRU eviction when pool full

---

## 6. Semantic Bus (System Call Interface)

### Actions = System Calls
```
Agent calls:
  bus.execute("spotify.play_track", {query: "lo-fi"})

Kernel:
  1. Validate capability (agent has "media.play_music")
  2. Validate params (schema check)
  3. Check risk level → request confirmation if needed
  4. Run through Verification Layer
  5. Execute handler
  6. Log to Audit
  7. Return result
```

### MCP Wire Format
All actions are also exposed as MCP tools via JSON-RPC 2.0:
```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
 "params": {"name": "spotify.play_track", "arguments": {"query": "lo-fi"}}}
```

---

## 7. Hardware Abstraction Layer (HAL)

### Platform Trait
```rust
trait Platform {
    fn get_location() -> Option<Location>;
    fn get_battery() -> BatteryInfo;
    fn get_network_status() -> NetworkInfo;
    fn take_photo() -> Result<PhotoData>;
    fn send_notification(title: &str, body: &str) -> Result<()>;
    fn trigger_haptic(pattern: HapticPattern) -> Result<()>;
    fn get_active_app() -> Option<String>;
    fn get_clipboard() -> Option<String>;
}
```

### Implementations
| Platform | Method |
|----------|--------|
| macOS | CoreLocation, IOKit, AppKit |
| Linux | D-Bus, PulseAudio, NetworkManager |
| Android | LocationManager, BatteryManager, AccessibilityService |
| iOS | CoreLocation, UIKit, HealthKit |
| Windows | WinRT, Win32 API |

---

## 8. Security Model

### Layers
1. **Capability check** — every resource access
2. **Schema validation** — every action parameter
3. **Risk assessment** — every action rated safe→critical
4. **Deterministic verification** — non-AI safety rules
5. **Rate limiting** — per-agent, per-action
6. **Audit logging** — immutable, append-only
7. **Encryption** — all credentials AES-256-GCM

### Threat Model
| Threat | Mitigation |
|--------|-----------|
| Malicious agent | Capability isolation, no ambient authority |
| Hallucinated action | Deterministic verification layer |
| Credential theft | Identity vault with scoped session tokens |
| Privilege escalation | Capability checks at every syscall |
| Resource exhaustion | Governor with CPU/memory/network quotas |
| Replay attack | Dedup detection in verification layer |
| Data exfiltration | Network capability required, audit logged |
