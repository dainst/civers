#!/usr/bin/env python3
"""
Storage Verification Script

Verifies that the CIVERS Web Interface REST API is running and working.
Supports two modes:
1. Passive (default): Checks API health and displays existing archived URLs/snapshots.
2. Active (via --upload): Generates mock artifacts, uploads them, and verifies retrieval.

Usage:
    python scripts/verify_storage.py [--api-url URL] [--upload] [-v]
"""

import argparse
import requests
import sys
import json
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime, timezone

# Add project root and scripts directory to python path for imports
scripts_dir = Path(__file__).resolve().parent
repo_root = scripts_dir.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from config_loader import load_script_config, get_web_interface_url


def check_web_interface_health(api_url: str) -> bool:
    """Check if the Web Interface is running and healthy."""
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ Web Interface healthy at {api_url}")
            return True
        else:
            print(f"❌ Web Interface returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Web Interface at {api_url}")
        return False
    except Exception as e:
        print(f"❌ Error checking Web Interface: {e}")
        return False


def get_upload_info(api_url: str) -> dict:
    """Get upload endpoint information."""
    try:
        response = requests.get(f"{api_url}/api/upload/info", timeout=5)
        if response.status_code == 200:
            info = response.json()
            print("✅ Upload endpoint available")
            print(f"   Allowed file types: {info.get('allowed_file_types', [])}")
            return info
        else:
            print(f"❌ Upload info endpoint returned status {response.status_code}")
            return {}
    except Exception as e:
        print(f"❌ Error getting upload info: {e}")
        return {}


def list_urls(api_url: str) -> list:
    """Get list of archived URLs."""
    try:
        response = requests.get(f"{api_url}/api/urls", timeout=10)
        if response.status_code == 200:
            data = response.json()
            urls = data.get("data", data.get("items", []))
            print(f"✅ Found {len(urls)} archived URLs")
            return urls
        else:
            print(f"❌ URLs endpoint returned status {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error listing URLs: {e}")
        return []


def get_snapshots_for_url(api_url: str, url_id: str) -> list:
    """Get snapshots for a specific URL."""
    try:
        response = requests.get(f"{api_url}/api/urls/{url_id}/snapshots", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("data", data.get("items", []))
        else:
            print(f"   ❌ Snapshots endpoint returned status {response.status_code}")
            return []
    except Exception as e:
        print(f"   ❌ Error getting snapshots: {e}")
        return []


def create_sample_artifacts(output_dir: Path, url: str, request_id: str) -> dict[str, Path]:
    """Create sample archive artifacts for testing."""
    artifacts = {}

    # 1. metadata.json
    metadata = {
        "archive_info": {
            "url": url,
            "request_id": request_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "generator": "verify_storage.py",
        },
        "results": {
            "scoop_exit_code": 0,
            "singlefile_exit_code": 0,
            "artifacts_created": ["archive.wacz", "singlefile.html", "document.html", "screenshot.png"]
        }
    }
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))
    artifacts["metadata.json"] = metadata_path

    # 2. singlefile.html
    html_content = f"""<!DOCTYPE html>
<html data-singlefile-generated="true">
<head><meta charset="utf-8"><title>Test - {url}</title><meta data-single-file="true"></head>
<body><h1>Archived Page</h1><p>URL: {url}</p><p>Request ID: {request_id}</p></body>
</html>"""
    singlefile_path = output_dir / "singlefile.html"
    singlefile_path.write_text(html_content)
    artifacts["singlefile.html"] = singlefile_path

    # 3. document.html
    document_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>DOM Snapshot</title></head>
