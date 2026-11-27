# NetCore TUI — Network Simulation Specification

| Field          | Value                                   |
| -------------- | --------------------------------------- |
| Owner          | NETWORK_ENGINEER (author), ARCHITECT (review) |
| Status         | Approved baseline v1.0                  |
| Last updated   | 2026-11-27                              |
| Scope          | IPv4, L2 switching, L3 static routing, simulated ARP, TTL, failures, traffic |

This document is normative. Words **MUST**, **MUST NOT**, **SHOULD**,
**MAY** follow RFC 2119. Behaviour not described here is out of scope
and must not be invented by an implementing agent — raise it as an open
question instead.

---

## 1. Simulation Principles

1. **Simulation only.** No packet ever leaves the process. No host
   network configuration is read or modified.
2. **Deterministic.** Same topology + same inputs + same seed ⇒ same
   result, same trace, same counters.
3. **Explainable.** Every decision produces a `HopRecord` with a
   human-readable `reason`.
4. **No fabricated measurements.** Latency, utilization and throughput
   are *simulated values* computed from the model in §10, always
   labelled as simulated. Nothing is presented as a measurement of real
   hardware or of the host machine.

## 2. Addressing

### 2.1 IPv4

- Parsing uses `ipaddress.IPv4Address`, `IPv4Interface`, `IPv4Network`.
- Input forms accepted: `"10.0.1.10"` (address), `"10.0.1.10/24"`
  (interface), `"10.0.1.0/24"` (network, `strict=True`).
- Rejected (raise `InvalidAddressError` with the offending text):
  - octet > 255, fewer/more than 4 octets, leading/trailing spaces
    inside, leading zeros (`010.0.0.1`), empty string;
  - prefix outside 0–32;
  - subnet with host bits set (`10.0.1.5/24` given as a subnet).
- Interface address rules:
  - MUST lie inside an existing `Subnet`.
  - MUST NOT equal the network or broadcast address when prefix ≤ 30.
  - /31 (point-to-point) both addresses usable; /32 allowed only for
    loopback interfaces.
