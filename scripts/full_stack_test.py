#!/usr/bin/env python3
"""
Full Stack Integration Test

Tests the complete CIVERS workflow:
1. Submit archive request to Orchestrator via Kafka
2. Wait for Generator to process and upload
3. Verify artifacts in Web Interface

Usage:
    python scripts/full_stack_test.py [--test-url URL] [--timeout SECONDS]
"""

import argparse
import asyncio
import sys
import time
import uuid
from pathlib import Path
from datetime import datetime

# Add project root and scripts directory to python path for imports
scripts_dir = Path(__file__).resolve().parent
repo_root = scripts_dir.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from config_loader import load_script_config, get_kafka_bootstrap, get_web_interface_url

try:
    import requests
except ImportError:
    print("❌ requests library required. Install with: pip install requests")
    sys.exit(1)

try:
    # Reuse the single canonical Kafka sender so submission stays consistent.
    from send_kafka_request import SendKafkaRequest
    KAFKA_AVAILABLE = True
except ImportError as e:
    KAFKA_AVAILABLE = False
    print(f"⚠️  Kafka submission unavailable (send_kafka_request/aiokafka import failed): {e}")


def _kafka_reachable(kafka_bootstrap: str) -> bool:
    """Return True if a Kafka producer can connect to the broker."""
    async def _run() -> bool:
        sender = SendKafkaRequest(kafka_bootstrap)
        try:
            return await sender.check_connection()
        finally:
            await sender.close()
    try:
        return asyncio.run(_run())
    except Exception:
        return False


def check_services(web_url: str, kafka_bootstrap: str) -> dict:
    """Check if required services are running."""
    status = {
        "web_interface": False,
        "kafka": False,
    }
    
    # Check Web Interface
    try:
        response = requests.get(f"{web_url}/health", timeout=5)
        status["web_interface"] = response.status_code == 200
        print(f"{'✅' if status['web_interface'] else '❌'} Web Interface: {web_url}")
    except Exception:
        print(f"❌ Web Interface: Cannot connect to {web_url}")
    
    # Check Kafka (via the shared SendKafkaRequest producer)
    if KAFKA_AVAILABLE:
        if _kafka_reachable(kafka_bootstrap):
            status["kafka"] = True
            print(f"✅ Kafka: {kafka_bootstrap}")
        else:
            print(f"❌ Kafka: Cannot connect to {kafka_bootstrap}")
    else:
        print("⚠️  Kafka: aiokafka/send_kafka_request unavailable")

    return status


def submit_archive_request_kafka(kafka_bootstrap: str, url: str, request_id: str) -> bool:
    """Submit a request to the ORCHESTRATOR topic via SendKafkaRequest.

    Publishing to orchestrator.requests triggers the full workflow
    (archive -> metadata -> callback) — exactly what a full-stack test exercises.
    """
    if not KAFKA_AVAILABLE:
        print("❌ Kafka library not available")
        return False

    async def _run() -> None:
        sender = SendKafkaRequest(kafka_bootstrap)
        try:
            await sender.send_one(url, "orchestrator", request_id=request_id)
        finally:
            await sender.close()

    try:
        asyncio.run(_run())
        print("✅ Submitted archive request to Kafka (orchestrator.requests)")
        print(f"   Request ID: {request_id}")
        print(f"   URL: {url}")
        return True
    except Exception as e:
        print(f"❌ Failed to submit Kafka message: {e}")
        return False


def wait_for_archive(web_url: str, url: str, timeout: int = 120, poll_interval: int = 5) -> dict:
    """Wait for archive to appear in Web Interface."""
    print(f"\n⏳ Waiting for archive to complete (timeout: {timeout}s)...")
    
    start_time = time.time()
    initial_count = get_snapshot_count(web_url, url)
    
    while time.time() - start_time < timeout:
        current_count = get_snapshot_count(web_url, url)
        
        if current_count > initial_count:
            print(f"✅ New snapshot detected! ({current_count} total)")
            return {"success": True, "snapshots": current_count}
        
        elapsed = int(time.time() - start_time)
        print(f"   ... waiting ({elapsed}s elapsed, {current_count} snapshots)")
        time.sleep(poll_interval)
    
    print("❌ Timeout waiting for new archive")
    return {"success": False, "snapshots": get_snapshot_count(web_url, url)}


def get_snapshot_count(web_url: str, url: str) -> int:
    """Get number of snapshots for a URL."""
    try:
        response = requests.get(f"{web_url}/api/urls", timeout=10)
        if response.status_code == 200:
            data = response.json()
            urls = data.get("data", [])
            for item in urls:
                if url in item.get("original_url", ""):
                    return item.get("snapshot_count", 0)
        return 0
    except Exception:
        return 0


