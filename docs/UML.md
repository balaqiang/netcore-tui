# NetCore TUI — UML Models

| Field          | Value                              |
| -------------- | ---------------------------------- |
| Owner          | ARCHITECT                          |
| Status         | Approved baseline v1.0             |
| Notation       | Mermaid (renders on GitHub / IDEs) |
| Last updated   | 2026-11-27                         |

Diagrams are the contract for class names, relationships and public
method signatures. Implementations MAY add private helpers but MUST NOT
rename or remove public members shown here without an accepted decision.

---

## 1. Package Diagram

```mermaid
flowchart TB
    subgraph tui[netcore.tui]
        App[NetCoreApp]
        Screens[screens/*]
        Widgets[widgets/*]
    end
    subgraph app[netcore.application]
        Services[services/*]
        DTO[dto]
        Ports[ports]
        Bus[event_bus]
    end
    subgraph dom[netcore.domain]
        Devices[devices/*]
        Topo[topology]
        Sim[simulation/*]
        Errors[errors]
    end
    subgraph infra[netcore.infrastructure]
        Repos[persistence/repositories]
        UoW[unit_of_work]
        Config[config]
    end
    Boot[bootstrap]

    tui --> app
    app --> dom
    infra -.implements.-> Ports
    infra --> dom
    Boot --> tui & app & infra
```

## 2. Core Domain Class Diagram

