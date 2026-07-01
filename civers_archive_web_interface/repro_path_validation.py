import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path("/home/sammar/Schreibtisch/dainst/daisnt_cviers_github/civers_individual_repos/civers_archive_web_interface")
sys.path.append(str(project_root))

from app.utils.security import validate_file_path, SecurityValidationError

def test_path_validation():
    # Paths from the database audit
    storage_root = project_root / "archives"
    
    # Path with special characters from DB audit
    artifact_path_str = "/home/sammar/Schreibtisch/dainst/daisnt_cviers_github/civers_individual_repos/civers_archive_web_interface/archives/arachne_test_dainst_org_entity_2003177?fl=20/home/req_test-request-1_20260213_104803/archive.wacz"
    artifact_path = Path(artifact_path_str)
    
    print("Testing Path Validation:")
    print(f"Storage Root: {storage_root}")
    print(f"Artifact Path: {artifact_path}")
    
    try:
        validated = validate_file_path(artifact_path, storage_root)
        print(f"SUCCESS: Validated Path: {validated}")
    except SecurityValidationError as e:
        print(f"FAILURE: SecurityValidationError: {e}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_path_validation()
