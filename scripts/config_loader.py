# config_loader.py
import os
import sys
from pathlib import Path
from typing import Any

# Resolve the repository root directory
REPO_ROOT = Path(__file__).resolve().parent.parent

# Add repo root to python path so civers_common is importable
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from civers_common.configs.loaders import BaseYamlConfigLoader
except ImportError:
    BaseYamlConfigLoader = None


def load_script_config() -> dict[str, Any]:
    """Load the unified CIVERS configuration relative to the repository root.
    
    Reads defaults and environment-specific configs from root configs/ folder,
    expanding env variables and detecting CONFIG_ENVIRONMENT automatically.
    """
    if BaseYamlConfigLoader is None:
        return {}
    
    try:
        # Load configs from the root configs directory
        loader = BaseYamlConfigLoader(config_dir=REPO_ROOT / "configs")
        return loader.load_raw()
    except Exception as e:
        # Fall back to empty dict if configs cannot be loaded or resolved
        import logging
        logging.getLogger(__name__).warning(f"Could not load CIVERS config: {e}. Using defaults.")
        return {}


def get_kafka_bootstrap(config: dict[str, Any], default: str = "localhost:29092") -> str:
    """Retrieve Kafka bootstrap servers from the config dict, with environment variable and default fallbacks."""
    # 1. Try config dictionary: transport.kafka.bootstrap_servers
    bootstrap = (
        config.get("transport", {})
        .get("kafka", {})
        .get("bootstrap_servers")
    )
    if bootstrap:
        return str(bootstrap)
        
    # 2. Check environment variable override directly
    if env_val := os.getenv("KAFKA_BOOTSTRAP_SERVERS"):
        return env_val
        
    return default


def get_web_interface_url(config: dict[str, Any], default: str = "http://localhost:8000") -> str:
    """Retrieve the Web Interface URL from the config dict, with environment variable and default fallbacks."""
    # 1. Try configs: app.metadata.web_interface_url or app.web_interface_url
    app_config = config.get("app", {})
    web_url = (
        app_config.get("metadata", {}).get("web_interface_url")
        or app_config.get("web_interface_url")
    )
    if web_url:
        return str(web_url)
        
    # 2. Check environment variable override directly
    if env_val := os.getenv("CIVERS_API_URL") or os.getenv("WEB_INTERFACE_URL"):
        return env_val
        
    return default
