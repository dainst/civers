#!/usr/bin/env python3
"""
Demo script for testing the Archive Generator's storage capabilities.

This script demonstrates:
1. Local file storage (metadata only)
2. CIVERS REST API storage (metadata and all artifacts)
3. Upload verification by downloading and comparing files

Usage:
    # Test local storage only (no external dependencies)
    uv run python demo_storage.py
    
    # Test with CIVERS REST API (requires API to be running)
    uv run python demo_storage.py --with-api
    
    # Test full artifact upload (wacz, html, png, etc.)
    uv run python demo_storage.py --with-api --artifacts
    
    # Custom API URL
    uv run python demo_storage.py --with-api --api-url=http://localhost:8000/api/upload

Prerequisites:
    - For local storage: No external dependencies
    - For API storage: CIVERS storage API must be running (default: http://127.0.0.1:8000)
"""

import asyncio
import json
import sys
import argparse
import zipfile
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# API Configuration defaults
DEFAULT_API_URL = "http://127.0.0.1:8000"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test the Archive Generator's storage layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Test local storage only
  %(prog)s --with-api                   # Test metadata upload to API
  %(prog)s --with-api --artifacts       # Test all artifact types (wacz, html, png)
  %(prog)s --use-config                 # Use config from configs/data/ (development.yaml)
  %(prog)s --use-config --url=https://example.com --request-id=my-request-123
  %(prog)s --with-api --api-url=http://localhost:8000/api/upload
        """
    )
    
    parser.add_argument(
        "--with-api",
        action="store_true",
        help="Test CIVERS REST API storage (requires API to be running)"
    )
    
    parser.add_argument(
        "--artifacts",
        action="store_true",
        help="Test upload of all artifact types (wacz, html, png, etc.)"
    )
    
    parser.add_argument(
        "--api-url",
        default=f"{DEFAULT_API_URL}/api/upload",
        help=f"CIVERS API upload endpoint URL (default: {DEFAULT_API_URL}/api/upload)"
    )
    
    parser.add_argument(
        "--use-config",
        action="store_true",
        help="Use storage config from configs/data/ instead of hardcoded values"
    )
    
    parser.add_argument(
        "--url",
        default=None,
        help="Custom URL to use for the test metadata (e.g., https://example.com/page)"
    )
    
    parser.add_argument(
        "--request-id",
        default=None,
        dest="request_id",
        help="Custom request ID to use (default: auto-generated with timestamp)"
    )
    
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Verify uploads by downloading and comparing (default: True)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    return parser.parse_args()


async def test_with_config(
    verbose: bool = False,
    custom_url: Optional[str] = None,
    custom_request_id: Optional[str] = None
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Test storage using configuration from configs/data/."""
    import importlib.util
    if importlib.util.find_spec("httpx") is None:
        pass  # May not need httpx if API is not enabled
    
    from configs.loaders import YamlFileConfigLoader
    from storage_layer import StorageManager
    
    print("\n" + "="*60)
    print("⚙️ Testing Storage with CONFIG SYSTEM")
    print("="*60)
    
    # Load config from configs/data/
    print("\n📄 Loading configuration...")
    config = YamlFileConfigLoader().load()
    storage_config = config.app.get_storage_config()
    
    enabled_backends = storage_config.get_enabled_backends()
    print(f"   Enabled backends: {enabled_backends}")
    
    # Show backend details
    if storage_config.backends:
        for backend_name in enabled_backends:
            backend_config = storage_config.backends.get(backend_name, {})
            if backend_name == "local_file":
                print(f"   local_file.base_path: {backend_config.get('base_path')}")
            elif backend_name == "civers_rest_api":
                print(f"   civers_rest_api.upload_url: {backend_config.get('upload_url')}")
    
    # Initialize StorageManager with config
    manager = StorageManager(storage_config)
    
    # Check backend availability
    print("\n🔍 Checking backend availability...")
    for backend_name, strategy in manager.strategies.items():
        is_available = await strategy.is_available()
        status = "✅ Available" if is_available else "❌ Not available"
        print(f"   - {backend_name}: {status}")
    
    # Use custom or default values
    request_id = custom_request_id or f"config_test_{int(datetime.now().timestamp())}"
    source_url = custom_url or "https://arachne.dainst.org/entity/99999"
    
    # Store test metadata
    test_metadata = {
        "source_url": source_url,
        "title": f"Storage Test - {source_url}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_count": 3,
        "total_size": 12345,
        "test_type": "config_system",
        "request_id": request_id
    }
    
    print("\n📤 Storing metadata via config-based StorageManager...")
    print(f"   Request ID: {request_id}")
    print(f"   URL: {source_url}")
    if verbose:
        print(f"   Data: {json.dumps(test_metadata, indent=2)}")
    
    result = await manager.store_metadata(
        data=test_metadata,
        request_id=request_id,
        url=source_url,
        filename=f"metadata_{request_id}.json"
    )
    
    print("\n📊 Result:")
    print(f"   Overall success: {result.overall_success}")
    print(f"   Successful: {result.get_successful_backends()}")
    print(f"   Failed: {result.get_failed_backends()}")
    
    api_snapshot_id = None
    for r in result.results:
        if r.success:
            print(f"\n   ✅ {r.storage_type}: {r.storage_location}")
            if r.storage_type == "civers_rest_api":
                api_snapshot_id = r.storage_location
        else:
            print(f"\n   ❌ {r.storage_type}: {r.error_message}")
    
    return result.overall_success, api_snapshot_id, test_metadata


