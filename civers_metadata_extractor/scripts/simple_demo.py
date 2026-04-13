#!/usr/bin/env python3
"""
CIVERS Metadata Extractor - Simple Demo

This simplified demo demonstrates metadata extraction from an Arachne sample:
1. Sends a Kafka message with Arachne URL and HTML content OR document_url
2. Monitors the processing
3. Displays the generated metadata output

Usage:
  # Using embedded HTML content (default):
  python simple_demo.py

  # Using document_url to download HTML:
  python simple_demo.py --document-url http://127.0.0.1:8000/api/artifacts/serve?snapshot_id=req_123456_20251204_163237&type=document.html
"""

import argparse
import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

import httpx
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from configs.loaders import YamlFileConfigLoader
from transport_services.kafka.event_models import MetadataExtractionRequestEvent

# Simple demo configuration
DEMO_CONFIG = {"timeout_seconds": 30, "output_directory": "demo_output"}

# Arachne sample data
ARACHNE_SAMPLE = {
    "url": "https://arachne.test.dainst.org/entity/1079332",
    "domain": "arachne.test.dainst.org",
    "html_content": """
    <html>
    <head>
        <title>Panzerstatue des Augustus von Prima Porta</title>
        <script type="application/ld+json">
        {
            "@context": "http://schema.org",
            "@type": "CreativeWork",
            "name": "Panzerstatue des Augustus von Prima Porta",
            "description": "Resource about Augustus statue from Prima Porta",
            "@id": "https://arachne.dainst.org/entity/1079332",
            "author": [
                {
                    "name": "Deutsches Archäologisches Institut",
                    "url": "https://www.dainst.org",
                    "@type": "Organization"
                },
                {
                    "name": "Universität zu Köln",
                    "url": "https://www.uni-koeln.de",
                    "@type": "Organization"
                }
            ],
            "publisher": [
                {
                    "name": "iDAI.objects/Arachne",
                    "@type": "Organization",
                    "identifier": {
                        "propertyID": "ror.org",
                        "value": "https://ror.org/02k8k4y17"
                    }
                }
            ],
            "datePublished": "2019-03-15",
            "dateModified": "2023-11-20",
            "image": [
                "https://arachne.dainst.org/data/image/1079332_01.jpg",
                "https://arachne.dainst.org/data/image/1079332_02.jpg"
            ]
        }
        </script>
    </head>
    <body>
        <h1>Panzerstatue des Augustus von Prima Porta</h1>
        <p>Detailed archaeological information about the Augustus statue...</p>
    </body>
    </html>
    """,
}
# read sample html content from file
sample_html_path = Path(__file__).parent / "sample_arachne.html"
print(f"Loading sample HTML content from: {sample_html_path}")
if sample_html_path.exists():
    with open(sample_html_path, encoding="utf-8") as f:
        ARACHNE_SAMPLE["html_content"] = f.read()


