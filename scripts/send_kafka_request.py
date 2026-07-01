# send_kafka_request.py
"""Send test request messages to CiVers Kafka topics.

One sender for every request topic — pick the topic with --request-type.
`request_id` + `url` are the MINIMUM fields every consuming service requires
(each *RequestEvent model also accepts an optional priority). See REQUEST_SPECS.

To trigger the FULL stack workflow (AWI -> Orchestrator -> Archive Generator ->
Metadata Extractor -> ...) send to the orchestrator topic: --request-type orchestrator.
Sending --request-type archive (or metadata) hits that single service directly and
does NOT run the orchestrated workflow.
"""
from random import randint
from collections import namedtuple
import asyncio
import json
import logging
import argparse
import sys
from pathlib import Path

# Add project root and scripts directory to python path for imports
scripts_dir = Path(__file__).resolve().parent
repo_root = scripts_dir.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from config_loader import load_script_config, get_kafka_bootstrap
from aiokafka import AIOKafkaProducer

# logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# --- Supported request types -------------------------------------------------
# Maps a --request-type to the Kafka topic it is published on and the service
# that consumes it. `request_id` + `url` are the MINIMUM fields every consumer
# requires; each request event model also accepts an optional `priority`.
#
#   orchestrator -> orchestrator.requests -> Orchestrator
#                   TRIGGERS THE FULL WORKFLOW (archive -> metadata -> callback).
#                   Optional: workflow_name, callback_url, metadata.
#   archive      -> archive.requests      -> Archive Generator (archiving only).
#   metadata     -> metadata.requests     -> Metadata Extractor (extraction only;
#                   optionally add document_url or html_content as the content source).
#
#TODO: doi.requests (DOI service) and change.detection.requests (Change Detection) are
# declared in config but have no live Kafka consumer yet, so they are omitted here.
RequestSpec = namedtuple("RequestSpec", ["topic", "consumer"])
REQUEST_SPECS: dict[str, RequestSpec] = {
    "orchestrator": RequestSpec("orchestrator.requests", "Orchestrator (full-stack workflow)"),
    "archive": RequestSpec("archive.requests", "Archive Generator"),
    "metadata": RequestSpec("metadata.requests", "Metadata Extractor"),
}


class SendKafkaRequest:
    """Utility to send test archive requests using aiokafka."""
    def __init__(self,kafka_bootstrap_servers: str="localhost:29092"):
        # Get Kafka configuration
        self.bootstrap_servers = kafka_bootstrap_servers
        self.producer = None
    
    async def _ensure_producer(self):
        """Create and start the aiokafka producer if not already running."""
        if self.producer is None:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks=1,
                request_timeout_ms=30000,
            )
            await self.producer.start()

    def build_kafka_request_message(
        self,
        url: str,
        request_type: str,
        priority: int,
        request_id: str,
        document_url: str | None = None,
        html_content: str | None = None,
    ):
        """Build the (message, topic) pair for the given request type.

        `request_id` + `url` are the minimum every consuming service requires; the
        topic and consumer for each request type are defined in REQUEST_SPECS.
        """
        if request_type not in REQUEST_SPECS:
            supported = ", ".join(sorted(REQUEST_SPECS))
            raise ValueError(
                f"Unsupported request-type '{request_type}'. Supported: {supported}."
            )
        topic = REQUEST_SPECS[request_type].topic
        # Minimum contract accepted by every request consumer.
        message = {
            "request_id": request_id,
            "url": url,
            "priority": priority,
        }
        
        if request_type == "metadata":
            if document_url:
                message["document_url"] = document_url
            if html_content:
                message["html_content"] = html_content
            
            # Automatically resolve domain from URL
            from urllib.parse import urlparse
            try:
                domain = urlparse(url).netloc
                if domain:
                    message["domain"] = domain
            except Exception:
                pass
                
        return message, topic
        
    async def send_one(
        self,
        url: str,
        request_type: str,
        request_id: str | None = None,
        priority: int = 1,
        document_url: str | None = None,
        html_content: str | None = None,
    ) -> str:
        """Send a single request to the topic for request_type; return its request_id.

        For callers (e.g. the full-stack test) that need to submit one request with a
        known request_id and inspect it afterwards. Starts the producer if needed.
        """
        await self._ensure_producer()
        if request_id is None:
            request_id = f"test-request-{randint(1, 1_000_000)}"
        message, topic = self.build_kafka_request_message(
            url, request_type, priority, request_id, document_url, html_content
        )
        await self.producer.send_and_wait(
            topic=topic, key=message["request_id"], value=message
        )
        logger.info(f"✅ {request_type} request published to {topic} (request_id={request_id})")
        return request_id

    async def check_connection(self, timeout: float = 8.0) -> bool:
        """Return True if a producer can reach the broker (fast readiness probe).

        Uses a throwaway producer so it never disturbs self.producer, and bounds the
        wait with a timeout instead of the long default request timeout.
        """
        probe = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        try:
            await asyncio.wait_for(probe.start(), timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"❌ Cannot connect to Kafka at {self.bootstrap_servers}: {e}")
            return False
        finally:
            try:
                await probe.stop()
            except Exception:
                pass

    async def send_requests(
        self,
        urls: list[str],
        request_type: str,
        document_url: str | None = None,
        html_content: str | None = None,
    ):
        """Send requests for the given URLs to the topic for request_type."""
        if request_type not in REQUEST_SPECS:
            supported = ", ".join(sorted(REQUEST_SPECS))
            logger.error(f"❌ Unsupported request-type '{request_type}'. Supported: {supported}.")
            return
        await self._ensure_producer()

        logger.info(f"📤 Sending {len(urls)} {request_type} requests...")
        
        # If metadata request lacks both document_url and html_content, apply a fallback
        if request_type == "metadata":
            if html_content:
                html_path = Path(html_content)
                if html_path.exists() and html_path.is_file():
                    try:
                        logger.info(f"📄 Reading HTML content from file: {html_content}")
                        html_content = html_path.read_text(encoding="utf-8")
                    except Exception as e:
                        logger.error(f"❌ Failed to read HTML file '{html_content}': {e}")
            elif not document_url:
                logger.warning("⚠️ Neither --document-url nor --html-content provided for metadata request; using default HTML.")
                html_content = "<html><head><title>Test Page</title></head><body><h1>CIVERS Test</h1></body></html>"
        
        for i, url in enumerate(urls, 1):
            request_id = f"test-request-{i}-{randint(1, 1000)}"
            # Create request event  
            logger.info(f"url {url}, request type {request_type}, priority {i}, request id {request_id}")   
            request_event, topic = self.build_kafka_request_message(
                url, request_type, i, request_id, document_url, html_content
            )
            
            # Publish to archive.requests so the running service processes it
            try:
                await self.producer.send_and_wait(
                    topic=topic,
                    key=request_event['request_id'],
                    value=request_event
                )
                logger.info(f"✅ send {request_type} request {i} published on topic {topic}")
            except Exception as e:
                logger.error(f"❌ Failed to publish {request_type} request {i}: {e}")
            
            # Small delay between requests
            await asyncio.sleep(1)
        
        logger.info("✅ All archive requests published")
    
    async def close(self):
        """Close the producer."""
        logger.info("🛑 Closing producer...")
        if self.producer:
            await self.producer.stop()


