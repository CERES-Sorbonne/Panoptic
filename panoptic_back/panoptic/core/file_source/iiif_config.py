"""Type-safe configuration for IIIF FileSource metadata.

Provides dataclasses that wrap the JSON metadata stored in FileSource.metadata,
with validation and convenient access patterns.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal, Optional


@dataclass
class IIIFAuth:
    """Authentication configuration for IIIF sources."""
    type: Literal['none', 'bearer', 'basic', 'custom'] = 'none'
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> 'IIIFAuth':
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class IIIFImportHistory:
    """Tracks import success/failure for a IIIF source."""
    last_import_at: Optional[str] = None
    last_import_status: Optional[Literal['success', 'partial', 'failed']] = None
    last_import_count: int = 0
    total_canvases: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> 'IIIFImportHistory':
        if not data:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class IIIFSourceConfig:
    """Complete metadata schema for dtype='iiif' FileSource.

    Stored in FileSource.metadata as JSON. Provides type-safe access
    with validation and sensible defaults for all IIIF-specific settings.
    """
    auth: IIIFAuth = field(default_factory=IIIFAuth)
    headers: Optional[dict[str, str]] = None
    rate_limit_ms: int = 500
    ssl_verify: bool = True
    custom_ca_path: Optional[str] = None
    proxy_url: Optional[str] = None
    import_history: IIIFImportHistory = field(default_factory=IIIFImportHistory)
    metadata_version: int = 1

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict for storage."""
        d = asdict(self)
        if self.auth:
            d['auth'] = self.auth.to_dict()
        if self.import_history:
            d['import_history'] = self.import_history.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> 'IIIFSourceConfig':
        """Parse metadata dict into typed config with validation."""
        if not data:
            return cls()

        parsed = {}
        for k, v in data.items():
            if k not in cls.__dataclass_fields__:
                continue
            if k == 'auth':
                parsed[k] = IIIFAuth.from_dict(v)
            elif k == 'import_history':
                parsed[k] = IIIFImportHistory.from_dict(v)
            else:
                parsed[k] = v

        return cls(**parsed)

    def apply_auth_headers(self, headers: dict) -> dict:
        """Apply authentication to request headers based on config.

        Returns modified headers dict.
        """
        if not self.auth or self.auth.type == 'none':
            return headers

        if self.auth.type == 'bearer' and self.auth.token:
            headers['Authorization'] = f"Bearer {self.auth.token}"
        elif self.auth.type == 'basic' and self.auth.username and self.auth.password:
            import base64
            credentials = base64.b64encode(
                f"{self.auth.username}:{self.auth.password}".encode()
            ).decode()
            headers['Authorization'] = f"Basic {credentials}"
        elif self.auth.type == 'custom' and self.auth.token:
            headers['X-API-Key'] = self.auth.token

        return headers

    def apply_custom_headers(self, headers: dict) -> dict:
        """Apply custom headers from config.

        Returns modified headers dict.
        """
        if self.headers:
            headers.update(self.headers)
        return headers

    def apply_all_headers(self, headers: dict) -> dict:
        """Apply both auth and custom headers.

        Returns modified headers dict.
        """
        headers = self.apply_auth_headers(headers)
        headers = self.apply_custom_headers(headers)
        return headers

    def update_import_history(
        self,
        status: Literal['success', 'partial', 'failed'],
        count: int,
        total: int,
    ) -> None:
        """Update import history with latest result."""
        self.import_history.last_import_at = datetime.utcnow().isoformat() + 'Z'
        self.import_history.last_import_status = status
        self.import_history.last_import_count = count
        self.import_history.total_canvases = total