class SimpleDemo:
    """Simplified demo for Arachne metadata extraction."""

    def __init__(self, document_url: str = None, request_id: str = None):
        self.document_url = document_url
        self.request_id = request_id
        self.demo_id = str(uuid.uuid4())[:8]
        self.producer = None
        self.consumer = None

        # Setup output directory
        self.output_dir = Path(DEMO_CONFIG["output_directory"])
        self.output_dir.mkdir(exist_ok=True)

        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG,  # Changed to DEBUG to see detailed mapping logs
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize demo components."""
        print("🚀 Initializing Simple Metadata Extraction Demo...")

        # Load configuration
        self.config = YamlFileConfigLoader().load()
        self.kafka_config = self.config.app.get_kafka_config()

        print("✅ Configuration loaded")
        print(f"   Kafka: {self.kafka_config.bootstrap_servers}")

        # Setup Kafka components
        await self._setup_kafka()

        print(f"✅ Demo initialized (ID: {self.demo_id})")
        return True

    async def _setup_kafka(self):
        """Setup Kafka producer and consumer."""
        # Producer
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_config.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks=1,
            request_timeout_ms=30000,
            retry_backoff_ms=1000,
        )
        await self.producer.start()

        # Consumer for monitoring
        response_topics = [
            self.kafka_config.topics["metadata_extraction_completed"],
            self.kafka_config.topics["metadata_extraction_failed"],
        ]

        self.consumer = AIOKafkaConsumer(
            *response_topics,
            bootstrap_servers=self.kafka_config.bootstrap_servers,
            group_id=f"simple_demo_{self.demo_id}",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            enable_auto_commit=True,
        )
        await self.consumer.start()

        # Brief wait for consumer setup
        await asyncio.sleep(2)

    async def run_demo(self):
        """Run the complete demo workflow."""
        print("\n🎯 Starting Arachne Metadata Extraction Demo")
        print("=" * 50)

        try:
            # Send extraction request
            request_id = await self.send_request()

            # Monitor and get result
            result = await self.monitor_extraction(request_id)

            # Display results
            local_json_path = self.display_results(result)

            # Verify CIVERS API upload if extraction succeeded
            if result["status"] == "completed" and local_json_path:
                await self.verify_civers_upload(request_id, local_json_path)

        except Exception as e:
            print(f"❌ Demo failed: {e}")
            self.logger.error(f"Demo failed: {e}", exc_info=True)

    async def send_request(self):
        """Send metadata extraction request."""
        if not self.request_id:
            self.request_id = f"demo_{self.demo_id}_{int(time.time())}"

        # Determine which mode to use
        if self.document_url:
            # Use document_url mode (download HTML from URL)
            request_data = {
                "request_id": self.request_id,
                "url": "https://arachne.test.dainst.org/entity/2003166",  # ARACHNE_SAMPLE['url'],
                "domain": ARACHNE_SAMPLE["domain"],
                "document_url": self.document_url,
                "priority": 1,
                "requester": f"simple_demo_{self.demo_id}",
            }
            mode = "document_url"
        else:
            # Use html_content mode (embedded HTML)
            request_data = {
                "request_id": self.request_id,
                "url": "https://arachne.test.dainst.org/entity/2003166",  # ARACHNE_SAMPLE['url'],
                "domain": "arachne.test.dainst.org",  # ARACHNE_SAMPLE['domain'],
                "html_content": ARACHNE_SAMPLE["html_content"],
                "priority": 1,
                "requester": f"simple_demo_{self.demo_id}",
            }
            mode = "html_content"

        # Create extraction request
        request = MetadataExtractionRequestEvent(**request_data)

        # Send to request topic
        topic = self.kafka_config.topics["metadata_extraction_requests"]
        await self.producer.send(topic, request.model_dump(), key=self.request_id)

        print(f"📤 Sent extraction request (mode: {mode})")
        print(f"   Request ID: {self.request_id}")
        print(f"   URL: {ARACHNE_SAMPLE['url']}")
        print(f"   Domain: {ARACHNE_SAMPLE['domain']}")
        if self.document_url:
            print(f"   Document URL: {self.document_url}")
        else:
            print(f"   HTML content length: {len(ARACHNE_SAMPLE['html_content'])} chars")

        return self.request_id

    async def monitor_extraction(self, request_id: str):
        """Monitor extraction process."""
        print(f"\n🔍 Monitoring extraction for: {request_id}")
        print("Waiting for response", end="")

        start_time = time.time()
        timeout = DEMO_CONFIG["timeout_seconds"]

        # Create async task for consuming messages
        consumer_task = asyncio.create_task(self._consume_messages(request_id, start_time))
        timeout_task = asyncio.create_task(asyncio.sleep(timeout))

        try:
            # Wait for either completion or timeout
            done, pending = await asyncio.wait(
                [consumer_task, timeout_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()

            # Check if we got a result
            if consumer_task in done:
                result = await consumer_task
                if result:
                    return result

            # Timeout case
            print(f"\n⏰ Timeout after {timeout}s")
            return {"status": "timeout", "data": None, "processing_time": timeout}

        except Exception as e:
            self.logger.error(f"Error monitoring: {e}")
            return {
                "status": "error",
                "data": {"error": str(e)},
                "processing_time": time.time() - start_time,
            }

    async def _consume_messages(self, request_id: str, start_time: float):
        """Consume messages asynchronously."""
        try:
            async for message in self.consumer:
                event_data = message.value
                message_request_id = event_data.get("request_id", "")

                if message_request_id != request_id:
                    continue  # Not our request

                # Check message type
                if "completed" in message.topic:
                    print("\n✅ Extraction completed!")
                    return {
                        "status": "completed",
                        "data": event_data,
                        "processing_time": time.time() - start_time,
                    }
                elif "failed" in message.topic:
                    print("\n❌ Extraction failed!")
                    return {
                        "status": "failed",
                        "data": event_data,
                        "processing_time": time.time() - start_time,
                    }
        except asyncio.CancelledError:
            # Task was cancelled due to timeout
            return None
        except Exception as e:
            self.logger.warning(f"Error consuming messages: {e}")
            return None

    def display_results(self, result):
        """Display extraction results and return path to saved file."""
        print("\n📊 EXTRACTION RESULTS")
        print("=" * 50)

        status = result["status"]
        processing_time = result.get("processing_time", 0)

        print(f"Status: {status.upper()}")
        print(f"Processing Time: {processing_time:.2f} seconds")

        demo_output_path = None  # Track the saved file path

        if status == "completed":
            data = result["data"]

            # Basic info
            print(f"Domain Used: {data.get('domain_used', 'unknown')}")
            print(f"Mappers Used: {', '.join(data.get('mappers_used', []))}")

            # Check for JSON output file
            json_output_path = data.get("json_output_path")
            if json_output_path and Path(json_output_path).exists():
                print(f"📄 JSON Output: {json_output_path}")

                # Display metadata preview
                try:
                    with open(json_output_path, encoding="utf-8") as f:
                        json_data = json.load(f)

                    print("\n📋 METADATA PREVIEW:")
                    self._display_metadata_preview(json_data)

                    # Copy to demo output directory
                    demo_output_path = self.output_dir / f"arachne_metadata_{self.demo_id}.json"
                    with open(demo_output_path, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, indent=2, ensure_ascii=False)

                    print(f"\n📁 Metadata saved to: {demo_output_path}")

                except Exception as e:
                    print(f"❌ Error reading JSON file: {e}")
            else:
                print("❌ No JSON output file generated")

        elif status == "failed":
            data = result["data"]
            print(f"❌ Error: {data.get('error_message', 'Unknown error')}")
            print(f"❌ Failed at: {data.get('failed_stage', 'Unknown stage')}")

        elif status == "timeout":
            print("⏰ No response received within timeout period")
            print("💡 Make sure the metadata extraction service is running:")
            print("   uv run python3 main.py")

        return str(demo_output_path) if demo_output_path else None

    def _display_metadata_preview(self, json_data):
        """Display a preview of the generated metadata."""
        # Look for the extraction result
        extraction_result = json_data.get("metadata_extraction_result", {})  # noqa: F841
        intermediate_metadata = json_data.get("intermediate_metadata", {})

        if not intermediate_metadata:
            print("   No intermediate metadata found")
            return

        # Display key metadata fields
        for field_name, field_data in intermediate_metadata.items():
            if isinstance(field_data, list) and field_data:
                print(f"   {field_name}: {len(field_data)} items")
                # Show first item as example
            elif field_data:
                print(f"   {field_name}: {field_data}")

    async def verify_civers_upload(self, request_id: str, local_json_path: str = None):
        """
        Verify that metadata was uploaded to CIVERS storage API.

        Checks if the file exists on the API and downloads it for comparison.

        Args:
            request_id: Request ID used for upload
            local_json_path: Path to local JSON file for comparison
        """
        print("\n🔎 Verifying CIVERS API Upload...")
        print("=" * 50)

        # Get storage results from Kafka event (we need snapshot_id)
        # For demo purposes, we'll construct expected snapshot_id
        # In real scenario, this comes from the storage result

        # Try to get snapshot_id from the CIVERS API
        # Format: {request_id}_{timestamp}
        import datetime
        # Estimate snapshot_id (format: req_demo_{id}_{timestamp})
        # Since we don't have exact timestamp, we'll need to check the response

        api_base_url = "http://localhost:8000/api"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # First, try to list artifacts for this request
                # We'll try different approaches to find the snapshot_id

                # Approach: Assume snapshot exists and try serve with a potential snapshot_id
                # Get currently available snapshots by trying to serve with request_id pattern
                # Note: In production, snapshot_id should come from storage_result

                print(f"📋 Checking  uploads for request: {request_id}")
                print(f"   API URL: {api_base_url}")

                # Try to find snapshot by checking serve endpoint with request_id pattern
                # The snapshot_id format is typically: {request_id}_{date}_{time}
                # Since we just uploaded, try with current date/time pattern

                # For demo: check if there's a recent snapshot
                # We need the snapshot_id from the upload response
                # Let's check the local file for storage_result info if available

                snapshot_id = None  # noqa: F841
                if local_json_path and Path(local_json_path).exists():  # noqa: ASYNC240
                    with open(local_json_path) as f:  # noqa: ASYNC230
                        data = json.load(f)  # noqa: F841
                        # Look for storage information in the metadata
                        # This would be added by the storage manager
                        print(f"✅ Local metadata file found: {local_json_path}")
                        # In a real scenario, snapshot_id would be in the storage result

                # For demo purposes, construct a likely snapshot_id
                # Format used by CIVERS API: {request_id}_{YYYYMMDD}_{HHMMSS}
                now = datetime.datetime.now()
                estimated_snapshot_id = f"{request_id}_{now.strftime('%Y%m%d_%H%M%S')}"

                # Try to download with estimated snapshot_id
                # Note: This might not work if timing doesn't match exactly
                serve_url = f"{api_base_url}/artifacts/serve"
                params = {"snapshot_id": estimated_snapshot_id, "type": "metadata.json"}

                print("\n📥 Attempting to download from CIVERS API...")
                print(f"   Snapshot ID (estimated): {estimated_snapshot_id}")
                print(f"   Serve URL: {serve_url}")

                response = await client.get(serve_url, params=params)

                if response.status_code == 200:
                    # Successfully downloaded!
                    downloaded_data = response.json()

                    print("\n✅ SUCCESS! Metadata downloaded from CIVERS API")
                    print(f"   Status Code: {response.status_code}")
                    print(f"   Content Type: {response.headers.get('content-type', 'unknown')}")
                    print(f"   Content Size: {len(response.content)} bytes")

                    # Save downloaded file for comparison
                    downloaded_path = self.output_dir / f"civers_downloaded_{request_id}.json"
                    with open(downloaded_path, "w", encoding="utf-8") as f:  # noqa: ASYNC230
                        json.dump(downloaded_data, f, indent=2, ensure_ascii=False)

                    print(f"📁 Downloaded file saved to: {downloaded_path}")

                    # Compare with local file if available
                    if local_json_path and Path(local_json_path).exists():  # noqa: ASYNC240
                        with open(local_json_path) as f:  # noqa: ASYNC230
                            local_data = json.load(f)

                        # Compare key fields
                        print("\n🔍 Comparing with local file...")
                        matches = self._compare_metadata(local_data, downloaded_data)

                        if matches:
                            print("✅ Files match - upload verified!")
                            return True
                        else:
                            print("⚠️  Files differ - possible issue")
                            return False
                    else:
                        # No local file to compare, but download successful
                        print("✅ Upload verified (download successful)")
                        return True

                elif response.status_code == 404:
                    print("\n⚠️  Snapshot not found on CIVERS API")
                    print(f"   Status: {response.status_code}")
                    print("   This could mean:")
                    print("   - The snapshot_id doesn't match (timing issue)")
                    print("   - File wasn't uploaded to CIVERS API")
                    print("   - Local file storage was used instead")
                    return False
                else:
                    print("\n❌ Unexpected response from CIVERS API")
                    print(f"   Status: {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
                    return False

        except httpx.ConnectError as e:
            print("\n❌ Cannot connect to CIVERS API")
            print(f"   Error: {e}")
            print(f"   Make sure CIVERS storage API is running at {api_base_url}")
            return False
        except Exception as e:
            print(f"\n❌ Error verifying upload: {e}")
            self.logger.error(f"Upload verification error: {e}", exc_info=True)
            return False

    def _compare_metadata(self, local_data: dict, downloaded_data: dict) -> bool:
        """
        Compare local and downloaded metadata.

        Returns True if key fields match.
        """
        # Compare key identifying fields
        local_request_id = (
            local_data.get("metadata_extraction_result", {})
            .get("request_information", {})
            .get("request_id")
        )
        downloaded_request_id = (
            downloaded_data.get("metadata_extraction_result", {})
            .get("request_information", {})
            .get("request_id")
        )

        if local_request_id and downloaded_request_id:
            match = local_request_id == downloaded_request_id
            print(f"   Request ID match: {match}")
            print(f"     Local: {local_request_id}")
            print(f"     Downloaded: {downloaded_request_id}")
            return match

        # If we can't find request_id, consider it a match if both have data
        return bool(local_data and downloaded_data)

    async def cleanup(self):
        """Cleanup resources."""
        try:
            if self.producer:
                await self.producer.stop()
            if self.consumer:
                await self.consumer.stop()
            print("✅ Demo cleanup completed")
        except Exception as e:
            self.logger.warning(f"Cleanup error: {e}")


async def main():
    """Main function."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="CIVERS Metadata Extractor - Simple Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using embedded HTML content (default):
  python simple_demo.py

  # Using document_url to download HTML:
  python simple_demo.py --document-url "http://127.0.0.1:8000/api/artifacts/serve?snapshot_id=req_123&type=document.html"
        """,
    )
    parser.add_argument(
        "--document-url",
        type=str,
        help="URL to download the HTML document from (enables document_url mode)",
    )
    parser.add_argument("--request-id", type=str, help="Request ID to use for the demo")
    args = parser.parse_args()

    print("🎯 CIVERS Metadata Extractor - Simple Demo")
    print("Arachne Archaeological Database Sample")
    print("=" * 50)

    if args.document_url:
        print("📥 Mode: Download HTML from document_url")
        print(f"   URL: {args.document_url}")
    else:
        print("💾 Mode: Use embedded HTML content")
    print()

    demo = SimpleDemo(document_url=args.document_url, request_id=args.request_id)

    try:
        # Initialize
        await demo.initialize()

        # Run demo
        await demo.run_demo()

    except KeyboardInterrupt:
        print("\n👋 Demo interrupted")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
    finally:
        await demo.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