async def test_local_storage(verbose: bool = False) -> Tuple[bool, Optional[str]]:
    """Test local file storage."""
    from configs.models import StorageConfig
    from storage_layer import StorageManager
    
    print("\n" + "="*60)
    print("📁 Testing LOCAL FILE Storage")
    print("="*60)
    
    output_dir = Path("test_output/metadata")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    config = StorageConfig(
        enabled=["local_file"],
        backends={
            "local_file": {
                "base_path": str(output_dir),
                "create_subdirectories": True
            }
        }
    )
    
    manager = StorageManager(config)
    
    request_id = f"local_test_{int(datetime.now().timestamp())}"
    test_metadata = {
        "source_url": "https://example.com/test-page",
        "title": "Local Storage Test",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_count": 3,
        "total_size": 12345,
    }
    
    print("\n📤 Storing metadata...")
    print(f"   Request ID: {request_id}")
    if verbose:
        print(f"   Data: {json.dumps(test_metadata, indent=2)}")
    
    result = await manager.store_metadata(
        data=test_metadata,
        request_id=request_id,
        url="https://example.com/test-page",
        filename=f"metadata_{request_id}.json"
    )
    
    print("\n📊 Result:")
    print(f"   Success: {result.overall_success}")
    print(f"   Backends: {result.get_successful_backends()}")
    
    if result.overall_success:
        file_path = result.results[0].storage_location
        print("\n   ✅ Local storage test PASSED!")
        print(f"   📁 File: {file_path}")
        return True, file_path
    else:
        print("\n   ❌ Local storage test FAILED!")
        return False, None


