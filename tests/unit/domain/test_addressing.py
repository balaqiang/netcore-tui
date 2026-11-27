"""NETWORK_SPEC §2 — addressing rules."""

from __future__ import annotations

import random
from ipaddress import IPv4Address, IPv4Network

import pytest

from netcore.domain.addressing import (
    MacAddress,
    MacGenerator,
    is_lab_range,
    parse_ipv4_address,
    parse_ipv4_interface,
    parse_ipv4_network,
    validate_hostname,
)
from netcore.domain.errors import (
    InvalidAddressError,
    InvalidSubnetError,
    InvalidValueError,
)


def test_at02_invalid_ipv4_rejected():
    """AT-02 — 10.0.0.256 is rejected with InvalidAddressError (NET001)."""
    with pytest.raises(InvalidAddressError) as exc:
        parse_ipv4_address("10.0.0.256")
    assert exc.value.code == "NET001"
    assert "10.0.0.256" in exc.value.message


@pytest.mark.parametrize(
    "text",
    [
        "",
        "10.0.0",
        "10.0.0.1.1",
        "010.0.0.1",
        " 10.0.0.1",
        "10.0.0.1 ",
        "a.b.c.d",
        "10..0.1",
        "256.1.1.1",
        "10.0.0.-1",
    ],
)
def test_invalid_addresses(text):
    with pytest.raises(InvalidAddressError):
        parse_ipv4_address(text)


def test_valid_address():
    assert parse_ipv4_address("10.0.1.10") == IPv4Address("10.0.1.10")


@pytest.mark.parametrize(
    "text", ["10.0.0.1/33", "10.0.0.1", "10.0.0.1/", "10.0.0.1/0x"]
)
def test_invalid_interface(text):
    with pytest.raises(InvalidAddressError):
        parse_ipv4_interface(text)


def test_interface_parse():
    iface = parse_ipv4_interface("10.0.1.10/24")
    assert str(iface.network) == "10.0.1.0/24"


def test_subnet_host_bits_suggests_network():
    with pytest.raises(InvalidSubnetError) as exc:
        parse_ipv4_network("10.0.1.5/24")
    assert exc.value.code == "NET002"
    assert "10.0.1.0/24" in exc.value.message


def test_subnet_parse_ok():
    assert parse_ipv4_network("10.0.1.0/24") == IPv4Network("10.0.1.0/24")


def test_subnet_empty():
    with pytest.raises(InvalidSubnetError):
        parse_ipv4_network("")


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        ("AA:BB:CC:DD:EE:F0", "aa:bb:cc:dd:ee:f0"),
        ("aa-bb-cc-dd-ee-f0", "aa:bb:cc:dd:ee:f0"),
        ("aabb.ccdd.eef0", "aa:bb:cc:dd:ee:f0"),
    ],
)
def test_mac_normalisation(text, canonical):
    assert MacAddress.parse(text).value == canonical


@pytest.mark.parametrize("text", ["aa:bb:cc", "zz:bb:cc:dd:ee:ff", "aa:bb-cc:dd:ee:ff"])
def test_mac_invalid(text):
    with pytest.raises(InvalidAddressError):
        MacAddress.parse(text)


def test_broadcast_and_multicast_not_assignable():
    with pytest.raises(InvalidAddressError):
        MacAddress.broadcast().ensure_assignable()
    with pytest.raises(InvalidAddressError):
        MacAddress.parse("01:00:5e:00:00:01").ensure_assignable()


def test_mac_generator_deterministic_and_local():
    a = MacGenerator(random.Random(5)).generate([])
    b = MacGenerator(random.Random(5)).generate([])
    assert a == b
    assert a.value.startswith("02:")
    c = MacGenerator(random.Random(5)).generate([a])
    assert c != a


def test_lab_range():
    assert is_lab_range(IPv4Address("10.1.1.1"))
    assert not is_lab_range(IPv4Address("8.8.8.8"))


@pytest.mark.parametrize("name", ["", "-a", "a-", "a_b", "x" * 64])
def test_hostname_invalid(name):
    with pytest.raises(InvalidValueError):
        validate_hostname(name)


def test_hostname_valid():
    assert validate_hostname("core-r1") == "core-r1"
