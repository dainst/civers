#!/usr/bin/env python3
"""
Test script for uploading files to the archive API.

Usage:
    python test_upload.py
    python test_upload.py --url https://example.com/page --request-id my-test-123
"""

import requests
import json
import sys
from datetime import datetime
import argparse


def create_test_files():
    """Create temporary test files for upload."""
    files = {}

    # Create metadata.json
    metadata = {
        "url": "https://www.sqlite.org/foreignkeys.html",
        "title": "Test Page Upload",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "status": 200,
        "content_type": "text/html"
    }
    files['metadata.json'] = json.dumps(metadata).encode('utf-8')

    # Create fake WACZ file
    files['archive.wacz'] = b"This is a test WACZ archive file content"

    # Create fake screenshot
    files['screenshot.png'] = b"Fake PNG image data for testing purposes"

    # Create fake SingleFile HTML
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <meta charset="UTF-8">
</head>
<body>
    <h1>Test Upload</h1>
    <p>This is a test page uploaded via the API.</p>
    <p>Timestamp: {}</p>
</body>
</html>""".format(datetime.now().isoformat())

    files['singlefile.html'] = html_content.encode('utf-8')

    return files


def upload_files(api_url, url, request_id, allow_existing=False):
    """
    Upload files to the archive API.

    Args:
        api_url: API endpoint URL
        url: URL being archived
        request_id: Unique request identifier
        allow_existing: Allow adding to existing snapshot

    Returns:
        Response object
    """
    print("=" * 60)
    print("Archive Upload Test")
    print("=" * 60)
    print(f"\nAPI URL: {api_url}")
    print(f"Target URL: {url}")
    print(f"Request ID: {request_id}")
    print(f"Allow existing: {allow_existing}")
    print()

    # Create test files
    print("Creating test files...")
    test_files = create_test_files()
    print(f"Created {len(test_files)} test files:")
    for filename, content in test_files.items():
        print(f"  - {filename} ({len(content)} bytes)")
    print()

    # Prepare multipart form data
    files_data = []
    for filename, content in test_files.items():
        files_data.append(
            ('files', (filename, content, 'application/octet-stream'))
        )

    form_data = {
        'url': url,
        'request_id': request_id,
        'allow_existing': str(allow_existing).lower()
    }

    # Upload
    print("Uploading to API...")
    try:
        response = requests.post(
            api_url,
            data=form_data,
            files=files_data,
            headers={'Accept': 'application/json'}
        )

        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()

        if response.status_code == 200:
            print("✅ Upload successful!")
            result = response.json()
            print(json.dumps(result, indent=2))
            return result
        else:
            print("❌ Upload failed!")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API.")
        print("Make sure the application is running on http://localhost:8000")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def verify_upload(snapshot_id):
    """Verify the uploaded snapshot can be retrieved."""
    print()
    print("=" * 60)
    print("Verifying Upload")
    print("=" * 60)
    print()

    # Get snapshot details
    print(f"Fetching snapshot: {snapshot_id}")
    try:
        response = requests.get(f"http://localhost:8000/api/snapshots/{snapshot_id}")

        if response.status_code == 200:
            print("✅ Snapshot retrieved successfully!")
            snapshot = response.json()
            print(json.dumps(snapshot, indent=2))
            print()
            print(f"Artifacts available: {', '.join(snapshot.get('available_artifacts', []))}")
        else:
            print(f"❌ Could not retrieve snapshot (status {response.status_code})")

    except Exception as e:
        print(f"❌ Error verifying upload: {e}")


def list_all_urls():
    """List all archived URLs."""
    print()
    print("=" * 60)
    print("All Archived URLs")
    print("=" * 60)
    print()

    try:
        response = requests.get("http://localhost:8000/api/urls")

        if response.status_code == 200:
            urls = response.json()
            print(f"Total URLs: {len(urls)}")
            print()

            for i, url_data in enumerate(urls['data'][-1:-4:-1], 1):  # Show last 3
                print(f"{i}. {url_data['url_id']}")
                print(f"   URL: {url_data['original_url']}")
                print(f"   Snapshots: {url_data['snapshot_count']}")
                print()

            if len(urls) > 3:
                print(f"... and {len(urls) - 3} more URLs")
        else:
            print(f"❌ Could not retrieve URLs (status {response.status_code})")

    except Exception as e:
        print(f"❌ Error listing URLs: {e}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test archive upload API')
    parser.add_argument('--url', default='https://www.sqlite.org/foreignkeys.html',
                        help='URL to archive')
    parser.add_argument('--request-id', default=None,
                        help='Request ID (generated if not provided)')
    parser.add_argument('--api-url', default='http://localhost:8000/api/upload',
                        help='API endpoint URL')
    parser.add_argument('--allow-existing', action='store_true',
                        help='Allow adding to existing snapshot')

    args = parser.parse_args()

    # Generate request ID if not provided
    request_id = args.request_id or f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Upload files
    result = upload_files(args.api_url, args.url, request_id, args.allow_existing)

    if result and result.get('success'):
        snapshot_id = result.get('snapshot_id')

        # Verify upload
        if snapshot_id:
            verify_upload(snapshot_id)

        # List all URLs
        list_all_urls()

        print()
        print("=" * 60)
        print("✅ Test Complete!")
        print("=" * 60)
        return 0
    else:
        print()
        print("=" * 60)
        print("❌ Test Failed")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