<body><h1>DOM Snapshot</h1><p>URL: {url}</p></body>
</html>"""
    document_path = output_dir / "document.html"
    document_path.write_text(document_html)
    artifacts["document.html"] = document_path

    # 4. screenshot.png (minimal valid 1x1 PNG)
    png_bytes = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x00, 0x00, 0x00, 0x00, 0x3A, 0x7E, 0x9B, 0x55,
        0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41, 0x54,
        0x08, 0xD7, 0x63, 0x60, 0x00, 0x00, 0x00, 0x02, 0x00, 0x01,
        0xE2, 0x21, 0xBC, 0x33,
        0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
        0xAE, 0x42, 0x60, 0x82
    ])
    screenshot_path = output_dir / "screenshot.png"
    screenshot_path.write_bytes(png_bytes)
    artifacts["screenshot.png"] = screenshot_path

    # 5. archive.wacz (minimal valid WACZ)
    wacz_path = output_dir / "archive.wacz"
    with zipfile.ZipFile(wacz_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        datapackage = {
            "profile": "data-package",
            "wacz_version": "1.1.1",
            "title": f"Archive of {url}",
            "created": datetime.now(timezone.utc).isoformat(),
        }
        zf.writestr("datapackage.json", json.dumps(datapackage, indent=2))
        zf.writestr("pages/pages.jsonl", json.dumps({"url": url, "title": "Test"}))
    artifacts["archive.wacz"] = wacz_path

    return artifacts


def run_active_upload_test(api_url: str, verbose: bool = False) -> bool:
    """Run an active verification check: upload mock artifacts and verify retrieval."""
    print("\n📦 Running Active Upload Verification...")
    
    request_id = f"verify_test_{int(datetime.now().timestamp())}"
    test_url = "https://example.com/verify-storage-test"
    
    # Mapping generator local names to expected API names
    api_name_mapping = {
        "metadata.json": "archive_generator_metadata.json",
        "singlefile.html": "singlefile.html",
        "document.html": "document.html",
        "screenshot.png": "screenshot.png",
        "archive.wacz": "archive.wacz"
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        print(f"   Creating mock artifacts in {temp_dir}...")
        artifacts = create_sample_artifacts(temp_path, test_url, request_id)
        
        # Prepare files for multipart form data
        files = []
        for local_name, path in artifacts.items():
            api_name = api_name_mapping[local_name]
            content_type = "application/octet-stream"
            if api_name.endswith(".html"):
                content_type = "text/html"
            elif api_name.endswith(".png"):
                content_type = "image/png"
            elif api_name.endswith(".json"):
                content_type = "application/json"
            
            files.append(
                ("files", (api_name, open(path, "rb"), content_type))
            )
            if verbose:
                print(f"   - Prepared {api_name} ({path.stat().st_size} bytes)")
        
        # Form fields
        data = {
            "url": test_url,
            "request_id": request_id,
            "allow_existing": "true"
        }
        
        # POST multipart upload request
        upload_endpoint = f"{api_url}/api/upload"
        print(f"   Uploading to {upload_endpoint}...")
        try:
            response = requests.post(upload_endpoint, data=data, files=files, timeout=30)
            
            # Close files
            for _, f_tuple in files:
                f_tuple[1].close()
                
            if response.status_code != 200:
                print(f"   ❌ Upload failed with status {response.status_code}: {response.text[:200]}")
                return False
                
            res_data = response.json()
            snapshot_id = res_data.get("snapshot_id", request_id)
            print(f"   ✅ Upload successful! Snapshot ID: {snapshot_id}")
            
        except Exception as e:
            print(f"   ❌ HTTP upload error: {e}")
            return False
            
        # Download and verify bytes
        print("   Verifying uploaded artifacts by downloading them back...")
        all_match = True
        for local_name, path in artifacts.items():
            api_name = api_name_mapping[local_name]
            serve_url = f"{api_url}/api/artifacts/serve?snapshot_id={snapshot_id}&type={api_name}"
            
            try:
                get_response = requests.get(serve_url, timeout=10)
                if get_response.status_code != 200:
                    print(f"   ❌ Failed to fetch {api_name} (HTTP {get_response.status_code})")
                    all_match = False
                    continue
                    
                downloaded_content = get_response.content
                original_content = path.read_bytes()
                
                if downloaded_content == original_content:
                    print(f"   ✅ Verified {api_name} ({len(downloaded_content)} bytes match)")
                else:
                    print(f"   ❌ Content mismatch for {api_name}!")
                    all_match = False
            except Exception as e:
                print(f"   ❌ Error verifying {api_name}: {e}")
                all_match = False
                
        return all_match


def verify_storage(api_url: str, upload: bool = False, verbose: bool = False) -> bool:
    """Run the storage verification checks."""
    print(f"\n{'='*60}")
    print("CIVERS Storage Verification")
    print(f"API URL: {api_url}")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Step 1: Check health
    print("Step 1: Checking Web Interface health...")
    if not check_web_interface_health(api_url):
        return False

    # Step 2: Get upload info
    print("\nStep 2: Checking upload endpoint...")
    upload_info = get_upload_info(api_url)
    if not upload_info:
        print("   ⚠️ Upload endpoint did not respond.")

    # Step 3: Run active check if requested
    if upload:
        print("\nStep 3: Running active upload tests...")
        if not run_active_upload_test(api_url, verbose):
            print("\n" + "="*60)
            print("VERIFICATION RESULT: FAILED ❌")
            print("Upload verification checks did not pass.")
            print("="*60)
            return False

    # Step 4: List archived URLs (for passive inspection)
    print("\nStep 4: Listing archived URLs...")
    urls = list_urls(api_url)

    if not urls:
        print("   ℹ️ No archived URLs found.")
        print("\n" + "="*60)
        print("VERIFICATION RESULT: SUCCESS ✅")
        print("Web Interface is running. Passive verification complete.")
        print("="*60)
        return True

    # Step 5: Show details of first few URLs
    print("\nStep 5: Showing archived URLs and snapshots...")
    total_snapshots = sum(url_item.get("snapshot_count", 0) for url_item in urls)
    
    shown_urls = urls[:5]
    # Ensure our active upload test URL is visible in the output if it was created
    test_url = "https://example.com/verify-storage-test"
    test_url_item = next((u for u in urls if u.get("original_url") == test_url), None)
    if test_url_item and test_url_item not in shown_urls:
        shown_urls.append(test_url_item)

    for url_item in shown_urls:
        url_id = url_item.get("url_id", url_item.get("id", "unknown"))
        original_url = url_item.get("original_url", "unknown")
        snapshot_count = url_item.get("snapshot_count", 0)

        # Highlight if it's the test URL
        label = "📁 [Test Run] " if original_url == test_url else "📁 "
        print(f"\n   {label}{original_url}")
        print(f"      URL ID: {url_id}")
        print(f"      Snapshots: {snapshot_count}")

        if (verbose or original_url == test_url) and snapshot_count > 0:
            snapshots = get_snapshots_for_url(api_url, url_id)
            # Show the most recent snapshot for the test URL, or up to 3 for others in verbose
            max_snaps = 1 if not verbose else 3
            for snap in snapshots[:max_snaps]:
                snap_id = snap.get("snapshot_id", "unknown")
                artifacts = snap.get("available_artifacts", [])
                print(f"      └── Snapshot: {snap_id}")
                print(f"          Artifacts: {artifacts}")

    # Calculate count of remaining urls not shown
    remaining = len(urls) - len(shown_urls)
    if remaining > 0:
        print(f"\n   ... and {remaining} more URLs")

    print("\n" + "="*60)
    print("VERIFICATION RESULT: SUCCESS ✅")
    print(f"Total URLs: {len(urls)}")
    print(f"Total Snapshots: {total_snapshots}")
    print("Storage system is working.")
    print("="*60)
    return True


def main():
    # Load configuration
    config = load_script_config()
    default_url = get_web_interface_url(config)

    parser = argparse.ArgumentParser(description="Verify CIVERS storage system")
    parser.add_argument(
        "--api-url",
        default=default_url,
        help=f"Web Interface API URL (default: {default_url})"
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Perform active mock uploads to verify write capacity end-to-end"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show verbose output including snapshot details"
    )

    args = parser.parse_args()

    success = verify_storage(args.api_url, args.upload, args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