```mermaid
classDiagram
    direction TB

    class LoggerMixin {
        <<mixin>>
        +logger: Logger
    }

    class NetworkDevice {
        <<abstract>>
        -_id: DeviceId
        -_hostname: str
        -_status: DeviceStatus
        -_interfaces: dict~str, NetworkInterface~
        +id: DeviceId
        +hostname: str
        +status: DeviceStatus
        +device_type: DeviceType*
        +location: str
        +description: str
        +interfaces() tuple~NetworkInterface~
        +get_interface(name: str) NetworkInterface
        +is_online() bool
        +set_status(status: DeviceStatus) None
        +owns_ip(ip: IPv4Address) bool
        +receive(frame: Frame, ingress: str, ctx: ForwardingContext) ForwardDecision*
    }

    class Router {
        +routing_table: RoutingTable
        +arp_table: ArpTable
        +device_type = ROUTER
        +add_static_route(entry: RoutingEntry) None
        +remove_route(entry_id: int) None
        +lookup(dst: IPv4Address) RoutingEntry | None
        +receive(frame, ingress, ctx) ForwardDecision
    }

    class Switch {
        +port_count: int
        +mac_table: MacTable
        +device_type = SWITCH
        +get_port(number: int) SwitchPort
        +set_port_admin(number: int, up: bool) None
        +receive(frame, ingress, ctx) ForwardDecision
    }

    class Server {
        +default_gateway: IPv4Address | None
        +arp_table: ArpTable
        +device_type = SERVER
        +set_default_gateway(ip: IPv4Address | None) None
        +receive(frame, ingress, ctx) ForwardDecision
    }

    class NetworkInterface {
        +name: str
        +mac: MacAddress
        +address: IPv4Interface | None
        +admin_up: bool
        +link_id: LinkId | None
        +assign_address(addr: IPv4Interface) None
        +clear_address() None
    }

    class SwitchPort {
        +number: int
        +speed_mbps: int
        +description: str
        +interface: NetworkInterface
    }

    class Link {
        +id: LinkId
        +endpoint_a: InterfaceRef
        +endpoint_b: InterfaceRef
        +capacity_mbps: int
        +latency_ms: float
        +admin_up: bool
        +peer_of(ref: InterfaceRef) InterfaceRef
        +set_admin(up: bool) None
    }

    class Subnet {
        +id: SubnetId
        +network: IPv4Network
        +name: str
        +gateway: IPv4Address | None
        +parent_id: SubnetId | None
        +contains(ip: IPv4Address) bool
        +usable_hosts() int
        +is_reserved(ip: IPv4Address) bool
    }

    class RoutingEntry {
        +id: int
        +destination: IPv4Network
        +next_hop: IPv4Address | None
        +interface: str
        +route_type: RouteType
        +admin_distance: int
        +metric: int
    }

    class RoutingTable {
        -_entries: list~RoutingEntry~
        +entries() tuple~RoutingEntry~
        +add(entry: RoutingEntry) None
        +remove(entry_id: int) None
        +sync_connected(interfaces) None
        +longest_prefix_match(dst: IPv4Address) RoutingEntry | None
    }

    class MacTable {
        +learn(mac: MacAddress, port: int, now: datetime) None
        +lookup(mac: MacAddress, now: datetime) int | None
        +entries(now: datetime) tuple~MacTableEntry~
        +clear() None
    }

    class ArpTable {
        +get(ip: IPv4Address, now: datetime) MacAddress | None
        +learn(ip, mac, interface, now) None
        +add_static(ip, mac, interface) None
        +entries(now: datetime) tuple~ArpEntry~
        +clear() None
    }

    class Packet {
        <<frozen>>
        +packet_id: int
        +src_ip: IPv4Address
        +dst_ip: IPv4Address
        +protocol: Protocol
        +ttl: int
        +size_bytes: int
        +payload: str
        +with_ttl(ttl: int) Packet
    }

    class Frame {
        <<frozen>>
        +frame_id: int
        +src_mac: MacAddress
        +dst_mac: MacAddress
        +payload: Packet | ArpMessage
        +is_broadcast() bool
    }

    class NetworkTopology {
        <<aggregate root>>
        -_devices: dict~DeviceId, NetworkDevice~
        -_links: dict~LinkId, Link~
        -_subnets: dict~SubnetId, Subnet~
        +add_device(device: NetworkDevice) None
        +remove_device(device_id: DeviceId) RemovalReport
        +get_device(device_id: DeviceId) NetworkDevice
        +find_by_hostname(name: str) NetworkDevice | None
        +add_subnet(subnet: Subnet) None
        +assign_address(device_id, if_name, addr: IPv4Interface) None
        +release_address(device_id, if_name) None
        +connect(a: InterfaceRef, b: InterfaceRef, capacity_mbps: int) Link
        +disconnect(link_id: LinkId) None
        +peer(ref: InterfaceRef) InterfaceRef | None
        +is_operational(ref: InterfaceRef) bool
        +l2_segment(ref: InterfaceRef) frozenset~InterfaceRef~
        +devices() tuple~NetworkDevice~
        +links() tuple~Link~
        +subnets() tuple~Subnet~
    }

    class NetworkEvent {
        <<frozen>>
        +id: int | None
        +timestamp: datetime
        +severity: Severity
        +category: EventCategory
        +device_id: DeviceId | None
        +message: str
        +payload: Mapping~str, object~
    }

    class TrafficEvent {
        <<frozen>>
        +link_id: LinkId | None
        +direction: Direction
        +packets: int
        +bytes: int
        +dropped: int
        +drop_reason: DropReason | None
    }

    LoggerMixin <|-- NetworkDevice
    LoggerMixin <|-- NetworkTopology
    NetworkDevice <|-- Router
    NetworkDevice <|-- Switch
    NetworkDevice <|-- Server
    NetworkDevice "1" *-- "1..*" NetworkInterface
    Switch "1" *-- "1..96" SwitchPort
    SwitchPort "1" --> "1" NetworkInterface
    Router "1" *-- "1" RoutingTable
    RoutingTable "1" *-- "*" RoutingEntry
    Router "1" *-- "1" ArpTable
    Server "1" *-- "1" ArpTable
    Switch "1" *-- "1" MacTable
    NetworkTopology "1" o-- "*" NetworkDevice
    NetworkTopology "1" o-- "*" Link
    NetworkTopology "1" o-- "*" Subnet
    Link "1" --> "2" NetworkInterface : connects
    Frame "1" --> "0..1" Packet
    NetworkEvent <|-- TrafficEvent
```

