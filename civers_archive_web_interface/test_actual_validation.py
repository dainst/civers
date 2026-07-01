import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path("/home/sammar/Schreibtisch/dainst/daisnt_cviers_github/civers_individual_repos/civers_archive_web_interface")
sys.path.append(str(project_root))

from configs import YamlFileConfigLoader
from app.utils.security import (
    validate_snapshot_id, 
    validate_artifact_type, 
    validate_file_path,
    SecurityValidationError
)

def test_full_validation():
    loader = YamlFileConfigLoader()
    config = loader.load()
    validation_config = config.validation
    
    snapshot_id = "req_test-request-1_20260213_102741"
    artifact_type = "singlefile.html"
    
    # Mock storage_root and artifact_path
    storage_root = project_root / "archives"
    artifact_path = storage_root / "test_domain" / "test_path" / snapshot_id / artifact_type
    
    print(f"Testing snapshot_id: {snapshot_id}")
    print(f"Testing artifact_type: {artifact_type}")
    print(f"Testing storage_root: {storage_root}")
    print(f"Testing artifact_path: {artifact_path}")
    
    try:
        # 1. Parameter validation
        validated_id = validate_snapshot_id(snapshot_id, validation_config)
        validated_type = validate_artifact_type(artifact_type, validation_config)
        print("SUCCESS: Parameter validation passed")
        
        # 2. Path validation
        # In reality, artifact_path would be obtained from storage service
        validated_path = validate_file_path(artifact_path, storage_root)
        print(f"SUCCESS: Path validation passed: {validated_path}")
        
    except SecurityValidationError as e:
        print(f"FAILURE: Security validation failed: {e}")
    except Exception as e:
        print(f"FAILURE: Unexpected error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_full_validation()
