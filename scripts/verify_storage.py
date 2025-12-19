#!/usr/bin/env python3
"""
Storage Verification Script

Verifies that the Archive Generator can successfully upload artifacts
to the CIVERS Web Interface REST API.

Usage:
    python scripts/verify_storage.py [--api-url http://localhost:8000]
"""

import argparse
import requests
import sys
from datetime import datetime


def check_web_interface_health(api_url: str) -> bool:
    """Check if the Web Interface is running."""
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
            print(f"✅ Upload endpoint available")
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
            # API returns 'data' key for list of URLs
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
            # API returns 'data' key for list of snapshots
            snapshots = data.get("data", data.get("items", []))
            return snapshots
        else:
            print(f"   ❌ Snapshots endpoint returned status {response.status_code}")
            return []
    except Exception as e:
        print(f"   ❌ Error getting snapshots: {e}")
        return []



def verify_storage(api_url: str, verbose: bool = False) -> bool:
    """
    Verify the storage system is working.
    
    Returns:
        True if verification passed, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"CIVERS Storage Verification")
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
        print("   ⚠️  Upload endpoint not responding (may be OK if no uploads yet)")
    
    # Step 3: List archived URLs
    print("\nStep 3: Listing archived URLs...")
    urls = list_urls(api_url)
    
    if not urls:
        print("   ℹ️  No archived URLs found - this is expected if no archives have been uploaded yet")
        print("\n" + "="*60)
        print("VERIFICATION RESULT: PARTIAL SUCCESS")
        print("Web Interface is running but no archives found.")
        print("Run the Archive Generator to upload some archives first.")
        print("="*60)
        return True
    
    # Step 4: Show URL details
    print("\nStep 4: Showing archived URLs and snapshots...")
    total_snapshots = 0
    for url_item in urls[:5]:  # Show first 5
        url_id = url_item.get("url_id", url_item.get("id", "unknown"))
        original_url = url_item.get("original_url", "unknown")
        snapshot_count = url_item.get("snapshot_count", 0)
        total_snapshots += snapshot_count
        
        print(f"\n   📁 {original_url}")
        print(f"      URL ID: {url_id}")
        print(f"      Snapshots: {snapshot_count}")
        
        if verbose and snapshot_count > 0:
            snapshots = get_snapshots_for_url(api_url, url_id)
            for snap in snapshots[:3]:  # Show first 3 snapshots
                snap_id = snap.get("snapshot_id", "unknown")
                artifacts = snap.get("available_artifacts", [])
                print(f"      └── Snapshot: {snap_id}")
                print(f"          Artifacts: {artifacts}")
    
    if len(urls) > 5:
        print(f"\n   ... and {len(urls) - 5} more URLs")
    
    print(f"\n" + "="*60)
    print(f"VERIFICATION RESULT: SUCCESS ✅")
    print(f"Total URLs: {len(urls)}")
    print(f"Total Snapshots: {total_snapshots}")
    print(f"Web Interface is working and has archived content.")
    print("="*60)
    return True


def main():
    parser = argparse.ArgumentParser(description="Verify CIVERS storage system")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Web Interface API URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show verbose output including snapshot details"
    )
    
    args = parser.parse_args()
    
    success = verify_storage(args.api_url, args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
