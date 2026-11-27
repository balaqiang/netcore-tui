"""Typed integer identifiers."""

from __future__ import annotations

from typing import NewType

DeviceId = NewType("DeviceId", int)
LinkId = NewType("LinkId", int)
SubnetId = NewType("SubnetId", int)
