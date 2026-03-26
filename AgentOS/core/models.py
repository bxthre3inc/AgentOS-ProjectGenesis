from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime

@dataclass
class TaskPayload:
    """Schema for various task-specific payloads."""
    command: Optional[str] = None
    arguments: dict[str, Any] = field(default_factory=dict)
    # Strategy specific
    company_id: Optional[str] = None
    new_state: Optional[str] = None
    pipeline_source: Optional[str] = None
    # Corporate specific
    amount: Optional[float] = None
    currency: str = "USD"
    department: str = "general"

@dataclass
class TaskContext:
    """Canonical Task Context Object (TCO)."""
    task_id: str
    tenant: str
    priority: int = 5
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    payload: dict = field(default_factory=dict)
    status: str = "pending"
    error: Optional[str] = None

    def __post_init__(self):
        VALID_TENANTS = {"tenant_zero", "product_alpha", "subsidiary_beta", "generic_template", "bxthre3_inc"}
        if self.tenant not in VALID_TENANTS:
            raise ValueError(f"Invalid tenant '{self.tenant}'. Must be one of {VALID_TENANTS}")

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}
