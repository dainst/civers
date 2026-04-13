import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path("/home/sammar/Schreibtisch/dainst/daisnt_cviers_github/civers_individual_repos/civers_archive_web_interface")
sys.path.append(str(project_root))

from configs import YamlFileConfigLoader
from app.storage import create_storage_service

def diagnose():
    os.chdir(str(project_root))
    print(f"Current Working Directory: {os.getcwd()}")
    
    loader = YamlFileConfigLoader()
    print(f"Detected Environment: {loader.environment}")
    
    config = loader.load()
    print(f"Configured Storage Type: {config.storage.type}")
    
    storage_service = create_storage_service(config)
    storage_path = storage_service.provider.storage_path
    print(f"Resolved Provider Storage Path: {storage_path}")
    print(f"Absolute Provider Storage Path: {storage_path.absolute()}")
    print(f"Resolved (Path.resolve()) Storage Path: {storage_path.resolve()}")
    
    # Check if this matches standard DB entry prefix
    db_prefix = "/home/sammar/Schreibtisch/dainst/daisnt_cviers_github/civers_individual_repos/civers_archive_web_interface/archives"
    print(f"Matches DB Prefix: {str(storage_path.resolve()).startswith(db_prefix)}")

if __name__ == "__main__":
    diagnose()
