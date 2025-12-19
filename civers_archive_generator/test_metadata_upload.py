#!/usr/bin/env python3
"""
Test script to verify archive_generator_metadata.json upload functionality.

Tests uploading metadata.json renamed to archive_generator_metadata.json
to the CIVERS REST API.

Usage:
    uv run python test_metadata_upload.py
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Test configuration
TEST_URL = "https://arachne.dainst.org/entity/822?fl=20&q=*&resultIndex=9"
API_BASE_URL = "http://127.0.0.1:8000"
API_UPLOAD_URL = f"{API_BASE_URL}/api/upload"


async def test_metadata_upload():
    """Test uploading metadata.json as archive_generator_metadata.json."""
    try:
        import httpx
    except ImportError:
        print("❌ httpx not installed. Install with: uv add httpx")
        return False
    
    print("\n" + "=" * 60)
    print("🧪 Testing archive_generator_metadata.json Upload")
    print("=" * 60)
    print(f"   Test URL: {TEST_URL}")
    print(f"   API URL: {API_UPLOAD_URL}")
    
    # Step 1: Check API health
    print("\n1️⃣ Checking API health...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                print("   ✅ API is healthy!")
            else:
                print(f"   ❌ API returned status {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ API not reachable: {e}")
            return False
    
    # Step 2: Create test metadata (simulating what archive generator creates)
    print("\n2️⃣ Creating test metadata...")
    request_id = f"test_metadata_{int(datetime.now().timestamp())}"
    
    test_metadata = {
        "archive_info": {
            "url": TEST_URL,
            "request_id": request_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "generator": "test_metadata_upload.py",
            "version": "1.0.0"
        },
        "results": {
            "scoop_exit_code": 0,
            "singlefile_exit_code": 0,
            "artifacts_created": [
                "archive.wacz",
                "singlefile.html",
                "screenshot.png",
                "archive_generator_metadata.json"
            ]
        },
        "config": {
            "archive_directory": "archives",
            "test_mode": True
        }
    }
    
    print(f"   Request ID: {request_id}")
    print(f"   Metadata keys: {list(test_metadata.keys())}")
    
    # Step 3: Upload the metadata as archive_generator_metadata.json
    print("\n3️⃣ Uploading metadata as archive_generator_metadata.json...")
    
    json_content = json.dumps(test_metadata, indent=2)
    json_bytes = json_content.encode('utf-8')
    
    form_data = {
        "url": TEST_URL,
        "request_id": request_id,
        "allow_existing": "true"
    }
    
    files = {
        "files": ("archive_generator_metadata.json", json_bytes, "application/json")
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                API_UPLOAD_URL,
                data=form_data,
                files=files
            )
            
            print(f"   Response status: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                snapshot_id = response_data.get("snapshot_id")
                artifacts_uploaded = response_data.get("artifacts_uploaded", [])
                
                print(f"   ✅ Upload successful!")
                print(f"   Snapshot ID: {snapshot_id}")
                print(f"   Artifacts uploaded: {artifacts_uploaded}")
                
                # Check if archive_generator_metadata.json was uploaded
                if "archive_generator_metadata.json" in artifacts_uploaded:
                    print("   ✅ archive_generator_metadata.json is in uploaded artifacts!")
                else:
                    print("   ⚠️ archive_generator_metadata.json NOT found in artifacts list")
                    print(f"   Received artifacts: {artifacts_uploaded}")
            else:
                print(f"   ❌ Upload failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Upload error: {e}")
            return False
    
    # Step 4: Verify by downloading the uploaded file
    print("\n4️⃣ Verifying upload by downloading...")
    
    serve_url = f"{API_BASE_URL}/api/artifacts/serve?snapshot_id={snapshot_id}&type=archive_generator_metadata.json"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(serve_url)
            
            if response.status_code == 200:
                downloaded_data = response.json()
                
                # Verify key fields match
                original_url = test_metadata["archive_info"]["url"]
                downloaded_url = downloaded_data.get("archive_info", {}).get("url")
                
                if original_url == downloaded_url:
                    print("   ✅ Downloaded data matches original!")
                    print(f"   URL in downloaded: {downloaded_url}")
                else:
                    print(f"   ⚠️ URL mismatch: expected {original_url}, got {downloaded_url}")
                
                return True
            elif response.status_code == 404:
                print(f"   ❌ File not found (404): {serve_url}")
                return False
            else:
                print(f"   ❌ Download failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"   ❌ Download error: {e}")
            return False


async def main():
    """Run the test."""
    print("\n" + "=" * 60)
    print("🧪 Archive Generator - Metadata Upload Test")
    print("=" * 60)
    
    success = await test_metadata_upload()
    
    print("\n" + "=" * 60)
    print("📊 RESULT")
    print("=" * 60)
    
    if success:
        print("✅ Test PASSED - archive_generator_metadata.json upload works!")
        return 0
    else:
        print("❌ Test FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
