"""Pydantic request schemas for the Laserpointer service."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LaserRequest(BaseModel):
    """Command sent by the controller to aim or disable the laser."""

    x: float = Field(
        description="Normalized horizontal target coordinate. Use -1 with y=-1 to disable the laser.",
    )
    y: float = Field(
        description="Normalized vertical target coordinate. Use -1 with x=-1 to disable the laser.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Controller confidence for the target, stored for diagnostics.",
    )