## 3. Simulation Class Diagram

```mermaid
classDiagram
    class ForwardingEngine {
        -_topology: NetworkTopology
        -_settings: SimulationSettings
        -_rng: Random
        -_clock_start: datetime
        +simulate(request: PacketRequest) SimulationResult
        +traceroute(request: PacketRequest) TracerouteResult
    }
    class ForwardingContext {
        +topology: NetworkTopology
        +now: datetime
        +hops: list~HopRecord~
        +record(hop: HopRecord) None
        +resolve_arp(device, egress, ip) MacAddress | None
    }
    class ForwardDecision {
        <<frozen>>
        +action: ForwardAction
        +egress: tuple~str~
        +frame: Frame | None
        +drop_reason: DropReason | None
    }
    class SimulationResult {
        <<frozen>>
        +run_id: int
        +status: SimulationStatus
        +drop_reason: DropReason | None
        +hops: tuple~HopRecord~
        +path: tuple~DeviceId~
        +total_latency_ms: float
        +started_at: datetime
        +seed: int
    }
    class HopRecord {
        <<frozen>>
        +index: int
        +device_id: DeviceId
        +device_name: str
        +device_type: DeviceType
        +kind: HopKind
        +ingress: str | None
        +egress: str | None
        +ttl_in: int | None
        +ttl_out: int | None
        +matched_route: str | None
        +reason: str
    }
    class TrafficGenerator {
        +run(flow: TrafficFlow, topology, engine) FlowReport
        +utilization(link: Link, active_flows) float
    }
    class TrafficFlow {
        <<frozen>>
        +src_device_id: DeviceId
        +dst_ip: IPv4Address
        +protocol: Protocol
        +packet_size: int
        +packets_per_second: int
        +duration_s: int
    }

    ForwardingEngine --> ForwardingContext : creates
    ForwardingEngine --> SimulationResult : returns
    SimulationResult "1" *-- "*" HopRecord
    ForwardingContext ..> ForwardDecision
    TrafficGenerator --> ForwardingEngine : uses for path
    TrafficGenerator --> TrafficFlow
```

## 4. Enumerations

```mermaid
classDiagram
    class DeviceType { <<enum>> ROUTER SWITCH SERVER }
    class DeviceStatus { <<enum>> ONLINE OFFLINE MAINTENANCE }
    class Protocol { <<enum>> ICMP TCP UDP }
    class RouteType { <<enum>> CONNECTED STATIC DEFAULT }
    class HopKind { <<enum>> SEND ARP SWITCH ROUTE DELIVER DROP FLOOD }
    class ForwardAction { <<enum>> FORWARD DELIVER DROP FLOOD }
    class SimulationStatus { <<enum>> DELIVERED DROPPED }
    class DropReason { <<enum>> NO_ROUTE TTL_EXPIRED DEVICE_OFFLINE LINK_DOWN INTERFACE_DOWN PORT_DOWN ARP_FAILED NOT_FOR_ME HOP_LIMIT NO_INTERFACE FILTERED CONGESTION }
    class Severity { <<enum>> DEBUG INFO WARNING ERROR CRITICAL }
    class EventCategory { <<enum>> CONFIG STATE FORWARD DROP DELIVERY ARP TRAFFIC SYSTEM }
```

## 5. Domain Error Hierarchy

