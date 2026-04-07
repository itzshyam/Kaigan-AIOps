"""
Mock Cisco Nexus provider for Kaigan AIOps.

Simulates NX-OS JSON API responses for the three core MCP tools.
Raw fixture data is in NX-OS TABLE/ROW format — exactly what the device
API returns. Normalisation converts it to the standard MCPResponse payload
before agents ever see it.

Scenarios
---------
NORMAL            All peers established, interfaces clean, full routing table.
BGP_PEER_DOWN     Primary ISP peer (AS 65002, 203.0.113.2) Idle after Hold
                  Timer Expired. Default route fails over to backup ISP.
INTERFACE_ERRORS  Ethernet1/2 (ISP-A uplink) has high CRC and input errors
                  while the link stays up — the physical-layer cause of the
                  BGP instability.
PARTIAL_TELEMETRY Provider returns incomplete data, simulating a query timeout.

Demo story: call get_bgp_neighbors(BGP_PEER_DOWN) + get_interface_health(INTERFACE_ERRORS)
+ get_routing_table(BGP_PEER_DOWN) together. The agent must correlate that the CRC
errors on Ethernet1/2 (desc: uplink-to-isp-a-203.0.113.2) are the root cause of the
Idle session to 203.0.113.2 (AS 65002) and the default route failover.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from mcp.schema import (
    MCPResponse,
    CIIdentity,
    Completeness,
    ErrorCode,
    LifecycleState,
    ResolutionMethod,
    TopologyTrust,
    CriticalityTier,
)


class Scenario(str, Enum):
    NORMAL = "normal"
    BGP_PEER_DOWN = "bgp_peer_down"
    INTERFACE_ERRORS = "interface_errors"
    PARTIAL_TELEMETRY = "partial_telemetry"


# ---------------------------------------------------------------------------
# CI Identity registry
# In production this is resolved from NetBox / CMDB via the MCP abstraction.
# ---------------------------------------------------------------------------

_TOPOLOGY_VERIFIED_AT = datetime(2026, 4, 7, 1, 0, 0, tzinfo=timezone.utc)

_CI_REGISTRY: dict[str, CIIdentity] = {
    "nexus-core-01": CIIdentity(
        canonical_id="CI-NX-CORE-001",
        canonical_name="nexus-core-01.lab.kaigan.net",
        resolved_by=ResolutionMethod.IP_MATCH,
        identity_confidence=0.98,
        lifecycle_state=LifecycleState.PRODUCTION,
        criticality_tier=CriticalityTier.CRITICAL,
        owning_team="network-core",
        cost_centre="CC-NET-001",
        escalation_contact="netops@kaigan.net",
        source_name="nexus-core-01",
        ipv4_address="10.0.0.1",
        bgp_asn=65001,
        bgp_router_id="10.0.0.1",
        topology_source="netbox",
        topology_trust_tier=TopologyTrust.REALTIME,
        topology_last_verified=_TOPOLOGY_VERIFIED_AT,
    ),
    "nexus-core-02": CIIdentity(
        canonical_id="CI-NX-CORE-002",
        canonical_name="nexus-core-02.lab.kaigan.net",
        resolved_by=ResolutionMethod.IP_MATCH,
        identity_confidence=0.98,
        lifecycle_state=LifecycleState.PRODUCTION,
        criticality_tier=CriticalityTier.CRITICAL,
        owning_team="network-core",
        cost_centre="CC-NET-001",
        escalation_contact="netops@kaigan.net",
        source_name="nexus-core-02",
        ipv4_address="10.0.0.2",
        bgp_asn=65001,
        bgp_router_id="10.0.0.2",
        topology_source="netbox",
        topology_trust_tier=TopologyTrust.REALTIME,
        topology_last_verified=_TOPOLOGY_VERIFIED_AT,
    ),
}


# ---------------------------------------------------------------------------
# Raw NX-OS fixture data
# Agents never see this format — it is normalised before MCPResponse wraps it.
# Format mirrors actual NX-OS JSON output (show bgp summary | json, etc.)
# ---------------------------------------------------------------------------

# -- BGP -------------------------------------------------------------------

_BGP_NORMAL: dict[str, dict] = {
    "nexus-core-01": {
        "TABLE_vrf": {"ROW_vrf": {
            "vrf-name-out": "default",
            "router-id": "10.0.0.1",
            "local-as": "65001",
            "TABLE_af": {"ROW_af": {
                "af-name": "IPv4 Unicast",
                "TABLE_neighbor": {"ROW_neighbor": [
                    {
                        "neighbor-id": "10.255.0.2",
                        "state": "Established",
                        "up/down": "5d14h22m",
                        "msg-rcvd": "48291",
                        "msg-sent": "48265",
                        "tbl-ver": "381",
                        "in-pfx": "8",
                        "using-as": "65001",
                        "last-reset-reason": None,
                        "last-reset-time": None,
                    },
                    {
                        "neighbor-id": "203.0.113.2",
                        "state": "Established",
                        "up/down": "12d03h07m",
                        "msg-rcvd": "128044",
                        "msg-sent": "24103",
                        "tbl-ver": "381",
                        "in-pfx": "142",
                        "using-as": "65002",
                        "last-reset-reason": None,
                        "last-reset-time": None,
                    },
                    {
                        "neighbor-id": "198.51.100.2",
                        "state": "Established",
                        "up/down": "4d18h55m",
                        "msg-rcvd": "41302",
                        "msg-sent": "18204",
                        "tbl-ver": "381",
                        "in-pfx": "138",
                        "using-as": "65003",
                        "last-reset-reason": None,
                        "last-reset-time": None,
                    },
                ]},
            }},
        }},
    },
}

_BGP_PEER_DOWN: dict[str, dict] = {
    "nexus-core-01": {
        "TABLE_vrf": {"ROW_vrf": {
            "vrf-name-out": "default",
            "router-id": "10.0.0.1",
            "local-as": "65001",
            "TABLE_af": {"ROW_af": {
                "af-name": "IPv4 Unicast",
                "TABLE_neighbor": {"ROW_neighbor": [
                    {
                        "neighbor-id": "10.255.0.2",
                        "state": "Established",
                        "up/down": "5d14h24m",
                        "msg-rcvd": "48295",
                        "msg-sent": "48269",
                        "tbl-ver": "379",
                        "in-pfx": "8",
                        "using-as": "65001",
                        "last-reset-reason": None,
                        "last-reset-time": None,
                    },
                    {
                        # Primary ISP (ISP-A) — session lost
                        "neighbor-id": "203.0.113.2",
                        "state": "Idle",
                        "up/down": "00:02:14",
                        "msg-rcvd": "128044",
                        "msg-sent": "24106",
                        "tbl-ver": "0",
                        "in-pfx": "0",
                        "using-as": "65002",
                        "last-reset-reason": "Hold timer expired",
                        "last-reset-time": "00:02:14",
                    },
                    {
                        # Backup ISP (ISP-B) — still up, now carrying default
                        "neighbor-id": "198.51.100.2",
                        "state": "Established",
                        "up/down": "4d18h57m",
                        "msg-rcvd": "41304",
                        "msg-sent": "18206",
                        "tbl-ver": "381",
                        "in-pfx": "138",
                        "using-as": "65003",
                        "last-reset-reason": None,
                        "last-reset-time": None,
                    },
                ]},
            }},
        }},
    },
}

# -- Interfaces ------------------------------------------------------------

_IFACE_NORMAL: dict[str, dict] = {
    "nexus-core-01": {
        "TABLE_interface": {"ROW_interface": [
            {
                "interface": "Ethernet1/1",
                "desc": "uplink-to-spine-01",
                "state": "up",
                "admin_state": "up",
                "eth_speed": "10 Gbps",
                "eth_duplex": "full",
                "eth_mtu": "9216",
                "eth_in_errors": "0",
                "eth_out_errors": "0",
                "eth_crc": "0",
                "eth_in_ifdown_drops": "0",
                "eth_out_ifdown_drops": "0",
            },
            {
                "interface": "Ethernet1/2",
                "desc": "uplink-to-isp-a-203.0.113.2",
                "state": "up",
                "admin_state": "up",
                "eth_speed": "1 Gbps",
                "eth_duplex": "full",
                "eth_mtu": "1500",
                "eth_in_errors": "0",
                "eth_out_errors": "0",
                "eth_crc": "0",
                "eth_in_ifdown_drops": "0",
                "eth_out_ifdown_drops": "0",
            },
            {
                "interface": "Ethernet1/3",
                "desc": "uplink-to-isp-b-198.51.100.2",
                "state": "up",
                "admin_state": "up",
                "eth_speed": "1 Gbps",
                "eth_duplex": "full",
                "eth_mtu": "1500",
                "eth_in_errors": "0",
                "eth_out_errors": "0",
                "eth_crc": "0",
                "eth_in_ifdown_drops": "0",
                "eth_out_ifdown_drops": "0",
            },
            {
                "interface": "Ethernet1/4",
                "desc": "interconnect-to-nexus-core-02",
                "state": "up",
                "admin_state": "up",
                "eth_speed": "10 Gbps",
                "eth_duplex": "full",
                "eth_mtu": "9216",
                "eth_in_errors": "0",
                "eth_out_errors": "0",
                "eth_crc": "0",
                "eth_in_ifdown_drops": "0",
                "eth_out_ifdown_drops": "0",
            },
            {
                "interface": "loopback0",
                "desc": "router-id-10.0.0.1",
                "state": "up",
                "admin_state": "up",
                "eth_speed": "auto",
                "eth_duplex": "auto",
                "eth_mtu": "1500",
                "eth_in_errors": "0",
                "eth_out_errors": "0",
                "eth_crc": "0",
                "eth_in_ifdown_drops": "0",
                "eth_out_ifdown_drops": "0",
            },
        ]},
    },
}

_IFACE_ERRORS: dict[str, dict] = {
    "nexus-core-01": {
        "TABLE_interface": {"ROW_interface": [
            {
                "interface": "Ethernet1/1",
                "desc": "uplink-to-spine-01",
                "state": "up",
                "admin_state": "up",
                "eth_speed": "10 Gbps",
                "eth_duplex": "full",
                "eth_mtu": "9216",
                "eth_in_errors": "0",
                "eth_out_errors": "0",
                "eth_crc": "0",
                "eth_in_ifdown_drops": "0",
                "eth_out_ifdown_drops": "0",
            },
            {
                # ISP-A uplink — link is up but physical-layer errors present.
                # CRC errors indicate a bad cable/optic or duplex mismatch.
                # The errors cause intermittent packet loss which drives Hold
                # Timer Expired on the BGP session to 203.0.113.2.
                "interface": "Ethernet1/2",
                "desc": "uplink-to-isp-a-203.0.113.2",
                "state": "up",
                "admin_state": "up",
                "eth_speed": "1 Gbps",
                "eth_duplex": "full",
                "eth_mtu": "1500",
                "eth_in_errors": "8901",
                "eth_out_errors": "0",
                "eth_crc": "14523",
                "eth_in_ifdown_drops": "0",
                "eth_out_ifdown_drops": "0",
            },
            {
                "interface": "Ethernet1/3",
                "desc": "uplink-to-isp-b-198.51.100.2",
                "state": "up",
                "admin_state": "up",
                "eth_speed": "1 Gbps",
                "eth_duplex": "full",
                "eth_mtu": "1500",
                "eth_in_errors": "0",
                "eth_out_errors": "0",
                "eth_crc": "0",
                "eth_in_ifdown_drops": "0",
                "eth_out_ifdown_drops": "0",
            },
            {
                "interface": "Ethernet1/4",
                "desc": "interconnect-to-nexus-core-02",
                "state": "up",
                "admin_state": "up",
                "eth_speed": "10 Gbps",
                "eth_duplex": "full",
                "eth_mtu": "9216",
                "eth_in_errors": "0",
                "eth_out_errors": "0",
                "eth_crc": "0",
                "eth_in_ifdown_drops": "0",
                "eth_out_ifdown_drops": "0",
            },
            {
                "interface": "loopback0",
                "desc": "router-id-10.0.0.1",
                "state": "up",
                "admin_state": "up",
                "eth_speed": "auto",
                "eth_duplex": "auto",
                "eth_mtu": "1500",
                "eth_in_errors": "0",
                "eth_out_errors": "0",
                "eth_crc": "0",
                "eth_in_ifdown_drops": "0",
                "eth_out_ifdown_drops": "0",
            },
        ]},
    },
}

# -- Routing table ---------------------------------------------------------

_ROUTES_NORMAL: dict[str, dict] = {
    "nexus-core-01": {
        "TABLE_vrf": {"ROW_vrf": {
            "vrf-name-out": "default",
            "TABLE_addrf": {"ROW_addrf": {
                "addrf": "ipv4",
                "TABLE_prefix": {"ROW_prefix": [
                    {
                        "ipprefix": "0.0.0.0/0",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "203.0.113.2",
                            "ifname": "Ethernet1/2",
                            "uptime": "12d03h07m",
                            "pref": "20",
                            "metric": "0",
                            "clientname": "bgp-65001",
                            "best-path": "true",
                            "source-as": "65002",
                        }},
                    },
                    {
                        # Backup default via ISP-B — higher metric, not active
                        "ipprefix": "0.0.0.0/0",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "198.51.100.2",
                            "ifname": "Ethernet1/3",
                            "uptime": "4d18h55m",
                            "pref": "20",
                            "metric": "100",
                            "clientname": "bgp-65001",
                            "best-path": "false",
                            "source-as": "65003",
                        }},
                    },
                    {
                        "ipprefix": "10.0.0.0/24",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "0.0.0.0",
                            "ifname": "Ethernet1/1",
                            "uptime": "5d14h22m",
                            "pref": "0",
                            "metric": "0",
                            "clientname": "direct",
                            "best-path": "true",
                            "source-as": None,
                        }},
                    },
                    {
                        "ipprefix": "10.255.0.0/30",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "0.0.0.0",
                            "ifname": "Ethernet1/4",
                            "uptime": "5d14h22m",
                            "pref": "0",
                            "metric": "0",
                            "clientname": "direct",
                            "best-path": "true",
                            "source-as": None,
                        }},
                    },
                    {
                        "ipprefix": "203.0.113.0/30",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "0.0.0.0",
                            "ifname": "Ethernet1/2",
                            "uptime": "12d03h10m",
                            "pref": "0",
                            "metric": "0",
                            "clientname": "direct",
                            "best-path": "true",
                            "source-as": None,
                        }},
                    },
                    {
                        "ipprefix": "198.51.100.0/30",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "0.0.0.0",
                            "ifname": "Ethernet1/3",
                            "uptime": "4d18h58m",
                            "pref": "0",
                            "metric": "0",
                            "clientname": "direct",
                            "best-path": "true",
                            "source-as": None,
                        }},
                    },
                    {
                        # Specific prefix advertised by ISP-A
                        "ipprefix": "192.0.2.0/24",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "203.0.113.2",
                            "ifname": "Ethernet1/2",
                            "uptime": "12d03h07m",
                            "pref": "20",
                            "metric": "0",
                            "clientname": "bgp-65001",
                            "best-path": "true",
                            "source-as": "65002",
                        }},
                    },
                ]},
            }},
        }},
    },
}

_ROUTES_BGP_PEER_DOWN: dict[str, dict] = {
    "nexus-core-01": {
        "TABLE_vrf": {"ROW_vrf": {
            "vrf-name-out": "default",
            "TABLE_addrf": {"ROW_addrf": {
                "addrf": "ipv4",
                "TABLE_prefix": {"ROW_prefix": [
                    {
                        # Default now via backup ISP — failover active, age resets
                        "ipprefix": "0.0.0.0/0",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "198.51.100.2",
                            "ifname": "Ethernet1/3",
                            "uptime": "00:02:14",
                            "pref": "20",
                            "metric": "100",
                            "clientname": "bgp-65001",
                            "best-path": "true",
                            "source-as": "65003",
                        }},
                    },
                    {
                        "ipprefix": "10.0.0.0/24",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "0.0.0.0",
                            "ifname": "Ethernet1/1",
                            "uptime": "5d14h24m",
                            "pref": "0",
                            "metric": "0",
                            "clientname": "direct",
                            "best-path": "true",
                            "source-as": None,
                        }},
                    },
                    {
                        "ipprefix": "10.255.0.0/30",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "0.0.0.0",
                            "ifname": "Ethernet1/4",
                            "uptime": "5d14h24m",
                            "pref": "0",
                            "metric": "0",
                            "clientname": "direct",
                            "best-path": "true",
                            "source-as": None,
                        }},
                    },
                    {
                        "ipprefix": "203.0.113.0/30",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "0.0.0.0",
                            "ifname": "Ethernet1/2",
                            "uptime": "12d03h12m",
                            "pref": "0",
                            "metric": "0",
                            "clientname": "direct",
                            "best-path": "true",
                            "source-as": None,
                        }},
                    },
                    {
                        "ipprefix": "198.51.100.0/30",
                        "TABLE_path": {"ROW_path": {
                            "ipnexthop": "0.0.0.0",
                            "ifname": "Ethernet1/3",
                            "uptime": "4d19h00m",
                            "pref": "0",
                            "metric": "0",
                            "clientname": "direct",
                            "best-path": "true",
                            "source-as": None,
                        }},
                    },
                    # 192.0.2.0/24 withdrawn — was BGP from AS 65002
                ]},
            }},
        }},
    },
}


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class CiscoNexusMockProvider:
    """
    Mock Cisco Nexus provider.

    Each method returns an MCPResponse with normalised payload.
    The raw NX-OS format is hashed and stored in raw_hash; agents never
    see it directly.

    Usage::

        provider = CiscoNexusMockProvider()
        bgp = provider.get_bgp_neighbors("nexus-core-01", Scenario.BGP_PEER_DOWN)
        iface = provider.get_interface_health("nexus-core-01", Scenario.INTERFACE_ERRORS)
        routes = provider.get_routing_table("nexus-core-01", Scenario.BGP_PEER_DOWN)
    """

    SOURCE = "cisco-nxos-mock"
    _SUPPORTED = frozenset(_CI_REGISTRY.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require(self, device_id: str) -> CIIdentity:
        if device_id not in self._SUPPORTED:
            raise ValueError(
                f"Unknown device {device_id!r}. Supported: {sorted(self._SUPPORTED)}"
            )
        return _CI_REGISTRY[device_id]

    @staticmethod
    def _sha256(raw: dict) -> str:
        return hashlib.sha256(
            json.dumps(raw, sort_keys=True, default=str).encode()
        ).hexdigest()

    @staticmethod
    def _wrap(
        payload: dict,
        raw: dict,
        ci: CIIdentity,
        completeness: Completeness = Completeness.FULL,
        confidence: float = 0.95,
        freshness: str = "realtime",
        error: Optional[ErrorCode] = None,
        error_detail: Optional[str] = None,
        partial_cis: Optional[list[str]] = None,
    ) -> MCPResponse:
        return MCPResponse(
            source=CiscoNexusMockProvider.SOURCE,
            confidence=confidence,
            freshness=freshness,
            completeness=completeness,
            payload=payload,
            raw_hash=CiscoNexusMockProvider._sha256(raw),
            ci_identity=ci,
            error=error,
            error_detail=error_detail,
            partial_cis=partial_cis,
        )

    # ------------------------------------------------------------------
    # Normalisation
    # Converts NX-OS TABLE/ROW structures to the standard payload format.
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_bgp(raw: dict, device_id: str) -> dict:
        vrf = raw["TABLE_vrf"]["ROW_vrf"]
        af = vrf["TABLE_af"]["ROW_af"]
        raw_neighbors = af["TABLE_neighbor"]["ROW_neighbor"]

        neighbors = [
            {
                "peer_ip": n["neighbor-id"],
                "peer_asn": int(n["using-as"]),
                "state": n["state"],
                "session_uptime": n["up/down"],
                "prefixes_received": int(n["in-pfx"]),
                "established": n["state"] == "Established",
                "last_reset_reason": n.get("last-reset-reason"),
                "last_reset_time": n.get("last-reset-time"),
            }
            for n in raw_neighbors
        ]

        established = sum(1 for n in neighbors if n["established"])
        return {
            "device": device_id,
            "local_asn": int(vrf["local-as"]),
            "router_id": vrf["router-id"],
            "vrf": vrf["vrf-name-out"],
            "address_family": af["af-name"],
            "neighbors": neighbors,
            "summary": {
                "total_peers": len(neighbors),
                "established": established,
                "not_established": len(neighbors) - established,
            },
        }

    @staticmethod
    def _normalise_interfaces(raw: dict, device_id: str) -> dict:
        raw_ifaces = raw["TABLE_interface"]["ROW_interface"]

        interfaces = []
        up_count = 0
        errors_detected = False

        for i in raw_ifaces:
            crc = int(i["eth_crc"])
            in_err = int(i["eth_in_errors"])
            out_err = int(i["eth_out_errors"])
            operational = i["state"] == "up"
            has_errors = crc > 0 or in_err > 0 or out_err > 0

            if operational:
                up_count += 1
            if has_errors:
                errors_detected = True

            mtu_raw = i["eth_mtu"]
            interfaces.append({
                "name": i["interface"],
                "description": i.get("desc", ""),
                "admin_state": i["admin_state"],
                "line_protocol": i["state"],
                "speed": i["eth_speed"],
                "mtu": int(mtu_raw) if mtu_raw.isdigit() else None,
                "input_errors": in_err,
                "output_errors": out_err,
                "crc_errors": crc,
                "input_drops": int(i["eth_in_ifdown_drops"]),
                "output_drops": int(i["eth_out_ifdown_drops"]),
                "operational": operational,
                "errors_present": has_errors,
            })

        return {
            "device": device_id,
            "interfaces": interfaces,
            "summary": {
                "total": len(interfaces),
                "up": up_count,
                "down": len(interfaces) - up_count,
                "errors_detected": errors_detected,
            },
        }

    @staticmethod
    def _normalise_routes(raw: dict, device_id: str) -> dict:
        vrf = raw["TABLE_vrf"]["ROW_vrf"]
        prefixes = vrf["TABLE_addrf"]["ROW_addrf"]["TABLE_prefix"]["ROW_prefix"]

        routes = []
        bgp_count = 0
        connected_count = 0
        default_present = False
        default_protocol: Optional[str] = None

        for p in prefixes:
            path = p["TABLE_path"]["ROW_path"]
            prefix = p["ipprefix"]
            protocol = "bgp" if path["clientname"].startswith("bgp") else "connected"
            is_best = path.get("best-path") == "true"

            if protocol == "bgp":
                bgp_count += 1
            else:
                connected_count += 1

            if prefix == "0.0.0.0/0" and is_best:
                default_present = True
                default_protocol = protocol

            src_as = path.get("source-as")
            routes.append({
                "prefix": prefix,
                "protocol": protocol,
                "next_hop": path["ipnexthop"],
                "interface": path["ifname"],
                "metric": int(path["metric"]),
                "preference": int(path["pref"]),
                "age": path["uptime"],
                "source_asn": int(src_as) if src_as else None,
                "best_path": is_best,
            })

        return {
            "device": device_id,
            "vrf": vrf["vrf-name-out"],
            "routes": routes,
            "summary": {
                "total_routes": len(routes),
                "bgp_routes": bgp_count,
                "connected_routes": connected_count,
                "default_route_present": default_present,
                "default_route_protocol": default_protocol,
            },
        }

    # ------------------------------------------------------------------
    # MCP tool methods
    # ------------------------------------------------------------------

    def get_bgp_neighbors(
        self,
        device_id: str,
        scenario: Scenario = Scenario.NORMAL,
    ) -> MCPResponse:
        ci = self._require(device_id)

        if scenario == Scenario.PARTIAL_TELEMETRY:
            # Simulate a mid-query timeout: only iBGP peer returned, ISP peers missing
            partial = copy.deepcopy(_BGP_NORMAL[device_id])
            neighbors = partial["TABLE_vrf"]["ROW_vrf"]["TABLE_af"]["ROW_af"][
                "TABLE_neighbor"
            ]["ROW_neighbor"]
            partial["TABLE_vrf"]["ROW_vrf"]["TABLE_af"]["ROW_af"][
                "TABLE_neighbor"
            ]["ROW_neighbor"] = neighbors[:1]
            return self._wrap(
                payload=self._normalise_bgp(partial, device_id),
                raw=partial,
                ci=ci,
                completeness=Completeness.PARTIAL,
                confidence=0.40,
                freshness="stale",
                error=ErrorCode.PARTIAL_DATA,
                error_detail=(
                    "BGP neighbor query timed out after 1 of 3 neighbours. "
                    "ISP-A (203.0.113.2) and ISP-B (198.51.100.2) missing from response."
                ),
                partial_cis=[
                    f"{device_id}:bgp:203.0.113.2",
                    f"{device_id}:bgp:198.51.100.2",
                ],
            )

        raw = _BGP_PEER_DOWN[device_id] if scenario == Scenario.BGP_PEER_DOWN else _BGP_NORMAL[device_id]
        return self._wrap(
            payload=self._normalise_bgp(raw, device_id),
            raw=raw,
            ci=ci,
            completeness=Completeness.FULL,
            confidence=0.95,
            freshness="realtime",
        )

    def get_interface_health(
        self,
        device_id: str,
        scenario: Scenario = Scenario.NORMAL,
    ) -> MCPResponse:
        ci = self._require(device_id)

        if scenario == Scenario.PARTIAL_TELEMETRY:
            # Only first 2 interfaces returned — Ethernet1/3, Ethernet1/4, loopback0 missing
            partial = copy.deepcopy(_IFACE_NORMAL[device_id])
            partial["TABLE_interface"]["ROW_interface"] = (
                partial["TABLE_interface"]["ROW_interface"][:2]
            )
            return self._wrap(
                payload=self._normalise_interfaces(partial, device_id),
                raw=partial,
                ci=ci,
                completeness=Completeness.PARTIAL,
                confidence=0.45,
                freshness="stale",
                error=ErrorCode.PARTIAL_DATA,
                error_detail=(
                    "Interface poll returned 2 of 5 interfaces. "
                    "Ethernet1/3, Ethernet1/4, loopback0 missing."
                ),
                partial_cis=[
                    f"{device_id}:iface:Ethernet1/3",
                    f"{device_id}:iface:Ethernet1/4",
                    f"{device_id}:iface:loopback0",
                ],
            )

        raw = (
            _IFACE_ERRORS[device_id]
            if scenario == Scenario.INTERFACE_ERRORS
            else _IFACE_NORMAL[device_id]
        )
        return self._wrap(
            payload=self._normalise_interfaces(raw, device_id),
            raw=raw,
            ci=ci,
            completeness=Completeness.FULL,
            confidence=0.95,
            freshness="realtime",
        )

    def get_routing_table(
        self,
        device_id: str,
        scenario: Scenario = Scenario.NORMAL,
    ) -> MCPResponse:
        ci = self._require(device_id)

        if scenario == Scenario.PARTIAL_TELEMETRY:
            # Routing table truncated — only first 3 prefixes returned
            partial = copy.deepcopy(_ROUTES_NORMAL[device_id])
            prefixes = partial["TABLE_vrf"]["ROW_vrf"]["TABLE_addrf"]["ROW_addrf"][
                "TABLE_prefix"
            ]["ROW_prefix"]
            partial["TABLE_vrf"]["ROW_vrf"]["TABLE_addrf"]["ROW_addrf"][
                "TABLE_prefix"
            ]["ROW_prefix"] = prefixes[:3]
            return self._wrap(
                payload=self._normalise_routes(partial, device_id),
                raw=partial,
                ci=ci,
                completeness=Completeness.PARTIAL,
                confidence=0.35,
                freshness="stale",
                error=ErrorCode.PARTIAL_DATA,
                error_detail=(
                    "Routing table query truncated at 3 prefixes. "
                    "Full RIB unavailable — provider timed out."
                ),
                partial_cis=[f"{device_id}:rib:truncated"],
            )

        raw = (
            _ROUTES_BGP_PEER_DOWN[device_id]
            if scenario == Scenario.BGP_PEER_DOWN
            else _ROUTES_NORMAL[device_id]
        )
        return self._wrap(
            payload=self._normalise_routes(raw, device_id),
            raw=raw,
            ci=ci,
            completeness=Completeness.FULL,
            confidence=0.95,
            freshness="realtime",
        )

    def list_devices(self) -> list[str]:
        return sorted(self._SUPPORTED)
