from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
from enum import Enum
from datetime import datetime, timezone

class Completeness(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    STALE = "stale"

class ErrorCode(str, Enum):
    TIMEOUT = "timeout"
    AUTH_FAILURE = "auth_failure"
    RATE_LIMITED = "rate_limited"
    PARTIAL_DATA = "partial_data"
    PARSE_FAILURE = "parse_failure"
    UNREACHABLE = "unreachable"
    STALE_CACHE = "stale_cache"
    SCHEMA_MISMATCH = "schema_mismatch"

class LifecycleState(str, Enum):
    PRODUCTION = "production"
    MAINTENANCE = "maintenance"
    DECOMMISSIONING = "decommissioning"
    LAB = "lab"

class ResolutionMethod(str, Enum):
    IP_MATCH = "ip_match"
    MAC_MATCH = "mac_match"
    VRF_IP_MATCH = "vrf_ip_match"
    FUZZY_NAME = "fuzzy_name"
    MANUAL = "manual"
    UNRESOLVED = "unresolved"

class TopologyTrust(str, Enum):
    REALTIME = "realtime"
    RECENT = "recent"
    STALE = "stale"
    UNKNOWN = "unknown"

class CriticalityTier(str, Enum):
    CRITICAL = "critical"    # core routers, internet edge
    HIGH = "high"            # distribution, WAN
    MEDIUM = "medium"        # access, branch
    LOW = "low"              # lab, dev

class CIIdentity(BaseModel):
    # Mandatory
    canonical_id: str
    canonical_name: str
    resolved_by: ResolutionMethod
    identity_confidence: float = Field(ge=0.0, le=1.0)
    lifecycle_state: LifecycleState = LifecycleState.PRODUCTION
    criticality_tier: CriticalityTier = CriticalityTier.MEDIUM
    maintenance_window_active: bool = False
    change_freeze_active: bool = False

    # Maintenance window
    maintenance_window_source: Optional[str] = None
    maintenance_window_verified_at: Optional[datetime] = None
    maintenance_window_end: Optional[datetime] = None
    maintenance_change_ref: Optional[str] = None
    change_freeze_ref: Optional[str] = None

    # Asset ownership
    owning_team: Optional[str] = None
    cost_centre: Optional[str] = None
    escalation_contact: Optional[str] = None

    # Identity
    source_name: str = ""
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = None
    mac_address: Optional[str] = None
    vrf: Optional[str] = None
    vrf_rd: Optional[str] = None
    vni: Optional[str] = None
    aliases: list[str] = []

    # Interface
    interface_canonical_id: Optional[str] = None
    interface_aliases: list[str] = []

    # BGP
    bgp_asn: Optional[int] = None
    bgp_router_id: Optional[str] = None

    # Topology
    topology_source: Optional[str] = None
    topology_trust_tier: Optional[TopologyTrust] = None
    topology_last_verified: Optional[datetime] = None

    # OOBM
    oobm_ip: Optional[str] = None
    oobm_provider: Optional[str] = None

    # Risk flags
    ip_reuse_risk: bool = False
    decommission_flag: bool = False
    last_seen: Optional[datetime] = None

class MCPResponse(BaseModel):
    schema_version: str = "1.0"
    source: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: str
    completeness: Completeness
    payload: dict[str, Any]
    raw_hash: str
    ci_identity: Optional[CIIdentity] = None
    error: Optional[ErrorCode] = None
    error_detail: Optional[str] = None
    partial_cis: Optional[list[str]] = None
    conflict_detected: bool = False
    conflict_sources: Optional[list[str]] = None

    @field_validator('timestamp')
    @classmethod
    def enforce_utc(cls, v):
        if v.tzinfo is None:
            raise ValueError("Timestamp must include timezone — use UTC")
        return v