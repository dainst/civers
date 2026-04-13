import sys
import os
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to sys.path
project_root = Path("/home/sammar/Schreibtisch/dainst/daisnt_cviers_github/civers_individual_repos/civers_archive_web_interface")
sys.path.append(str(project_root))

from app.main import app

def simulate_download():
    snapshot_id = "req_test-request-1_20260213_102741"
    artifact_type = "singlefile.html"
    
    print(f"Simulating request: /api/artifacts/serve?snapshot_id={snapshot_id}&type={artifact_type}")
    
    with TestClient(app) as client:
        response = client.get(f"/api/artifacts/serve?snapshot_id={snapshot_id}&type={artifact_type}")
    
    print(f"Response Status: {response.status_code}")
    print(f"Response Body: {response.json()}")

if __name__ == "__main__":
    simulate_download()
