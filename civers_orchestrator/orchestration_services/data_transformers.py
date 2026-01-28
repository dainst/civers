"""Data transformers for passing data between workflow steps.

This module provides a flexible framework for transforming data from one step
to another step in a workflow, eliminating the need for hardcoded step-specific
logic in the orchestrator.

Architecture:
- DataTransformer: Base class for all transformers
- Concrete transformers: Implement specific transformation logic
- TRANSFORMERS registry: Maps transformer names to instances
- apply_transformer(): Main entry point for applying transformations
"""

from typing import Any, Dict

from configs.logging_config import get_logger

logger = get_logger(__name__)


class DataTransformer:
    """Base class for data transformers.

    Subclasses must implement the transform() method to perform the actual
    data transformation.
    """

    def transform(
        self,
        value: Any,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Transform a value based on configuration.

        Args:
            value: The input value to transform
            config: Transformer-specific configuration
            context: Execution context (may include orchestrator_config, etc.)

        Returns:
            Transformed value

        Raises:
            ValueError: If transformation fails or value is invalid
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement transform()"
        )


class BuildWebInterfaceUrlTransformer(DataTransformer):
    """Build web interface URL from snapshot_id.

    This transformer constructs a URL pointing to archived content in the
    web interface, using a configurable base URL and URL template.

    Configuration:
        - base_url_config_path: Optional path to base URL in orchestrator config
        - default_base_url: Default base URL if config path not found
        - url_template: Template for constructing URL (supports {base_url}, {value})

    Example:
        transformer_config = {
            "base_url_config_path": "app.metadata.web_interface_url",
            "default_base_url": "http://localhost:8000",
            "url_template": "{base_url}/api/artifacts/serve?snapshot_id={value}&type=dom-snapshot.html"
        }

        result = transformer.transform(
            value="req_123_20250117_120000",
            config=transformer_config,
            context={"orchestrator_config": config}
        )
        # Returns: "http://localhost:8000/api/artifacts/serve?snapshot_id=req_123_20250117_120000&type=dom-snapshot.html"
    """

    def transform(
        self,
        value: Any,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Build web interface URL from snapshot_id.

        Args:
            value: snapshot_id value
            config: Transformer configuration with base_url_config_path, default_base_url, url_template
            context: Execution context with orchestrator_config

        Returns:
            Constructed URL string

        Raises:
            ValueError: If snapshot_id is missing or invalid
        """
        if not value:
            raise ValueError(
                "snapshot_id is required for building web interface URL. "
                "Ensure the source step provides 'snapshot_id' in its results."
            )

        # Validate snapshot_id format (should start with req_)
        if not isinstance(value, str) or not value.startswith("req_"):
            raise ValueError(
                f"Invalid snapshot_id format: {value}. "
                f"Expected format: req_<request_id>_<timestamp>"
            )

        # Get base URL from config or use default
        base_url = config.get("default_base_url", "http://localhost:8000")

        # Try to get base URL from orchestrator config if path is provided
        config_path = config.get("base_url_config_path")
        if config_path:
            orchestrator_config = context.get("orchestrator_config")
            if orchestrator_config:
                try:
                    # Navigate config path like "app.metadata.web_interface_url"
                    obj = orchestrator_config
                    for part in config_path.split("."):
                        if isinstance(obj, dict):
                            obj = obj.get(part)
                        else:
                            obj = getattr(obj, part, None)

                        if obj is None:
                            break

                    # Use the value if found
                    if obj and isinstance(obj, (str, dict)):
                        if isinstance(obj, dict):
                            # If it's a dict, try to get a url or base_url key
                            base_url = obj.get("url", obj.get("base_url", base_url))
                        else:
                            base_url = obj

                except Exception as e:
                    logger.warning(
                        f"Could not access config path '{config_path}': {e}. "
                        f"Using default base URL: {base_url}"
                    )
            else:
                logger.warning("No orchestrator_config found in context.")
        
        logger.info(f"🔍 Resulting base_url for transformation: {base_url}")

        # Apply URL template
        url_template = config.get(
            "url_template",
            "{base_url}/api/artifacts/serve?snapshot_id={value}&type=dom-snapshot.html"
        )

        try:
            url = url_template.format(base_url=base_url, value=value)
        except KeyError as e:
            raise ValueError(
                f"Invalid url_template: missing placeholder {e}. "
                f"Available placeholders: {{base_url}}, {{value}}"
            )

        logger.debug(f"Built web interface URL: {url}")
        return url


class PassThroughTransformer(DataTransformer):
    """Simple pass-through transformer that returns the value unchanged.

    Useful for simple field copying without transformation.

    Example:
        # Copy snapshot_id from archive_generation to metadata_extraction
        transformer_config = {}
        result = transformer.transform(
            value="req_123_20250117_120000",
            config=transformer_config,
            context={}
        )
        # Returns: "req_123_20250117_120000" (unchanged)
    """

    def transform(
        self,
        value: Any,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """Return value unchanged.

        Args:
            value: Input value
            config: Configuration (unused)
            context: Context (unused)

        Returns:
            Input value unchanged
        """
        return value


# Registry of available transformers
# Maps transformer names (as used in configuration) to transformer instances
TRANSFORMERS: Dict[str, DataTransformer] = {
    "build_web_interface_url": BuildWebInterfaceUrlTransformer(),
    "pass_through": PassThroughTransformer(),
}


def apply_transformer(
    transformer_name: str,
    value: Any,
    config: Dict[str, Any],
    context: Dict[str, Any]
) -> Any:
    """Apply a named transformer to a value.

    This is the main entry point for using transformers. It looks up the
    transformer by name in the TRANSFORMERS registry and applies it.

    Args:
        transformer_name: Name of transformer to apply (must be in TRANSFORMERS)
        value: Input value to transform
        config: Transformer-specific configuration
        context: Execution context

    Returns:
        Transformed value

    Raises:
        ValueError: If transformer name is unknown

    Example:
        result = apply_transformer(
            transformer_name="build_web_interface_url",
            value="req_123_20250117_120000",
            config={
                "default_base_url": "http://localhost:8000",
                "url_template": "{base_url}/api/artifacts/serve?snapshot_id={value}"
            },
            context={"orchestrator_config": config}
        )
    """
    transformer = TRANSFORMERS.get(transformer_name)
    if not transformer:
        available = list(TRANSFORMERS.keys())
        raise ValueError(
            f"Unknown transformer: '{transformer_name}'. "
            f"Available transformers: {available}"
        )

    logger.debug(f"Applying transformer '{transformer_name}' to value: {value}")

    try:
        result = transformer.transform(value, config, context)
        logger.debug(f"Transformation successful: {value} → {result}")
        return result
    except Exception as e:
        logger.error(
            f"Transformation failed for transformer '{transformer_name}': {e}"
        )
        raise


def register_transformer(name: str, transformer: DataTransformer) -> None:
    """Register a custom transformer.

    This allows users to add their own custom transformers at runtime.

    Args:
        name: Transformer name (used in configuration)
        transformer: Transformer instance

    Example:
        class MyCustomTransformer(DataTransformer):
            def transform(self, value, config, context):
                return value.upper()

        register_transformer("to_uppercase", MyCustomTransformer())
    """
    if name in TRANSFORMERS:
        logger.warning(f"Overwriting existing transformer: {name}")

    TRANSFORMERS[name] = transformer
    logger.info(f"Registered transformer: {name}")
