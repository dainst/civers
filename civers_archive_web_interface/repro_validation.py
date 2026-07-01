
import re
from typing import List
from pydantic import BaseModel

class ValidationConfig(BaseModel):
    snapshot_id_pattern: str
    snapshot_id_max_length: int
    allowed_artifact_types: List[str]

def validate_snapshot_id(snapshot_id: str, pattern: str, max_length: int):
    if not snapshot_id:
        return "Empty snapshot ID"
    if len(snapshot_id) > max_length:
        return f"Snapshot ID too long: {len(snapshot_id)} > {max_length}"
    if ".." in snapshot_id or "/" in snapshot_id or "\\" in snapshot_id:
        return "Invalid characters (path traversal)"
    
    pat = re.compile(pattern)
    if not pat.match(snapshot_id):
        return f"Snapshot ID '{snapshot_id}' does not match pattern '{pattern}'"
    return "OK"

def validate_artifact_type(artifact_type: str, allowed_types: List[str]):
    if not artifact_type:
        return "Empty artifact type"
    if ".." in artifact_type or "/" in artifact_type or "\\" in artifact_type:
        return "Invalid characters (path traversal)"
    if artifact_type not in allowed_types:
        return f"Artifact type '{artifact_type}' not in allowed types: {allowed_types}"
    return "OK"

# Mock config from validation.yaml
CONFIG = {
    "snapshot_id_pattern": '^req_[a-zA-Z0-9\\-_]+_\\d{8}_\\d{6}$',
    "snapshot_id_max_length": 100,
    "allowed_artifact_types": [
        "archive.wacz",
        "metadata.json",
        "screenshot.png",
        "singlefile.html",
        "warc.file",
        "document.html",
        "dom-snapshot.html",
        "archive_generator_metadata.json"
    ]
}

# Test cases
test_cases = [
    {
        "snapshot_id": "req_test-request-1_20260213_102741",
        "artifact_type": "singlefile.html"
    }
]

for case in test_cases:
    sid = case["snapshot_id"]
    atype = case["artifact_type"]
    print(f"Testing Snapshot ID: {sid}")
    print(f"Result: {validate_snapshot_id(sid, CONFIG['snapshot_id_pattern'], CONFIG['snapshot_id_max_length'])}")
    print(f"Testing Artifact Type: {atype}")
    print(f"Result: {validate_artifact_type(atype, CONFIG['allowed_artifact_types'])}")
    print("-" * 20)
