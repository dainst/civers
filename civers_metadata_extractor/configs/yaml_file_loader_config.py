import yaml
import os
import logging
from typing import Optional
from pydantic import ValidationError

from configs import ConfigLoaderInterface
from configs.config_data_model import ConfigDataModel


logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Custom exception for configuration loading and validation errors."""
    
    def __init__(self, message: str, file_path: Optional[str] = None, original_error: Optional[Exception] = None):
        self.file_path = file_path
        self.original_error = original_error
        
        error_msg = f"Configuration error: {message}"
        if file_path:
            error_msg += f" (file: {file_path})"
        if original_error:
            error_msg += f" (caused by: {original_error})"
            
        super().__init__(error_msg)


class YamlFileConfigLoader(ConfigLoaderInterface):
    """Enhanced YAML configuration loader with comprehensive error handling."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
    
    def load(self) -> ConfigDataModel:
        """Load configuration from YAML file with detailed error reporting."""
        try:
            # Validate file exists and is readable
            self._validate_file_access()
            
            # Load and parse YAML
            with open(self.file_path, "r", encoding="utf-8") as file:
                raw_data = yaml.safe_load(file)
            
            # Validate YAML content
            if raw_data is None:
                raise ConfigurationError(
                    f"Configuration file is empty or contains only comments",
                    file_path=self.file_path
                )
            
            if not isinstance(raw_data, dict):
                raise ConfigurationError(
                    f"Configuration must be a YAML object/dictionary, got {type(raw_data).__name__}",
                    file_path=self.file_path
                )
            
            # Create and validate configuration model
            config_data = ConfigDataModel(**raw_data)
            
            logger.info(f"Successfully loaded configuration from {self.file_path}")
            logger.debug(f"Configuration contains {len(config_data.domains)} domains")
            
            return config_data
            
        except FileNotFoundError as e:
            raise ConfigurationError(
                f"Configuration file not found: {self.file_path}",
                file_path=self.file_path,
                original_error=e
            )
            
        except PermissionError as e:
            raise ConfigurationError(
                f"Permission denied reading configuration file: {self.file_path}",
                file_path=self.file_path,
                original_error=e
            )
            
        except yaml.YAMLError as e:
            # Extract line information if available
            error_msg = f"Invalid YAML syntax in configuration file"
            if hasattr(e, 'problem_mark') and e.problem_mark:
                error_msg += f" at line {e.problem_mark.line + 1}, column {e.problem_mark.column + 1}"
            
            raise ConfigurationError(
                error_msg,
                file_path=self.file_path,
                original_error=e
            )
            
        except ValidationError as e:
            # Format Pydantic validation errors for better readability
            error_details = []
            for error in e.errors():
                field_path = " -> ".join(str(x) for x in error['loc']) if error['loc'] else "root"
                error_details.append(f"{field_path}: {error['msg']}")
            
            error_msg = f"Configuration validation failed:\n" + "\n".join(f"  - {detail}" for detail in error_details)
            
            raise ConfigurationError(
                error_msg,
                file_path=self.file_path,
                original_error=e
            )
            
        except Exception as e:
            raise ConfigurationError(
                f"Unexpected error loading configuration: {str(e)}",
                file_path=self.file_path,
                original_error=e
            )
    
    def _validate_file_access(self) -> None:
        """Validate file exists and has appropriate permissions."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Configuration file does not exist: {self.file_path}")
        
        if not os.path.isfile(self.file_path):
            raise ConfigurationError(
                f"Configuration path is not a file: {self.file_path}",
                file_path=self.file_path
            )
        
        if not os.access(self.file_path, os.R_OK):
            raise PermissionError(f"Cannot read configuration file: {self.file_path}")
        
        # Check file size (prevent loading extremely large files)
        file_size = os.path.getsize(self.file_path)
        max_size = 10 * 1024 * 1024  # 10MB limit
        
        if file_size > max_size:
            raise ConfigurationError(
                f"Configuration file too large ({file_size} bytes, max {max_size} bytes)",
                file_path=self.file_path
            )
        
        # Log security warning for world-readable config files
        file_stat = os.stat(self.file_path)
        if file_stat.st_mode & 0o044:  # World or group readable
            logger.warning(
                f"Configuration file {self.file_path} has broad read permissions "
                f"(mode: {oct(file_stat.st_mode)}) - consider restricting access"
            )