"""Pydantic configuration models for CiVers ChangeDetection.

Extends the shared civers_common base config models. Only
``ChangeDetectionStrategyConfig`` (and the per-domain ``change_detection`` field)
is ChangeDetection-specific; everything else follows the shared defaults.
"""

import re
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from civers_common import (
    BaseAppConfig,
    BaseDomainConfig,
    BaseKafkaConfig,
    BaseTransportConfig,
    DomainResolutionMixin,
)

DetectionStrategyName = Literal["css_selector"]
ComparisonAlgorithmName = Literal["simhash", "simple_text"]
RenderingEngineName = Literal["httpx", "playwright"]


class ChangeDetectionStrategyConfig(BaseModel):
    """Per-domain change detection configuration.

    Conditional validation rules:
    - ``css_selectors`` is validated only when ``detection_strategy == "css_selector"``
    - ``simhash_threshold`` range (0–64) is enforced only when ``comparison_algorithm == "simhash"``
    """

    model_config = ConfigDict(extra="ignore")

    # ── Core strategy selection ──────────────────────────────────────────
    detection_strategy: DetectionStrategyName = "css_selector"
    comparison_algorithm: ComparisonAlgorithmName = "simple_text"
    rendering_engine: RenderingEngineName = "httpx"

    # ── CSS selector strategy options ────────────────────────────────────
    css_selectors: list[str] = Field(default=["body"])



    # ── SimHash algorithm options ────────────────────────────────────────
    simhash_threshold: int = Field(default=3)

    # ── Archive interval (optional cooldown) ─────────────────────────────
    archive_interval: str | None = None

    # ── General ──────────────────────────────────────────────────────────
    request_timeout_seconds: int = Field(default=30, ge=1)

    # ── Cross-field validation ───────────────────────────────────────────

    @model_validator(mode="after")
    def validate_strategy_specific_fields(self) -> "ChangeDetectionStrategyConfig":
        """Validate fields conditionally based on the active strategy/algorithm."""
        # css_selectors: only validate when css_selector strategy is active
        if self.detection_strategy == "css_selector":
            if not self.css_selectors:
                raise ValueError(
                    "css_selectors must not be empty when detection_strategy is 'css_selector'"
                )
            cleaned: list[str] = []
            for selector in self.css_selectors:
                stripped = selector.strip()
                if not stripped:
                    raise ValueError(
                        "css_selectors must not contain empty strings"
                    )
                cleaned.append(stripped)
            self.css_selectors = cleaned



        # simhash_threshold: range-check only when simhash algorithm is active
        if self.comparison_algorithm == "simhash":
            if not (0 <= self.simhash_threshold <= 64):
                raise ValueError(
                    f"simhash_threshold must be between 0 and 64, got {self.simhash_threshold}"
                )

        return self

    # ── Archive interval parsing ─────────────────────────────────────────

    _INTERVAL_MULTIPLIERS: ClassVar[dict[str, int]] = {
        "h": 3600,
        "d": 86400,
        "w": 604800,
        "m": 2592000,  # 30 days
    }

    def get_archive_interval_seconds(self) -> int | None:
        """Parse archive_interval string to seconds. Returns None if not set.

        Supported formats: ``<number><unit>`` where unit is
        ``h`` (hours), ``d`` (days), ``w`` (weeks), ``m`` (months/30 days).

        Raises:
            ValueError: If the format is invalid or the value is not positive.
        """
        if not self.archive_interval:
            return None
        match = re.match(r"^(\d+)([hdwm])$", self.archive_interval)
        if not match:
            raise ValueError(
                f"Invalid archive_interval format: '{self.archive_interval}'. "
                "Use <number><unit> e.g. '6h', '7d', '2w', '1m'"
            )
        value = int(match.group(1))
        unit = match.group(2)
        if value <= 0:
            raise ValueError(
                f"archive_interval must be positive, got '{self.archive_interval}'"
            )
        return value * self._INTERVAL_MULTIPLIERS[unit]




class DomainConfig(BaseDomainConfig):
    """ChangeDetection domain config = shared base + per-domain change_detection."""

    change_detection: ChangeDetectionStrategyConfig = Field(
        default_factory=ChangeDetectionStrategyConfig
    )


class KafkaConfig(BaseKafkaConfig):
    """ChangeDetection Kafka config = shared base with service consumer_group default."""

    consumer_group: str = Field(default="change_detection_group")


class TransportConfig(BaseTransportConfig):
    """ChangeDetection transport config = shared base with the CD KafkaConfig type."""

    kafka: KafkaConfig | None = None


class AppConfig(BaseAppConfig):
    """ChangeDetection app config = shared base with CD defaults and transport type."""

    name: str = "change_detection_system"
    version: str = "0.1.0"
    transport: TransportConfig | None = None


class ConfigDataModel(DomainResolutionMixin, BaseModel):
    """Root configuration model for CiVers ChangeDetection.

    Domain resolution (``resolve_domain`` / ``resolve_domain_for_url``) is inherited
    from ``DomainResolutionMixin``. Transport sync is kept locally for now; it will be
    revisited in the Kafka/Transport unification plan.
    """

    model_config = ConfigDict(extra="ignore")

    app: AppConfig
    transport: TransportConfig | None = None
    domains: list[DomainConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_transport(self) -> "ConfigDataModel":
        """Merge root-level transport into app-level transport if needed."""
        if self.transport and not self.app.transport:
            self.app.transport = self.transport
        elif self.app.transport and not self.transport:
            self.transport = self.app.transport
        elif self.transport and self.app.transport:
            if not self.app.transport.kafka and self.transport.kafka:
                self.app.transport.kafka = self.transport.kafka
        return self
