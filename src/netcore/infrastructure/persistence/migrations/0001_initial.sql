-- NetCore schema v1 (UML.md §10). Forward-only.
CREATE TABLE devices (
    id              INTEGER PRIMARY KEY,
    hostname        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    device_type     TEXT NOT NULL CHECK (device_type IN ('ROUTER','SWITCH','SERVER')),
    status          TEXT NOT NULL CHECK (status IN ('ONLINE','OFFLINE','MAINTENANCE')),
    location        TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    default_gateway TEXT,
    port_count      INTEGER,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE subnets (
    id        INTEGER PRIMARY KEY,
    cidr      TEXT NOT NULL UNIQUE,
    name      TEXT NOT NULL DEFAULT '',
    gateway   TEXT,
    parent_id INTEGER REFERENCES subnets(id) ON DELETE RESTRICT
);

CREATE TABLE interfaces (
    id          INTEGER PRIMARY KEY,
    device_id   INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    name        TEXT NOT NULL,
    mac         TEXT NOT NULL UNIQUE,
    ip_address  TEXT UNIQUE,
    prefix_len  INTEGER CHECK (prefix_len BETWEEN 0 AND 32),
    subnet_id   INTEGER REFERENCES subnets(id) ON DELETE SET NULL,
    admin_up    INTEGER NOT NULL DEFAULT 1 CHECK (admin_up IN (0,1)),
    port_number INTEGER,
    speed_mbps  INTEGER,
    description TEXT NOT NULL DEFAULT '',
    UNIQUE (device_id, name)
);

CREATE TABLE links (
    id             INTEGER PRIMARY KEY,
    interface_a_id INTEGER NOT NULL UNIQUE REFERENCES interfaces(id) ON DELETE CASCADE,
    interface_b_id INTEGER NOT NULL UNIQUE REFERENCES interfaces(id) ON DELETE CASCADE,
    capacity_mbps  INTEGER NOT NULL CHECK (capacity_mbps BETWEEN 1 AND 400000),
    latency_ms     REAL NOT NULL DEFAULT 0.1 CHECK (latency_ms >= 0),
    admin_up       INTEGER NOT NULL DEFAULT 1 CHECK (admin_up IN (0,1)),
    CHECK (interface_a_id <> interface_b_id)
);

CREATE TABLE routes (
    id              INTEGER PRIMARY KEY,
    device_id       INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    route_no        INTEGER NOT NULL,
    insertion_index INTEGER NOT NULL,
    destination     TEXT NOT NULL,
    next_hop        TEXT,
    interface_name  TEXT NOT NULL,
    route_type      TEXT NOT NULL CHECK (route_type IN ('CONNECTED','STATIC','DEFAULT')),
    admin_distance  INTEGER NOT NULL,
    metric          INTEGER NOT NULL DEFAULT 0 CHECK (metric BETWEEN 0 AND 65535),
    UNIQUE (device_id, route_no)
);

CREATE TABLE arp_entries (
    id             INTEGER PRIMARY KEY,
    device_id      INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    ip             TEXT NOT NULL,
    mac            TEXT NOT NULL,
    interface_name TEXT NOT NULL,
    entry_type     TEXT NOT NULL CHECK (entry_type IN ('DYNAMIC','STATIC')),
    learned_at     TEXT,
    expires_at     TEXT
);

CREATE TABLE mac_entries (
    id          INTEGER PRIMARY KEY,
    device_id   INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    mac         TEXT NOT NULL,
    port_number INTEGER NOT NULL,
    learned_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);

CREATE TABLE events (
    id           INTEGER PRIMARY KEY,
    timestamp    TEXT NOT NULL,
    severity     TEXT NOT NULL,
    category     TEXT NOT NULL,
    device_id    INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    message      TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_events_timestamp ON events(timestamp);

CREATE TABLE simulation_runs (
    id               INTEGER PRIMARY KEY,
    started_at       TEXT NOT NULL,
    src_device_id    INTEGER,
    dst_ip           TEXT NOT NULL,
    protocol         TEXT NOT NULL,
    ttl              INTEGER NOT NULL,
    size_bytes       INTEGER NOT NULL,
    status           TEXT NOT NULL,
    drop_reason      TEXT,
    total_latency_ms REAL NOT NULL,
    seed             INTEGER NOT NULL,
    path_json        TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE hop_records (
    id            INTEGER PRIMARY KEY,
    run_id        INTEGER NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    hop_index     INTEGER NOT NULL,
    device_id     INTEGER,
    device_name   TEXT NOT NULL,
    device_type   TEXT NOT NULL,
    kind          TEXT NOT NULL,
    ingress       TEXT,
    egress        TEXT,
    ttl_in        INTEGER,
    ttl_out       INTEGER,
    matched_route TEXT,
    reason        TEXT NOT NULL
);

CREATE TABLE traffic_counters (
    id                INTEGER PRIMARY KEY,
    device_id         INTEGER REFERENCES devices(id) ON DELETE CASCADE,
    link_id           INTEGER REFERENCES links(id) ON DELETE CASCADE,
    direction         TEXT NOT NULL,
    packets           INTEGER NOT NULL DEFAULT 0,
    bytes             INTEGER NOT NULL DEFAULT 0,
    dropped           INTEGER NOT NULL DEFAULT 0,
    drop_reasons_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (device_id, link_id, direction)
);

CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
