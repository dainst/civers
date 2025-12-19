"""
Configuration validation module for comprehensive schema and business logic validation.
Provides early failure detection and detailed error reporting for configuration issues.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from pydantic import ValidationError

from .config_data_model import ConfigDataModel, DomainConfig, TransportConfig, KafkaConfig


logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors with detailed context."""
    
    def __init__(self, message: str, validation_errors: Optional[List[str]] = None, file_path: Optional[str] = None):
        self.message = message
        self.validation_errors = validation_errors or []
        self.file_path = file_path
        super().__init__(self.format_error_message())
    
    def format_error_message(self) -> str:
        """Format a comprehensive error message with context."""
        error_msg = f"Configuration validation failed: {self.message}"
        
        if self.file_path:
            error_msg += f"\nFile: {self.file_path}"
        
        if self.validation_errors:
            error_msg += "\nValidation errors:"
            for i, error in enumerate(self.validation_errors, 1):
                error_msg += f"\n  {i}. {error}"
        
        return error_msg


class ConfigValidator:
    """
    Comprehensive configuration validator with business logic checks.
    
    Validates both Pydantic schema compliance and business-specific requirements
    that can't be captured in the data model alone.
    """
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize the configuration validator.
        
        Args:
            strict_mode: If True, treats warnings as errors
        """
        self.strict_mode = strict_mode
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []
    
    def validate_config(self, config: ConfigDataModel, file_path: Optional[str] = None) -> Tuple[bool, List[str], List[str]]:
        """
        Perform comprehensive validation of configuration.
        
        Args:
            config: Configuration to validate
            file_path: Optional path to config file for error reporting
            
        Returns:
            Tuple of (is_valid, errors, warnings)
            
        Raises:
            ConfigValidationError: If validation fails and strict_mode is True
        """
        self.validation_errors = []
        self.validation_warnings = []
        
        # Validate domain configurations
        self._validate_domains(config.domains)
        
        # Validate transport configuration
        self._validate_transport(config.app.transport)
        
        # Validate business logic constraints
        self._validate_business_logic(config)
        
        # Validate mapper consistency
        self._validate_mapper_consistency(config.domains)
        
        # Check for potential issues
        self._check_potential_issues(config)
        
        is_valid = len(self.validation_errors) == 0
        
        if not is_valid and self.strict_mode:
            raise ConfigValidationError(
                "Configuration validation failed",
                validation_errors=self.validation_errors,
                file_path=file_path
            )
        
        return is_valid, self.validation_errors.copy(), self.validation_warnings.copy()
    
    def _validate_domains(self, domains: List[DomainConfig]) -> None:
        """Validate domain configurations."""
        if not domains:
            self.validation_errors.append("No domains configured - at least one domain is required")
            return
        
        domain_names = set()
        
        for i, domain in enumerate(domains):
            domain_prefix = f"Domain {i+1} ({domain.name})"
            
            # Check for duplicate domain names
            if domain.name in domain_names:
                self.validation_errors.append(f"{domain_prefix}: Duplicate domain name")
            domain_names.add(domain.name)
            
            # Validate domain name format
            if not self._is_valid_domain_name(domain.name):
                self.validation_errors.append(f"{domain_prefix}: Invalid domain name format")
            
            # Validate mappings configuration
            if not domain.mappings:
                self.validation_errors.append(f"{domain_prefix}: No mappings configured")
            
            # Check mapping targets for validity
            invalid_targets = self._validate_mapping_targets(domain.mappings)
            if invalid_targets:
                self.validation_warnings.extend([
                    f"{domain_prefix}: Potentially invalid mapping target: {target}" 
                    for target in invalid_targets
                ])
    
    def _validate_transport(self, transport: TransportConfig) -> None:
        """Validate transport configuration."""
        if not transport.enabled:
            self.validation_errors.append("No transports enabled - at least one transport is required")
            return
        
        # Validate Kafka configuration if enabled
        if transport.is_transport_enabled("kafka") and transport.kafka:
            self._validate_kafka_config(transport.kafka)
    
    def _validate_kafka_config(self, kafka: KafkaConfig) -> None:
        """Validate Kafka-specific configuration."""
        if not kafka.bootstrap_servers:
            self.validation_errors.append("Kafka bootstrap_servers cannot be empty")
        
        if not kafka.topics:
            self.validation_errors.append("Kafka topics configuration cannot be empty")
        
        if not kafka.consumer_group:
            self.validation_errors.append("Kafka consumer_group cannot be empty")
        
        # Check for required topic patterns
        required_topic_patterns = ["metadata", "extraction", "status"]
        configured_topics = list(kafka.topics.values())
        
        for pattern in required_topic_patterns:
            if not any(pattern in topic for topic in configured_topics):
                self.validation_warnings.append(
                    f"No Kafka topics contain pattern '{pattern}' - may affect event routing"
                )
    
    def _validate_business_logic(self, config: ConfigDataModel) -> None:
        """Validate business-specific configuration requirements."""
        # Since we now have only one universal mapper, we no longer need to check
        # for mapper type diversity
        
        # Check for reasonable number of domains
        if len(config.domains) > 10:
            self.validation_warnings.append(
                f"Large number of domains ({len(config.domains)}) - "
                "ensure this is intentional as it may impact performance"
            )
    
    def _validate_mapper_consistency(self, domains: List[DomainConfig]) -> None:
        """Validate consistency across mapping configurations."""
        # Check for common target fields across domains
        all_targets = set()
        for domain in domains:
            all_targets.update(domain.mappings.values())
        
        # Validate that common DataCite fields are being mapped
        common_datacite_fields = [
            "titles[0].title", "creators[0].creator_name", "publication_year",
            "descriptions[0].description", "identifiers[0].identifier"
        ]
        
        mapped_common_fields = [field for field in common_datacite_fields if field in all_targets]
        
        if len(mapped_common_fields) < len(common_datacite_fields) * 0.6:  # 60% threshold
            self.validation_warnings.append(
                f"Few common DataCite fields are mapped ({len(mapped_common_fields)}/{len(common_datacite_fields)}) - "
                "consider mapping more standard fields for interoperability"
            )
    
    def _check_potential_issues(self, config: ConfigDataModel) -> None:
        """Check for potential configuration issues that might cause runtime problems."""
        # Check storage configuration
        if config.app.storage:
            storage = config.app.storage
            if storage.backend not in storage.backends:
                self.validation_errors.append(
                    f"Storage backend '{storage.backend}' not found in configured backends"
                )
            
            # Check local file storage path
            if storage.backend == "local_file":
                backend_config = storage.get_backend_config()
                if not backend_config.get("base_path"):
                    self.validation_warnings.append(
                        "Local file storage has no base_path configured - using default"
                    )
    
    def _is_valid_domain_name(self, domain: str) -> bool:
        """Check if domain name follows valid format."""
        if not domain or '.' not in domain:
            return False
        
        # Basic domain validation
        parts = domain.split('.')
        return len(parts) >= 2 and all(len(part) > 0 for part in parts)
    
    def _validate_mapping_targets(self, mappings: Dict[str, str]) -> List[str]:
        """Validate mapping target fields for common issues."""
        invalid_targets = []
        
        for source, target in mappings.items():
            # Check for common target field patterns
            if not any(pattern in target for pattern in [
                "title", "creator", "description", "identifier", "date", 
                "subject", "rights", "publisher", "language"
            ]):
                invalid_targets.append(f"{source} -> {target}")
        
        return invalid_targets


def validate_configuration_file(file_path: str, strict_mode: bool = True) -> ConfigDataModel:
    """
    Load and validate a configuration file with comprehensive error reporting.
    
    Args:
        file_path: Path to configuration file
        strict_mode: If True, raises exception on validation errors
        
    Returns:
        Validated ConfigDataModel instance
        
    Raises:
        ConfigValidationError: If validation fails
    """
    import yaml
    from .yaml_file_loader_config import YamlFileConfigLoader
    
    validator = ConfigValidator(strict_mode=strict_mode)
    
    try:
        # Load configuration using existing loader
        loader = YamlFileConfigLoader(file_path)
        config = loader.load()
        
        # Perform comprehensive validation
        is_valid, errors, warnings = validator.validate_config(config, file_path)
        
        # Log warnings even if validation passes
        if warnings:
            logger.warning(f"Configuration warnings for {file_path}:")
            for warning in warnings:
                logger.warning(f"  - {warning}")
        
        if errors:
            logger.error(f"Configuration errors for {file_path}:")
            for error in errors:
                logger.error(f"  - {error}")
        
        return config
        
    except ValidationError as e:
        raise ConfigValidationError(
            f"Pydantic validation failed: {e}",
            validation_errors=[str(e)],
            file_path=file_path
        )
    except Exception as e:
        raise ConfigValidationError(
            f"Configuration loading failed: {e}",
            file_path=file_path
        )


def quick_validate_config(config_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Quick validation of configuration dictionary without file I/O.
    
    Args:
        config_dict: Configuration dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    try:
        config = ConfigDataModel(**config_dict)
        validator = ConfigValidator(strict_mode=False)
        is_valid, errors, _ = validator.validate_config(config)
        return is_valid, errors
    except ValidationError as e:
        return False, [str(e)]
    except Exception as e:
        return False, [f"Validation error: {e}"]