- Reserved ranges allowed in labs: all RFC 1918 ranges, `100.64.0.0/10`,
  `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`. Other public
  ranges are allowed but produce a `WARNING` event ("public range used
  in lab").

### 2.2 MAC Addresses

- Canonical format: lowercase, colon-separated `aa:bb:cc:dd:ee:ff`.
- Accepted input: `:`, `-` or `.` (Cisco `aabb.ccdd.eeff`) separators,
  any case; normalised to canonical.
- Generated MACs: locally administered unicast — first octet `0x02`,
  remaining 5 octets from the seeded RNG, retried until unique.
- `ff:ff:ff:ff:ff:ff` is the broadcast MAC; it MUST NOT be assigned.
- Multicast MACs (LSB of first octet = 1) MUST NOT be assigned.

### 2.3 Uniqueness (enforced by `NetworkTopology`)

| Attribute         | Scope        | Error                    |
| ----------------- | ------------ | ------------------------ |
| Hostname          | Lab, case-insensitive | `DuplicateHostnameError` |
| IPv4 address      | Lab          | `DuplicateAddressError`  |
| MAC address       | Lab          | `DuplicateMacError`      |
| Interface name    | Device       | `DuplicateInterfaceError`|
| Subnet            | Lab, no overlap unless parent/child declared | `OverlappingSubnetError` |

## 3. Devices

| Property            | Router              | Switch                 | Server            |
| ------------------- | ------------------- | ---------------------- | ----------------- |
| OSI role            | L3                  | L2                     | End host          |
| Interfaces          | `ge0/0` … (L3, have IP) | ports `1..N` (no IP)  | `eth0` … (have IP) |
| Default count       | 4                   | 24                     | 2                 |
| Allowed count       | 1–16                | 1–96                   | 1–8               |
| Forwards packets    | Yes (routing table) | Yes (MAC table)        | No (sink/source)  |
| Decrements TTL      | Yes                 | No                     | No                |
| ARP table           | Yes                 | No                     | Yes               |
| Default gateway     | n/a                 | n/a                    | Optional, per server |

Status values: `ONLINE`, `OFFLINE`, `MAINTENANCE`. Only `ONLINE`
devices send, receive or forward. `MAINTENANCE` behaves like `OFFLINE`
for forwarding but is shown differently in the UI.

### 3.1 Interface State

An interface is **operationally up** iff:

```
device.status == ONLINE
and interface.admin_up
and interface.link is not None
and interface.link.admin_up
and peer_interface.admin_up
and peer_device.status == ONLINE
```

## 4. Links

- A `Link` joins exactly two interfaces on **different** devices.
- An interface MUST have at most one link.
- Attributes: `capacity_mbps` (int, 1–400_000, default 1000),
  `admin_up` (bool), `latency_ms` (float, simulated, default 0.1),
  `utilization_pct` (derived, 0–100, read-only — §10).
- Router↔Router, Router↔Switch, Switch↔Switch, Switch↔Server,
  Router↔Server links are all valid. Server↔Server direct links are
  valid (back-to-back) but generate an `INFO` event.

## 5. Packet & Frame Model

```
Packet (L3)
  packet_id: int            # monotonically increasing per run
  src_ip: IPv4Address
  dst_ip: IPv4Address
  protocol: Protocol        # ICMP | TCP | UDP
  ttl: int                  # 1..255, default from settings (64)
  size_bytes: int           # 64..9000, default 64
  payload: str              # optional label, max 128 chars

Frame (L2)
  src_mac: MacAddress
  dst_mac: MacAddress
  packet: Packet | ArpMessage
```

Packets are immutable; TTL decrement produces a new `Packet` via
`packet.with_ttl(ttl - 1)` so the trace can show each hop's TTL.

## 6. Routing

### 6.1 Routing Table Entries

```
RoutingEntry
  destination: IPv4Network
  next_hop: IPv4Address | None   # None ⇒ directly connected
  interface: str                 # egress interface name
  route_type: CONNECTED | STATIC | DEFAULT
  admin_distance: int            # CONNECTED=0, STATIC=1, DEFAULT=1
  metric: int                    # 0..65535, default 0
```

- **Connected routes** are generated automatically for every
  interface address on an operationally *configured* interface
  (presence of address; operational state is checked at forwarding).
  They are removed when the address is removed.
- **Static routes** require: `destination` strictly valid network;
  `next_hop` inside a connected subnet of this router **at creation
  time** (`InvalidNextHopError` otherwise); `interface` exists.
- **Default route** is a static route with destination `0.0.0.0/0`.
- Duplicate (destination, next_hop) pair → `DuplicateRouteError`.

### 6.2 Longest Prefix Match (LPM)

Algorithm (MUST be implemented on integers, never on strings):

```
candidates = [e for e in table if dst_ip in e.destination]
if not candidates: return None
best = max(candidates, key=lambda e: (
    e.destination.prefixlen,      # longest prefix first
    -e.admin_distance,            # lower AD wins
    -e.metric,                    # lower metric wins
    -e.insertion_index,           # earlier entry wins
))
```

Example table and expected results (used verbatim in tests):

| Destination     | Next hop   | Interface |
| --------------- | ---------- | --------- |
| 0.0.0.0/0       | 10.0.0.1   | ge0/0     |
| 10.0.0.0/8      | 10.0.0.2   | ge0/1     |
| 10.1.0.0/16     | 10.0.0.3   | ge0/1     |
| 10.1.2.0/24     | (connected)| ge0/2     |

| dst_ip      | Selected route |
| ----------- | -------------- |
| 10.1.2.5    | 10.1.2.0/24    |
| 10.1.3.5    | 10.1.0.0/16    |
| 10.9.9.9    | 10.0.0.0/8     |
| 8.8.8.8     | 0.0.0.0/0      |
| 10.1.2.0    | 10.1.2.0/24    |

### 6.3 Router Forwarding Procedure

On receiving packet `P` on interface `in_if`:

1. If router status ≠ ONLINE → drop `DEVICE_OFFLINE`.
2. If `P.dst_ip` equals any of the router's own interface addresses →
   **deliver locally** (status `DELIVERED`, destination is router).
3. `ttl' = P.ttl - 1`. If `ttl' <= 0` → drop `TTL_EXPIRED` at this
   router (record ICMP time-exceeded note in trace; no reply packet is
   simulated in v1 except in traceroute mode, §9.2).
4. Route lookup (LPM). None → drop `NO_ROUTE`.
5. Determine L2 next-hop IP: `route.next_hop` or, if connected,
   `P.dst_ip`.
6. Egress interface must be operationally up (§3.1) → else drop
   `INTERFACE_DOWN` (admin down) or `LINK_DOWN` (link/peer issue).
7. ARP resolve next-hop IP on egress interface (§7) → failure drops
   `ARP_FAILED`.
8. Emit frame `src_mac=egress.mac, dst_mac=resolved_mac` with
   `P.with_ttl(ttl')` onto the link.

### 6.4 Server (End Host) Behaviour

- **Sending:** if `dst_ip` is in the subnet of the egress interface →
  ARP for `dst_ip` directly; else ARP for the default gateway. No
  gateway configured and destination off-subnet → drop `NO_ROUTE` at
  source.
- **Receiving:** if `dst_ip` matches one of its addresses → `DELIVERED`;
  otherwise drop `NOT_FOR_ME` (servers do not forward).
- Servers do not decrement TTL.

## 7. Simulated ARP

ARP is explicit so learners can see L3→L2 resolution.

### 7.1 Tables

```
ArpEntry: ip, mac, interface, learned_at, expires_at, entry_type (DYNAMIC|STATIC)
```

- Each router and server has an `ArpTable` per device.
- Default timeout: 300 s of *simulation time* (configurable 10–3600).
- Static entries never expire.

### 7.2 Resolution Algorithm

To resolve `target_ip` out of interface `egress`:

1. If a non-expired entry exists → use it (trace: `ARP cache hit`).
2. Else simulate ARP request: broadcast frame (`dst_mac = ff:ff:…`)
   flooded through the L2 domain reachable from `egress` (through
   switches, honouring port/link/device state, **not** crossing
   routers).
3. The device owning `target_ip` on that L2 domain replies
   (trace: `ARP reply from <host> <mac>`). Both sides cache the
   mapping; switches on the path learn source MACs.
4. No owner reachable → `ARP_FAILED`.

ARP exchanges are recorded as `HopRecord`s of kind `ARP` but **do not**
consume TTL and **do not** count toward the hop limit. They do count
toward traffic counters as 2 frames of 64 bytes (request + reply).

### 7.3 Clearing

ARP tables can be cleared per device via the UI; clearing emits an
`INFO` event.

## 8. Switching

### 8.1 Ports

```
SwitchPort: number (1..N), admin_up, speed_mbps (10|100|1000|10000|25000|40000|100000),
            description, link (via interface)
```

- Port number outside `1..N` → `InvalidPortError` (message includes
  valid range).
- Each port is backed by a `NetworkInterface` named `"port<N>"`.

### 8.2 MAC Address Table

```
MacTableEntry: mac, port, learned_at, expires_at (default 300 s sim time)
```

### 8.3 Forwarding Procedure

On receiving frame `F` on port `in_p`:

1. Switch status ≠ ONLINE → drop `DEVICE_OFFLINE`.
2. `in_p` admin down → drop `PORT_DOWN`.
3. **Learn:** `mac_table[F.src_mac] = in_p` (refresh timer).
4. If `F.dst_mac` is broadcast → flood to all operationally-up ports
   except `in_p`.
5. Else if `F.dst_mac` in `mac_table` →
   - if mapped port == `in_p` → filter (drop silently, reason
     `FILTERED`, `DEBUG` severity);
   - else forward out mapped port (must be operationally up, else
     drop `PORT_DOWN`/`LINK_DOWN`).
6. Else (unknown unicast) → flood to all operationally-up ports except
   `in_p`.

The switch MUST NOT read `F.packet.dst_ip`. Forwarding decisions are
based on `dst_mac` only (fixes original UTS defect).

Flooding in the engine is resolved by following only the branch that
leads to the frame's destination MAC owner; other copies are recorded
as a single `FLOOD` note with the list of egress ports (they do not
create separate trace branches in v1).

### 8.4 Loops

STP is out of scope. To keep the simulation finite:
- The engine keeps a `visited` set of `(device_id, frame_id)` for
  flooded frames and does not re-flood the same frame through the same
  switch.
- Topology service emits a `WARNING` event when a switch loop (cycle
  consisting only of switches) is detected on link creation.

## 9. Simulation Engine

### 9.1 Single Packet

```
simulate(src_device_id, dst_ip, protocol, ttl, size, payload) -> SimulationResult
```

- Source must be a `Server` or `Router` that is ONLINE with at least
  one addressed interface (`InvalidSourceError`).
- Hop limit: `max_hops` (default 64, settings range 8–255) counts L3
  and L2 device visits (ARP excluded). Exceeding → drop `HOP_LIMIT`.
- Result:

```
SimulationResult
  run_id: int
  status: DELIVERED | DROPPED
  drop_reason: DropReason | None
  hops: list[HopRecord]
  path: list[DeviceId]              # devices traversed in order
  total_latency_ms: float           # sum of simulated link latencies
  started_at: datetime
  seed: int

HopRecord
  index: int
  device_id, device_name, device_type
  kind: SEND | ARP | SWITCH | ROUTE | DELIVER | DROP | FLOOD
  ingress: str | None
  egress: str | None
  ttl_in: int | None
  ttl_out: int | None
  matched_route: str | None         # "10.1.0.0/16 via 10.0.0.3 ge0/1"
  reason: str                       # human-readable explanation
```

### 9.2 Traceroute Mode

Runs `simulate` with TTL = 1, 2, … until `DELIVERED` or `max_hops`.
For each `TTL_EXPIRED` drop the result records the router that
expired the packet. Output: list of `(ttl, router_name | "*", status)`.

### 9.3 Drop Reasons (enum `DropReason`)

| Code              | Raised when |
| ----------------- | ----------- |
| `NO_ROUTE`        | No LPM match and no default route; server off-subnet with no gateway. |
| `TTL_EXPIRED`     | TTL reaches 0 after decrement at a router. |
| `DEVICE_OFFLINE`  | Packet would be processed by an OFFLINE/MAINTENANCE device. |
| `LINK_DOWN`       | Link admin down, or peer interface/device not up. |
| `INTERFACE_DOWN`  | Local interface admin down. |
| `PORT_DOWN`       | Switch port admin down (ingress or egress). |
| `ARP_FAILED`      | No device owns the next-hop IP on the L2 segment. |
| `NOT_FOR_ME`      | Server receives packet not addressed to it. |
| `HOP_LIMIT`       | Engine hop guard exceeded (loop protection). |
| `NO_INTERFACE`    | Source has no addressed, up interface. |
| `FILTERED`        | Switch receives frame destined to ingress port (informational). |
| `CONGESTION`      | Traffic flows only: offered load exceeds link capacity (§10.2). |

## 10. Traffic & Utilization Model

**Capacity** (`capacity_mbps`) is configuration. **Utilization** is a
simulated, derived value. They MUST be stored and displayed separately.

### 10.1 Counters

Per device and per link direction, updated only by simulated traffic:

```
tx_packets, rx_packets, tx_bytes, rx_bytes, dropped_packets, drop_reasons{reason: count}
```

### 10.2 Traffic Flows

`TrafficGenerator.run(flow)` where:

```
TrafficFlow: src_device_id, dst_ip, protocol, packet_size, packets_per_second (1..100_000),
             duration_s (1..3600), seed
```

- The engine simulates **one** representative packet to determine the
  path, then accounts `pps × duration` packets on every link on the path
  (no per-packet simulation for large flows).
- Simulated offered load per link direction:
  `load_mbps = Σ(flow.pps × flow.packet_size × 8) / 1_000_000`.
- `utilization_pct = min(100, load_mbps / capacity_mbps × 100)`,
  rounded to 1 decimal.
- If `load_mbps > capacity_mbps`, the excess fraction is counted as
  dropped with reason `CONGESTION` (simulated tail drop) and a
  `WARNING` event is emitted. (`CONGESTION` is the only reason specific
  to flows.)
- Utilization decays to 0 when flows end (sliding window: active flows
  only).

### 10.3 Simulated Latency

`total_latency_ms = Σ link.latency_ms + Σ per_device_processing`,
where processing is 0.01 ms per switch hop and 0.05 ms per router hop.
These constants live in `domain/simulation/constants.py` and are shown
in the UI as "simulated".

## 11. Events

| Category    | Examples                                           | Severity |
| ----------- | -------------------------------------------------- | -------- |
| `CONFIG`    | device added, IP assigned, route added, port disabled | INFO |
| `STATE`     | device offline, link down, link up                 | WARNING / INFO |
| `FORWARD`   | packet forwarded at hop                            | DEBUG |
| `DROP`      | packet dropped (with reason)                       | WARNING |
| `DELIVERY`  | packet delivered                                   | INFO |
| `ARP`       | ARP resolved / failed / table cleared              | DEBUG / WARNING / INFO |
| `TRAFFIC`   | flow started/ended, congestion                     | INFO / WARNING |
| `SYSTEM`    | lab loaded, migration applied, error               | INFO / ERROR |

Event payloads are JSON objects with ids (not names) plus a rendered
`message` string.

## 12. Validation Error Catalogue

| Error class               | Code   | Example message |
| ------------------------- | ------ | --------------- |
| `InvalidAddressError`     | NET001 | `"10.0.0.256" is not a valid IPv4 address.` |
| `InvalidSubnetError`      | NET002 | `"10.0.1.5/24" has host bits set; did you mean 10.0.1.0/24?` |
| `AddressNotInSubnetError` | NET003 | `10.0.2.5 is outside subnet 10.0.1.0/24.` |
| `ReservedAddressError`    | NET004 | `10.0.1.0 is the network address of 10.0.1.0/24.` |
| `DuplicateAddressError`   | NET005 | `10.0.1.10 is already assigned to srv-01 eth0.` |
| `DuplicateMacError`       | NET006 | `02:00:00:00:00:01 is already used by sw-01 port3.` |
| `DuplicateHostnameError`  | NET007 | `Hostname "core-r1" already exists.` |
| `OverlappingSubnetError`  | NET008 | `10.0.0.0/16 overlaps 10.0.1.0/24.` |
| `InvalidNextHopError`     | NET009 | `Next hop 172.16.0.1 is not on a connected subnet of core-r1.` |
| `DuplicateRouteError`     | NET010 | `Route 10.1.0.0/16 via 10.0.0.3 already exists.` |
| `InvalidPortError`        | NET011 | `Port 99 does not exist on sw-01 (valid: 1-24).` |
| `InterfaceInUseError`     | NET012 | `ge0/1 on core-r1 is already linked.` |
| `InvalidLinkError`        | NET013 | `A link must connect two different devices.` |
| `InvalidSourceError`      | NET014 | `Source srv-03 is offline.` |
| `DeviceNotFoundError`     | NET015 | `Device 42 not found.` |

## 13. Reference Test Topology

Used by acceptance tests AT-01..AT-10 (fixture `tests/fixtures/two_router_lab.py`):

```
 srv-a (10.0.1.10/24, gw .1)                     srv-b (10.0.2.10/24, gw .1)
     │ eth0                                            │ eth0
   port1                                             port1
 [ sw-a ] port24 ── ge0/1 [ r1 ] ge0/0 ── ge0/0 [ r2 ] ge0/1 ── port24 [ sw-b ]
                      10.0.1.1/24  10.0.12.1/30  10.0.12.2/30  10.0.2.1/24

 r1 static: 10.0.2.0/24 via 10.0.12.2
 r2 static: 10.0.1.0/24 via 10.0.12.1
```

Expected AT-01 trace (srv-a → 10.0.2.10, TTL 64):

```
0 SEND    srv-a   eth0     ARP for gw 10.0.1.1
1 ARP     r1      ge0/1    reply 10.0.1.1 is-at <r1.ge0/1.mac>
2 SWITCH  sw-a    port1→port24  dst_mac learned/flooded
3 ROUTE   r1      ge0/1→ge0/0  10.0.2.0/24 via 10.0.12.2  TTL 64→63
4 ARP     r2      ge0/0    reply 10.0.12.2
5 ROUTE   r2      ge0/0→ge0/1  10.0.2.0/24 connected     TTL 63→62
6 ARP     srv-b   eth0     reply 10.0.2.10
7 SWITCH  sw-b    port24→port1
8 DELIVER srv-b   eth0     TTL 62
```

(Exact indices may differ; tests assert on status, drop reason, path
and TTL values, not on index numbers.)