def parse_arguments(default_bootstrap: str) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Send test requests to a CiVers Kafka topic. The default broker is loaded from "
            "the CiVers configuration; override it with the KAFKA_BOOTSTRAP_SERVERS env var or "
            "--kafka-bootstrap-servers. Pick the target topic with --request-type "
            "(orchestrator | archive | metadata). Use --request-type orchestrator to trigger "
            "the FULL stack workflow; archive/metadata hit that single service directly."
        ),
        epilog="""
    Examples:
      # Trigger the full pipeline via the orchestrator (recommended end-to-end):
      %(prog)s --urls https://example.com --request-type orchestrator
      # Hit the Archive Generator directly (archiving only):
      %(prog)s --urls https://example.com --request-type archive
      # Multiple URLs to the Metadata Extractor:
      %(prog)s --urls https://example.com https://httpbin.org/get --request-type metadata
      # Override the broker (e.g. inside Docker):
      %(prog)s --urls https://example.com --request-type orchestrator --kafka-bootstrap-servers kafka:9092
            """
    )
    
    parser.add_argument(
        "--urls",
        nargs="+",  
        required=True,
        help="URLs to archive."
    )    
    parser.add_argument(
        "--request-type",
        required=True,
        choices=sorted(REQUEST_SPECS),
        help=(
            "Target request topic: 'orchestrator' -> orchestrator.requests (runs the FULL "
            "workflow), 'archive' -> archive.requests (Archive Generator only), 'metadata' -> "
            "metadata.requests (Metadata Extractor only)."
        )
    )
    parser.add_argument(
        "--kafka-bootstrap-servers",
        default=default_bootstrap,
        help=f"Kafka bootstrap servers, default resolved from configuration: {default_bootstrap}."
    )
    parser.add_argument(
        "--document-url",
        default=None,
        help="For metadata requests: URL to download the HTML document from."
    )
    parser.add_argument(
        "--html-content",
        default=None,
        help="For metadata requests: Raw HTML content to process directly."
    )
    return parser.parse_args()


async def main(
    urls: list[str],
    request_type: str,
    kafka_bootstrap_servers: str,
    document_url: str | None = None,
    html_content: str | None = None,
):
    """Send or process archive requests for the specified URLs."""
    sender = SendKafkaRequest(kafka_bootstrap_servers)

    try:
        await sender.send_requests(urls, request_type, document_url, html_content)
    finally:
        await sender.close()


if __name__ == "__main__":
    # Load configuration
    config = load_script_config()
    default_bootstrap = get_kafka_bootstrap(config)
    
    # Parse command line arguments
    args = parse_arguments(default_bootstrap)
    
    logger.info("Args: %s", args)
    
    request_type = args.request_type
    urls = args.urls
    
    logger.info("📤 Kafka Request Sender")
    logger.info(f"Request Type: {request_type}")
    logger.info(f"Number of URLS to archive: {len(urls)}")
    for i, url in enumerate(urls, 1):
        logger.info(f"  {i}. {url}")
    logger.info("=" * 50)
    
    asyncio.run(main(
        urls,
        request_type,
        args.kafka_bootstrap_servers,
        args.document_url,
        args.html_content
    )) 