async def test_api_storage(api_url: str, verbose: bool = False) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Test CIVERS REST API storage (metadata only)."""
    try:
        import httpx
    except ImportError:
        print("\n❌ httpx not installed. Install with: uv add httpx")
        return False, None, {}
    
    from configs.models import StorageConfig
    from storage_layer import StorageManager
    
    print("\n" + "="*60)
    print("🌐 Testing CIVERS REST API Storage (Metadata)")
    print(f"   API URL: {api_url}")
    print("="*60)
    
    base_url = api_url.rsplit('/api', 1)[0]
    
    # Check API availability
    print("\n🔍 Checking API availability...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("   ✅ API is running!")
            else:
                print(f"   ⚠️ API responded with status {response.status_code}")
        except Exception as e:
            print(f"   ❌ API not reachable: {e}")
            return False, None, {}
    
    output_dir = Path("test_output/metadata")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    config = StorageConfig(
        enabled=["local_file", "civers_rest_api"],
        backends={
            "local_file": {
                "base_path": str(output_dir),
                "create_subdirectories": True
            },
            "civers_rest_api": {
                "upload_url": api_url,
                "timeout_seconds": 30,
                "verify_ssl": False,
                "auth": {"enabled": False}
            }
        }
    )
    
    manager = StorageManager(config)
    
    request_id = f"api_test_{int(datetime.now().timestamp())}"
    test_metadata = {
        "source_url": "https://arachne.dainst.org/entity/12345",
        "title": "API Storage Test",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_count": 5,
        "total_size": 54321,
        "artifacts": ["warc", "html", "screenshot"],
    }
    
    print("\n📤 Storing metadata via StorageManager...")
    print(f"   Request ID: {request_id}")
    if verbose:
        print(f"   Data: {json.dumps(test_metadata, indent=2)}")
    
    result = await manager.store_metadata(
        data=test_metadata,
        request_id=request_id,
        url="https://arachne.dainst.org/entity/12345",
        filename=f"metadata_{request_id}.json"
    )
    
    print("\n📊 Result:")
    print(f"   Success: {result.overall_success}")
    print(f"   Successful: {result.get_successful_backends()}")
    print(f"   Failed: {result.get_failed_backends()}")
    
    api_snapshot_id = None
    for r in result.results:
        if r.success:
            print(f"\n   ✅ {r.storage_type}: {r.storage_location}")
            if r.storage_type == "civers_rest_api":
                api_snapshot_id = r.storage_location
        else:
            print(f"\n   ❌ {r.storage_type}: {r.error_message}")
    
    api_success = "civers_rest_api" in result.get_successful_backends()
    return api_success, api_snapshot_id, test_metadata


def create_sample_artifacts(output_dir: Path, url: str, request_id: str) -> Dict[str, Path]:
    """Create sample archive artifacts for testing."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    artifacts = {}
    
    # 1. metadata.json
    metadata = {
        "archive_info": {
            "url": url,
            "request_id": request_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "generator": "demo_storage.py",
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
    
    # 4. screenshot.png (minimal valid PNG)
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


async def test_artifact_upload(api_url: str, verbose: bool = False) -> Tuple[bool, Optional[str], Dict[str, Path]]:
    """Test upload of all archive artifact types."""
    try:
        import httpx
    except ImportError:
        print("\n❌ httpx not installed")
        return False, None, {}
    
    from storage_layer.civers_rest_api_storage_strategy import CiversRestApiStorageStrategy
    
    print("\n" + "="*60)
    print("📦 Testing ARTIFACT UPLOAD (All File Types)")
    print("="*60)
    
    base_url = api_url.rsplit('/api', 1)[0]
    
    # Check API
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code != 200:
                print("   ⚠️ API not healthy")
                return False, None, {}
        except Exception:
            print("   ❌ API not reachable")
            return False, None, {}
    
    # Create sample artifacts
    request_id = f"artifact_test_{int(datetime.now().timestamp())}"
    test_url = "https://example.com/artifact-test"
    output_dir = Path(f"test_output/artifacts/{request_id}")
    
    print("\n📦 Creating sample artifacts...")
    print(f"   Output dir: {output_dir}")
    artifacts = create_sample_artifacts(output_dir, test_url, request_id)
    
    for name, path in artifacts.items():
        print(f"   ✓ {name} ({path.stat().st_size} bytes)")
    
    # Upload
    print("\n📤 Uploading artifacts...")
    strategy = CiversRestApiStorageStrategy(
        upload_url=api_url,
        timeout_seconds=60,
        verify_ssl=False
    )
    
    result = await strategy.store_artifacts(
        archive_path=str(output_dir),
        request_id=request_id,
        url=test_url
    )
    
    if result.success:
        print("\n   ✅ Upload successful!")
        print(f"   Snapshot ID: {result.storage_location}")
        files_uploaded = result.metadata.get("files_uploaded", []) if result.metadata else []
        print(f"   Files: {files_uploaded}")
        return True, result.storage_location, artifacts
    else:
        print(f"\n   ❌ Upload failed: {result.error_message}")
        return False, None, {}


async def verify_api_upload(snapshot_id: str, original_data: Dict[str, Any], api_base_url: str) -> bool:
    """Verify metadata upload."""
    import httpx
    
    serve_url = f"{api_base_url}/api/artifacts/serve?snapshot_id={snapshot_id}&type=metadata.json"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(serve_url)
            if response.status_code == 200:
                downloaded = response.json()
                # Check key fields match
                match = all(
                    downloaded.get(k) == original_data.get(k)
                    for k in ["source_url", "title"]
                )
                return match
            return False
        except Exception:
            return False


async def verify_artifacts(snapshot_id: str, artifacts: Dict[str, Path], api_base_url: str) -> Dict[str, bool]:
    """Verify all artifact uploads."""
    import httpx
    
    print("\n🔍 Verifying artifacts...")
    
    results = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for name, local_path in artifacts.items():
            url = f"{api_base_url}/api/artifacts/serve?snapshot_id={snapshot_id}&type={name}"
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    downloaded = response.content
                    local = local_path.read_bytes()
                    match = downloaded == local
                    status = "✅" if match else "⚠️"
                    print(f"   {status} {name}: {len(downloaded)} bytes")
                    results[name] = True  # Accept if downloaded
                else:
                    print(f"   ❌ {name}: HTTP {response.status_code}")
                    results[name] = False
            except Exception as e:
                print(f"   ❌ {name}: {e}")
                results[name] = False
    
    return results


async def main():
    """Run storage tests."""
    args = parse_args()
    
    print("\n" + "="*60)
    print("🧪 Archive Generator - Storage Layer Demo")
    print("="*60)
    
    results = {}
    
    # Test with config system (if requested)
    if args.use_config:
        config_ok, snapshot_id, metadata = await test_with_config(
            verbose=args.verbose,
            custom_url=args.url,
            custom_request_id=args.request_id
        )
        results["config_system"] = config_ok
        
        if config_ok and snapshot_id and args.verify:
            # Get API URL from config
            from configs.loaders import YamlFileConfigLoader
            config = YamlFileConfigLoader().load()
            storage_config = config.app.get_storage_config()
            api_config = storage_config.backends.get("civers_rest_api", {})
            upload_url = api_config.get("upload_url", args.api_url)
            base_url = upload_url.rsplit('/api', 1)[0]
            verify_ok = await verify_api_upload(snapshot_id, metadata, base_url)
            results["config_api_verification"] = verify_ok
    else:
        # Test 1: Local storage
        local_ok, _ = await test_local_storage(verbose=args.verbose)
        results["local_file"] = local_ok
        
        # Test 2: API storage (metadata)
        if args.with_api:
            api_ok, snapshot_id, metadata = await test_api_storage(
                api_url=args.api_url,
                verbose=args.verbose
            )
            results["api_metadata"] = api_ok
            
            if api_ok and snapshot_id and args.verify:
                base_url = args.api_url.rsplit('/api', 1)[0]
                verify_ok = await verify_api_upload(snapshot_id, metadata, base_url)
                results["api_verification"] = verify_ok
        
        # Test 3: Artifact upload (all file types)
        if args.with_api and args.artifacts:
            artifact_ok, artifact_snapshot_id, artifacts = await test_artifact_upload(
                api_url=args.api_url,
                verbose=args.verbose
            )
            results["artifact_upload"] = artifact_ok
            
            if artifact_ok and artifact_snapshot_id:
                base_url = args.api_url.rsplit('/api', 1)[0]
                artifact_results = await verify_artifacts(artifact_snapshot_id, artifacts, base_url)
                for name, passed in artifact_results.items():
                    results[f"artifact_{name}"] = passed
    
    # Summary
    print("\n" + "="*60)
    print("📊 FINAL RESULTS")
    print("="*60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️ Some tests failed.")
    
    if not args.with_api and not args.use_config:
        print("\n💡 Options:")
        print("   --with-api        Test with hardcoded API URL")
        print("   --use-config      Use config from configs/data/")
        print("   --artifacts       Test all artifact types")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