```mermaid
classDiagram
    class NetCoreError { <<exception>> +code: str +message: str }
    class ValidationError
    class NotFoundError
    class ConflictError
    NetCoreError <|-- ValidationError
    NetCoreError <|-- NotFoundError
    NetCoreError <|-- ConflictError
    ValidationError <|-- InvalidAddressError
    ValidationError <|-- InvalidSubnetError
    ValidationError <|-- AddressNotInSubnetError
    ValidationError <|-- ReservedAddressError
    ValidationError <|-- InvalidNextHopError
    ValidationError <|-- InvalidPortError
    ValidationError <|-- InvalidLinkError
    ValidationError <|-- InvalidSourceError
    ConflictError <|-- DuplicateAddressError
    ConflictError <|-- DuplicateMacError
    ConflictError <|-- DuplicateHostnameError
    ConflictError <|-- DuplicateRouteError
    ConflictError <|-- OverlappingSubnetError
    ConflictError <|-- InterfaceInUseError
    NotFoundError <|-- DeviceNotFoundError
    NotFoundError <|-- InterfaceNotFoundError
    NotFoundError <|-- LinkNotFoundError
```

## 6. Application Layer Class Diagram

```mermaid
classDiagram
    class UnitOfWork {
        <<Protocol>>
        +topology: TopologyRepository
        +events: EventRepository
        +simulations: SimulationRepository
        +settings: SettingsRepository
        +__enter__() UnitOfWork
        +__exit__(exc_type, exc, tb) None
        +commit() None
        +rollback() None
    }
    class TopologyRepository {
        <<Protocol>>
        +load() NetworkTopology
        +save(topology: NetworkTopology) None
    }
    class EventRepository {
        <<Protocol>>
        +add(event: NetworkEvent) int
        +query(filter: EventFilter) list~NetworkEvent~
        +prune(keep: int) int
    }
    class EventBus {
        +subscribe(category: EventCategory | None, handler) Unsubscribe
        +publish(event: NetworkEvent) None
    }
    class DeviceService {
        +list_devices(filter) list~DeviceDTO~
        +create_device(req: CreateDeviceRequest) DeviceDTO
        +update_device(req: UpdateDeviceRequest) DeviceDTO
        +delete_device(device_id) RemovalReportDTO
        +set_status(device_id, status) DeviceDTO
    }
    class IpamService {
        +list_subnets() list~SubnetDTO~
        +create_subnet(req) SubnetDTO
        +assign_address(req) InterfaceDTO
        +release_address(device_id, if_name) None
        +next_free_address(subnet_id) str | None
    }
    class RoutingService {
        +routes(router_id) list~RouteDTO~
        +add_static_route(req) RouteDTO
        +remove_route(router_id, route_id) None
        +lookup(router_id, dst_ip) RouteLookupDTO
    }
    class SwitchService {
        +ports(switch_id) list~SwitchPortDTO~
        +set_port_admin(switch_id, port, up) SwitchPortDTO
        +update_port(req) SwitchPortDTO
        +mac_table(switch_id) list~MacEntryDTO~
        +clear_mac_table(switch_id) None
    }
    class TopologyService {
        +snapshot() TopologyDTO
        +connect(req: ConnectRequest) LinkDTO
        +disconnect(link_id) None
        +set_link_admin(link_id, up) LinkDTO
    }
    class SimulationService {
        +send_packet(req: SendPacketRequest) SimulationResultDTO
        +traceroute(req: SendPacketRequest) TracerouteDTO
        +history(limit: int) list~SimulationSummaryDTO~
    }
    class MonitoringService {
        +dashboard_summary() DashboardDTO
        +link_stats() list~LinkStatsDTO~
        +device_stats() list~DeviceStatsDTO~
        +start_flow(req) FlowDTO
        +stop_flow(flow_id) None
        +reset_counters() None
    }
    class EventLogService {
        +query(filter: EventFilterDTO) list~EventDTO~
        +export(filter, fmt, path) ExportResultDTO
    }
    class SettingsService {
        +get() SettingsDTO
        +update(req) SettingsDTO
        +load_sample_lab(name) None
        +reset_lab() None
    }

    UnitOfWork --> TopologyRepository
    UnitOfWork --> EventRepository
    DeviceService --> UnitOfWork
    DeviceService --> EventBus
    IpamService --> UnitOfWork
    RoutingService --> UnitOfWork
    SwitchService --> UnitOfWork
    TopologyService --> UnitOfWork
    SimulationService --> UnitOfWork
    MonitoringService --> EventBus
    EventLogService --> UnitOfWork
    SettingsService --> UnitOfWork
```

