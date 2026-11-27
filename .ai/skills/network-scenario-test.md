# Skill: network-scenario-test

## Trigger
Implementing or testing any rule in `docs/NETWORK_SPEC.md`.

## Inputs
- Spec section reference (e.g., §6.3 step 3).
- Reference topology fixture `tests/fixtures/two_router_lab.py`
  (NETWORK_SPEC §13) or a minimal custom topology.

## Steps
1. **Name the rule** in the test docstring with its spec reference and
   AT id if applicable.
2. **Arrange** a topology through `NetworkTopology` public methods only
   (never poke private attributes). Use the `fixed_now` and `rng`
   fixtures for determinism.
3. **Mutate** one condition for failure scenarios (set device offline,
   link down, port admin down, remove route, TTL=1).
4. **Act** via `ForwardingEngine.simulate(...)` or the domain method
   under test.
5. **Assert**, in this order:
   - `result.status` and `result.drop_reason`,
   - `result.path` (device hostnames),
   - TTL values on ROUTE hops (`ttl_in`, `ttl_out`),
   - the dropping/delivering hop's `device_name` and `kind`,
   - for validation errors: `pytest.raises(ErrorType)` and `exc.code`.
6. Parametrize rule tables (e.g., LPM rows, invalid IP strings).

## Example

```python
def test_ttl_expires_at_first_router(two_router_lab, engine_factory):
    """NETWORK_SPEC §6.3 step 3 — AT-07."""
    engine = engine_factory(two_router_lab)
    result = engine.simulate(PacketRequest(src="srv-a", dst_ip="10.0.2.10", ttl=1))
    assert result.status is SimulationStatus.DROPPED
    assert result.drop_reason is DropReason.TTL_EXPIRED
    assert result.hops[-1].device_name == "r1"
```

## Checks
- Test fails if the rule is removed from the implementation.
- No reliance on hop index numbers (they may change with ARP details).
