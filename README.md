# NetCore TUI

Data Center Network Management & Traffic Simulator — an educational,
keyboard-first terminal app (Python + Textual). You act as a network
administrator: manage routers, switches and servers, do IPAM, configure
static routes, connect devices, and simulate packets hop by hop with
explicit ARP, MAC learning, longest-prefix match and TTL.

**Simulation only.** Nothing touches the host network; every traffic
number is simulated and labelled as such.

## Install

Requires Python ≥ 3.12.

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

(or `python -m venv .venv && pip install -e ".[dev]"`)

## Run

```bash
python -m netcore --seed spine-leaf
```

- `--db PATH` — SQLite file (default `$XDG_DATA_HOME/netcore/netcore.db`,
  env `NETCORE_DB`).
- `--seed spine-leaf|two-router` — load a sample lab if the DB is empty.
- `--version`

Minimum terminal size is 100×30. Diagnostic logs go to
`$XDG_STATE_HOME/netcore/netcore.log`; the user-visible audit trail is the
Event Logs screen.

## Keymap

| Key | Action |
| --- | ------ |
| `1`…`9`, `0` | Dashboard, Devices, IPAM, Routing, Switch Ports, Topology, Packet Lab, Traffic, Event Logs, Settings |
| `?` | Help for the current screen |
| `ctrl+p` | Command palette |
| `ctrl+b` | Toggle sidebar |
| `tab` / `shift+tab` | Move focus |
| `escape` | Close modal / leave an input |
| `r` | Refresh |
| `n` / `e` / `d` | New / edit / delete (list screens) |
| `j` `k` `g` `G` | Table down / up / first / last |
| `q` / `ctrl+q` | Quit |

Screen-specific keys: Devices `s` cycle status, `c` clear ARP, `/` search ·
IPAM `a` assign, `x` release · Routing `/` route lookup · Switch Ports
arrows + `space` toggle port, `e` edit, `c` clear MAC table · Topology
arrows/`enter` select device, `l` add link, `u` link up/down, `h` path
highlight, `t` canvas/list · Packet Lab `enter`/`ctrl+t` send, `ctrl+h`
history (enter on a row replays it) · Traffic `f` start flow, `x` stop,
`z` reset counters · Event Logs `enter` detail, `E` export, `t` live tail ·
Settings `ctrl+s` save, `ctrl+l` load sample lab, `ctrl+r` reset lab.

## Sample-lab walkthrough (two-router)

1. `python -m netcore --seed two-router`, press `6` to see the topology:
   `srv-a — sw-a — r1 — r2 — sw-b — srv-b`.
2. Press `7`, choose source `srv-a`, destination `10.0.2.10`, `enter`.
   The trace shows the SEND, the ARP reply from r1, sw-a's MAC lookup,
   r1's route match (TTL 64→63), r2 (63→62), and DELIVER at srv-b.
3. Set TTL to `1` and send again: **DROPPED — TTL_EXPIRED at r1**.
4. Press `2`, select `r2`, press `s` (offline). Send again from Packet Lab:
   **DEVICE_OFFLINE**. Press `s` twice more to bring it back online.
5. Press `6`, `tab` to the link table, select `r1:ge0/0 ↔ r2:ge0/0`, `u`:
   the link is down; packets now drop with **LINK_DOWN**.
6. Press `8`, `f` to start a flow (e.g. 90000 pps × 1000 B = 720 Mbps
   simulated) and watch utilization next to the separate capacity column.
7. Press `9` to read every config change, forwarding decision and drop.

## Development

Quality gates (must all pass):

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
ty check src/netcore
```

Architecture: layered modular monolith (`tui → application → domain`,
infrastructure implements application ports; `bootstrap.py` is the
composition root). Specs live in `docs/`; AI-agent orchestration in
`CLAUDE.md` and `.ai/`.