## 7. Sequence — Packet Delivery (AT-01)

```mermaid
sequenceDiagram
    actor U as User
    participant S as PacketLabScreen
    participant SS as SimulationService
    participant UoW as UnitOfWork
    participant E as ForwardingEngine
    participant A as srv-a
    participant SW as sw-a
    participant R1 as r1
    participant R2 as r2
    participant B as srv-b

    U->>S: fill form, ctrl+enter
    S->>SS: send_packet(req) [worker thread]
    SS->>UoW: topology.load()
    SS->>E: simulate(request)
    E->>A: originate packet (dst off-subnet → gw)
    A->>R1: ARP who-has 10.0.1.1 (via sw-a flood)
    R1-->>A: ARP reply
    A->>SW: frame dst_mac=r1.ge0/1
    SW->>R1: forward by MAC table
    R1->>R1: TTL 64→63, LPM 10.0.2.0/24 via 10.0.12.2
    R1->>R2: frame (after ARP)
    R2->>R2: TTL 63→62, connected 10.0.2.0/24
    R2->>B: frame via sw-b (after ARP)
    B-->>E: DELIVER
    E-->>SS: SimulationResult(DELIVERED)
    SS->>UoW: simulations.add, events.add, commit
    SS-->>S: SimulationResultDTO
    S-->>U: render hop trace
```

## 8. Sequence — Assign IP with Validation Failure

```mermaid
sequenceDiagram
    actor U as User
    participant M as AssignAddressModal
    participant IS as IpamService
    participant T as NetworkTopology
    U->>M: enter 10.0.1.10/24, submit
    M->>IS: assign_address(req)
    IS->>T: assign_address(dev, eth0, 10.0.1.10/24)
    T-->>IS: raise DuplicateAddressError(NET005)
    IS-->>M: raise ApplicationError(code=NET005, message)
    M-->>U: inline error + toast
```

## 9. State Machines

### 9.1 Device Status

```mermaid
stateDiagram-v2
    [*] --> ONLINE : created
    ONLINE --> OFFLINE : set_status / failure injection
    ONLINE --> MAINTENANCE : set_status
    OFFLINE --> ONLINE : set_status
    MAINTENANCE --> ONLINE : set_status
    OFFLINE --> MAINTENANCE : set_status
    MAINTENANCE --> OFFLINE : set_status
    ONLINE --> [*] : delete
    OFFLINE --> [*] : delete
    MAINTENANCE --> [*] : delete
```

### 9.2 Packet Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Created
    Created --> Resolving : needs L2 next hop
    Resolving --> InTransit : ARP ok
    Resolving --> Dropped : ARP_FAILED
    InTransit --> AtSwitch
    InTransit --> AtRouter
    InTransit --> AtHost
    AtSwitch --> InTransit : forward / flood
    AtSwitch --> Dropped : PORT_DOWN / DEVICE_OFFLINE / LINK_DOWN
    AtRouter --> Resolving : TTL ok, route found
    AtRouter --> Dropped : TTL_EXPIRED / NO_ROUTE / DEVICE_OFFLINE
    AtRouter --> Delivered : dst is router
    AtHost --> Delivered : dst matches
    AtHost --> Dropped : NOT_FOR_ME
    Delivered --> [*]
    Dropped --> [*]
