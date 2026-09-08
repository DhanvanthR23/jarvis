"""Capability manifest — integrity-verified capability definitions.

The manifest (capabilities.toml) defines what tools exist and their risk tiers.
It is security-sensitive: hashed at startup, compared to a trusted reference,
and a mismatch halts startup. The hash is over raw file bytes to detect any
modification.
"""

import hashlib
from dataclasses import dataclass
from enum import Enum

try:
    import tomllib
except ImportError:
    # Python < 3.11 fallback — should not happen on 3.11+
    raise ImportError('tomllib requires Python 3.11+')


class RiskTier(Enum):
    """Risk classification for a capability."""
    SAFE = 'safe'
    APPROVAL = 'approval'
    DISABLED = 'disabled'


@dataclass
class Capability:
    """A single capability with its risk tier."""
    name: str
    risk_tier: RiskTier
    description: str = ''


@dataclass
class Role:
    """A role definition constraining an agent's capabilities."""
    name: str
    description: str
    allowed_capabilities: list[str]
    max_execution_time: int
    can_mutate: bool
    approval_required: bool = False


class ManifestIntegrityError(Exception):
    """Raised when the manifest hash does not match the trusted reference."""
    pass


class CapabilityManifest:
    """Loads, parses, and integrity-verifies capabilities.toml.

    The hash is computed over the raw file bytes, not the parsed structure,
    to detect any modification including whitespace or comment changes.
    """

    def __init__(self, path: str):
        self.path = path
        self._raw_bytes: bytes = b''
        self._capabilities: dict[str, Capability] = {}
        self._roles: dict[str, Role] = {}
        self._version: str = ''
        self._loaded: bool = False

    def load(self) -> dict:
        """Read and parse the manifest file."""
        with open(self.path, 'rb') as f:
            self._raw_bytes = f.read()
        data = tomllib.loads(self._raw_bytes.decode('utf-8'))

        self._version = data.get('meta', {}).get('version', 'unknown')

        caps = data.get('capabilities', {})
        self._capabilities = {}
        for name, tier_str in caps.items():
            self._capabilities[name] = Capability(
                name=name,
                risk_tier=RiskTier(tier_str),
            )
            
        roles_data = data.get('roles', {})
        self._roles = {}
        for name, role_info in roles_data.items():
            self._roles[name] = Role(
                name=name,
                description=role_info.get('description', ''),
                allowed_capabilities=role_info.get('allowed_capabilities', []),
                max_execution_time=role_info.get('max_execution_time', 60),
                can_mutate=role_info.get('can_mutate', False),
                approval_required=role_info.get('approval_required', False),
            )

        self._loaded = True
        return data

    @property
    def capabilities(self) -> dict[str, Capability]:
        if not self._loaded:
            raise RuntimeError('Manifest not loaded — call load() first')
        return self._capabilities
        
    @property
    def roles(self) -> dict[str, Role]:
        if not self._loaded:
            raise RuntimeError('Manifest not loaded — call load() first')
        return self._roles

    @property
    def version(self) -> str:
        if not self._loaded:
            raise RuntimeError('Manifest not loaded — call load() first')
        return self._version

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of the raw manifest file bytes."""
        if not self._raw_bytes:
            with open(self.path, 'rb') as f:
                self._raw_bytes = f.read()
        return hashlib.sha256(self._raw_bytes).hexdigest()

    def verify_integrity(self, trusted_hash: str) -> bool:
        """Verify the manifest hash matches the trusted reference.

        Returns True if the hash matches, False otherwise.
        A False result should halt startup.
        """
        return self.compute_hash() == trusted_hash


def load_manifest(path: str, trusted_hash: str) -> CapabilityManifest:
    """Load and verify a capability manifest.

    Reads the file, verifies its hash against the trusted reference,
    then parses it. If the hash doesn't match, raises ManifestIntegrityError.

    This ordering (read bytes → verify hash → parse) ensures we never
    act on a tampered manifest.
    """
    manifest = CapabilityManifest(path)

    # Read raw bytes and verify hash BEFORE parsing
    with open(path, 'rb') as f:
        manifest._raw_bytes = f.read()

    if not manifest.verify_integrity(trusted_hash):
        raise ManifestIntegrityError(
            f'Manifest integrity check failed for {path}. '
            f'Expected hash: {trusted_hash}, '
            f'Got: {manifest.compute_hash()}'
        )

    # Only parse after verification passes
    data = tomllib.loads(manifest._raw_bytes.decode('utf-8'))
    manifest._version = data.get('meta', {}).get('version', 'unknown')
    caps = data.get('capabilities', {})
    manifest._capabilities = {
        name: Capability(name=name, risk_tier=RiskTier(tier_str))
        for name, tier_str in caps.items()
    }
    
    roles_data = data.get('roles', {})
    manifest._roles = {
        name: Role(
            name=name,
            description=role_info.get('description', ''),
            allowed_capabilities=role_info.get('allowed_capabilities', []),
            max_execution_time=role_info.get('max_execution_time', 60),
            can_mutate=role_info.get('can_mutate', False),
            approval_required=role_info.get('approval_required', False),
        ) for name, role_info in roles_data.items()
    }
    
    manifest._loaded = True

    return manifest