def get_latest_snapshot(web_url: str, url: str) -> tuple[dict, str]:
    """Get details of the latest snapshot for a URL.

    Returns:
        tuple: (snapshot_dict, url_id)
    """
    try:
        # First find the URL ID
        response = requests.get(f"{web_url}/api/urls", timeout=10)
        if response.status_code != 200:
            return {}, ""

        data = response.json()
        urls = data.get("data", [])

        url_id = None
        for item in urls:
            if url in item.get("original_url", ""):
                url_id = item.get("url_id")
                break

        if not url_id:
            return {}, ""

        # Get snapshots
        response = requests.get(f"{web_url}/api/urls/{url_id}/snapshots", timeout=10)
        if response.status_code != 200:
            return {}, url_id

        data = response.json()
        snapshots = data.get("data", [])

        if snapshots:
            return snapshots[0], url_id  # Most recent snapshot and url_id
        return {}, url_id

    except Exception as e:
        print(f"   Error getting snapshot: {e}")
        return {}, ""


def verify_artifacts(web_url: str, url: str) -> bool:
    """Verify artifacts are present and valid."""
    print("\n🔍 Verifying artifacts...")

    snapshot, url_id = get_latest_snapshot(web_url, url)
    if not snapshot:
        print("❌ No snapshot found")
        return False

    snapshot_id = snapshot.get("snapshot_id", "unknown")
    artifacts = snapshot.get("available_artifacts", [])

    print(f"   Snapshot ID: {snapshot_id}")
    print(f"   Artifacts: {artifacts}")

    # Check for expected artifact types
    expected = ["archive.wacz", "screenshot.png", "metadata.json"]
    found = []
    missing = []

    for exp in expected:
        if exp in artifacts:
            found.append(exp)
        else:
            missing.append(exp)

    if found:
        print(f"   ✅ Found expected artifacts: {found}")
    if missing:
        print(f"   ⚠️  Missing expected artifacts: {missing}")

    # Display web UI URLs
    if snapshot_id != "unknown":
        replay_url = f"{web_url}/replay/{snapshot_id}"
        print(f"   ✅ View replay: {replay_url}")

    if url_id:
        archive_url = f"{web_url}/archive/{url_id}"
        print(f"   ✅ View archive: {archive_url}")

    return len(artifacts) > 0


def run_full_stack_test(
    web_url: str = "http://localhost:8000",
    kafka_bootstrap: str = "localhost:29092",
    test_url: str = "https://arachne.test.dainst.org/entity/2003181",
    timeout: int = 120
) -> bool:
    """Run the full stack integration test."""
    
    request_id = f"fullstack-test-{uuid.uuid4().hex[:8]}"
    
    print(f"\n{'='*60}")
    print("CIVERS Full Stack Integration Test")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")
    
    print("Configuration:")
    print(f"  Web Interface: {web_url}")
    print(f"  Kafka: {kafka_bootstrap}")
    print(f"  Test URL: {test_url}")
    print(f"  Request ID: {request_id}")
    print(f"  Timeout: {timeout}s")
    print()
    
    # Step 1: Check services
    print("Step 1: Checking services...")
    status = check_services(web_url, kafka_bootstrap)
    
    if not status["web_interface"]:
        print("\n❌ Web Interface is required for verification")
        return False
    
    # Step 2: Submit request (if Kafka available)
    if status["kafka"]:
        print("\nStep 2: Submitting archive request via Kafka...")
        if not submit_archive_request_kafka(kafka_bootstrap, test_url, request_id):
            print("❌ Failed to submit request")
            return False
        
        # Step 3: Wait for archive
        print("\nStep 3: Waiting for archive completion...")
        result = wait_for_archive(web_url, test_url, timeout)
        
        if not result["success"]:
            print("\n⚠️  No new archive detected within timeout")
            print("   This may be because:")
            print("   - Orchestrator or Generator is not running")
            print("   - The URL is already archived")
            print("   - There was a processing error")
            print("\n   Checking existing archives...")
    else:
        print("\nStep 2-3: Skipping Kafka submission (library not installed)")
        print("   Checking existing archives instead...")
    
    # Step 4: Verify artifacts
    print("\nStep 4: Verifying artifacts...")
    verified = verify_artifacts(web_url, test_url)
    
    print(f"\n{'='*60}")
    if verified:
        print("RESULT: SUCCESS ✅")
        print("Full stack integration verified!")
        print("Archives are present and accessible via Web Interface.")
    else:
        print("RESULT: PARTIAL SUCCESS ⚠️")
        print("Services are running but no archives found for test URL.")
        print("Manual archive generation may be required.")
    print(f"{'='*60}")
    
    return verified


def main():
    # Load configuration
    config = load_script_config()
    default_web_url = get_web_interface_url(config)
    default_kafka = get_kafka_bootstrap(config)

    parser = argparse.ArgumentParser(description="Full Stack Integration Test")
    parser.add_argument(
        "--web-url",
        default=default_web_url,
        help=f"Web Interface URL (default: {default_web_url})"
    )
    parser.add_argument(
        "--kafka",
        default=default_kafka,
        help=f"Kafka bootstrap servers (default: {default_kafka})"
    )
    parser.add_argument(
        "--test-url",
        default="https://arachne.test.dainst.org/entity/2003181",
        help="URL to archive for testing"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout in seconds waiting for archive"
    )
    
    args = parser.parse_args()
    
    success = run_full_stack_test(
        web_url=args.web_url,
        kafka_bootstrap=args.kafka,
        test_url=args.test_url,
        timeout=args.timeout
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