```

## 10. Entity-Relationship (SQLite schema)

```mermaid
erDiagram
    devices ||--o{ interfaces : has
    devices ||--o{ routes : has
    devices ||--o{ arp_entries : has
    devices ||--o{ mac_entries : has
    interfaces ||--o| links : "endpoint a/b"
    subnets ||--o{ interfaces : "contains address"
    subnets ||--o{ subnets : parent
    simulation_runs ||--o{ hop_records : has
    devices ||--o{ events : about
    links ||--o{ traffic_counters : has
    devices ||--o{ traffic_counters : has

    devices {
        INTEGER id PK
        TEXT hostname UK "COLLATE NOCASE"
        TEXT device_type "ROUTER|SWITCH|SERVER"
        TEXT status
        TEXT location
        TEXT description
        TEXT default_gateway "servers only"
        INTEGER port_count "switches only"
        TEXT created_at
        TEXT updated_at
    }
    interfaces {
        INTEGER id PK
        INTEGER device_id FK
        TEXT name "UK(device_id,name)"
        TEXT mac UK
        TEXT ip_address UK "nullable"
        INTEGER prefix_len
        INTEGER subnet_id FK
        INTEGER admin_up
        INTEGER port_number "switch ports"
        INTEGER speed_mbps
        TEXT description
    }
    links {
        INTEGER id PK
        INTEGER interface_a_id FK,UK
        INTEGER interface_b_id FK,UK
        INTEGER capacity_mbps
        REAL latency_ms
        INTEGER admin_up
    }
    subnets {
        INTEGER id PK
        TEXT cidr UK
        TEXT name
        TEXT gateway
        INTEGER parent_id FK
    }
    routes {
        INTEGER id PK
        INTEGER device_id FK
        TEXT destination
        TEXT next_hop
        TEXT interface_name
        TEXT route_type
        INTEGER admin_distance
        INTEGER metric
    }
    arp_entries {
        INTEGER id PK
        INTEGER device_id FK
        TEXT ip
        TEXT mac
        TEXT interface_name
        TEXT entry_type
        TEXT expires_at
    }
    mac_entries {
        INTEGER id PK
        INTEGER device_id FK
        TEXT mac
        INTEGER port_number
        TEXT expires_at
    }
    events {
        INTEGER id PK
        TEXT timestamp
        TEXT severity
        TEXT category
        INTEGER device_id FK "ON DELETE SET NULL"
        TEXT message
        TEXT payload_json
    }
    simulation_runs {
        INTEGER id PK
        TEXT started_at
        INTEGER src_device_id
        TEXT dst_ip
        TEXT protocol
        INTEGER ttl
        INTEGER size_bytes
        TEXT status
        TEXT drop_reason
        REAL total_latency_ms
        INTEGER seed
    }
    hop_records {
        INTEGER id PK
        INTEGER run_id FK
        INTEGER hop_index
        INTEGER device_id
        TEXT kind
        TEXT ingress
        TEXT egress
        INTEGER ttl_in
        INTEGER ttl_out
        TEXT matched_route
        TEXT reason
    }
    traffic_counters {
        INTEGER id PK
        INTEGER device_id FK
        INTEGER link_id FK
        TEXT direction
        INTEGER packets
        INTEGER bytes
        INTEGER dropped
    }
    settings {
        TEXT key PK
        TEXT value
    }
    schema_migrations {
        INTEGER version PK
        TEXT applied_at
    }
```

## 11. Use Case Diagram (summary)

```mermaid
flowchart LR
    Admin((Network<br/>Administrator))
    Admin --> UC1[Manage devices]
    Admin --> UC2[Manage subnets & IPs]
    Admin --> UC3[Configure routes]
    Admin --> UC4[Manage switch ports]
    Admin --> UC5[Connect / fail links]
    Admin --> UC6[View topology]
    Admin --> UC7[Simulate packet / traceroute]
    Admin --> UC8[Generate traffic & monitor]
    Admin --> UC9[Review event logs]
    Admin --> UC10[Configure settings / load lab]
    UC7 -.includes.-> UCa[Resolve ARP]
    UC7 -.includes.-> UCb[Longest prefix match]
    UC8 -.includes.-> UC7
```
