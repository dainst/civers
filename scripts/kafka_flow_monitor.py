import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root and scripts directory to python path for imports
scripts_dir = Path(__file__).resolve().parent
repo_root = scripts_dir.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from config_loader import load_script_config, get_kafka_bootstrap
from aiokafka import AIOKafkaConsumer

# ANSI Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class KafkaFlowMonitor:
    """
    Unified Kafka Workflow Monitor for CIVERS.
    Tracks requests across multiple topics to show the end-to-end flow.
    """

    def __init__(self, bootstrap_servers: str = "localhost:29092"):
        self.bootstrap_servers = bootstrap_servers
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.running = False
        
        # Track active requests to correlate events
        self.active_requests: Dict[str, Dict[str, Any]] = {}
        
        # Topic to Service mappings (Sender/Receiver inference)
        self.topic_roles = {
            "orchestrator.requests": ("Web/CLI", "Orchestrator"),
            "orchestrator.status": ("Orchestrator", "Monitor"),
            "orchestrator.completed": ("Orchestrator", "Web/CLI"),
            "orchestrator.failed": ("Orchestrator", "Web/CLI"),
            
            "metadata.requests": ("Orchestrator", "Metadata Extractor"),
            "metadata.started": ("Metadata Extractor", "Orchestrator"),
            "metadata.completed": ("Metadata Extractor", "Orchestrator"),
            "metadata.failed": ("Metadata Extractor", "Orchestrator"),
            
            "archive.requests": ("Orchestrator", "Archive Generator"),
            "archive.status": ("Archive Generator", "Orchestrator"),
            "archive.completed": ("Archive Generator", "Orchestrator"),
            "archive.failed": ("Archive Generator", "Orchestrator"),
            
            "doi.requests": ("Orchestrator", "DOI Service"),
            "doi.completed": ("DOI Service", "Orchestrator"),
            "doi.failed": ("DOI Service", "Orchestrator"),
        }

    async def start(self):
        """Initialize and start the Kafka consumer."""
        self.consumer = AIOKafkaConsumer(
            *self.topic_roles.keys(),
            bootstrap_servers=self.bootstrap_servers,
            group_id="civers_flow_monitor_group",
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest'
        )
        
        await self.consumer.start()
        self.running = True
        logger.info(f"{Colors.BOLD}{Colors.OKGREEN}🚀 CIVERS Kafka Flow Monitor Started{Colors.ENDC}")
        logger.info(f"Monitoring topics: {', '.join(self.topic_roles.keys())}")
        logger.info(f"Bootstrap servers: {self.bootstrap_servers}")
        logger.info("-" * 80)

        try:
            async for msg in self.consumer:
                if not self.running:
                    break
                await self.process_message(msg)
        finally:
            await self.consumer.stop()

    async def process_message(self, msg):
        """Process and format a Kafka message."""
        topic = msg.topic
        payload = msg.value
        request_id = payload.get("request_id", "unknown-id")
        
        sender, receiver = self.topic_roles.get(topic, ("Unknown", "Unknown"))
        
        # Color coding by topic type
        color = Colors.OKCYAN
        if ".failed" in topic:
            color = Colors.FAIL
        elif ".completed" in topic:
            color = Colors.OKGREEN
        elif ".requests" in topic:
            color = Colors.OKBLUE
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Print header
        print(f"[{timestamp}] {color}{topic.upper():<25}{Colors.ENDC} | ID: {Colors.BOLD}{request_id}{Colors.ENDC}")
        print(f"  {Colors.BOLD}From:{Colors.ENDC} {sender:<20} -> {Colors.BOLD}To:{Colors.ENDC} {receiver}")
        
        # Common fields extraction
        url = payload.get("url", "")
        status = payload.get("status", "")
        message = payload.get("message", "")
        error = payload.get("error_message", "")
        error_type = payload.get("error_type", "")
        failed_stage = payload.get("failed_stage", "")
        processing_time = payload.get("processing_time_seconds", "")
        created_at = payload.get("created_at", "")

        # Display extracted fields
        if url:
             print(f"  {Colors.BOLD}URL:{Colors.ENDC} {url}")
        
        if created_at:
             print(f"  {Colors.BOLD}Created At:{Colors.ENDC} {created_at}")

        if status or message:
             print(f"  {Colors.BOLD}Status:{Colors.ENDC} {status} {f'({message})' if message else ''}")
        
        if error or error_type:
             err_str = f"[{error_type}] " if error_type else ""
             err_str += error if error else "Unknown error"
             print(f"  {Colors.FAIL}Error: {err_str}{Colors.ENDC}")
             if failed_stage:
                 print(f"  {Colors.FAIL}Failed Stage: {failed_stage}{Colors.ENDC}")

        if processing_time:
             print(f"  {Colors.BOLD}Processing Time:{Colors.ENDC} {processing_time:.2f}s")

        # Specific payload fields based on topic
        if topic == "metadata.completed":
             mappers = payload.get("mappers_used", [])
             if mappers:
                 print(f"  {Colors.BOLD}Mappers Used:{Colors.ENDC} {', '.join(mappers)}")
             total_fields = payload.get("total_fields_extracted", 0)
             if total_fields:
                 print(f"  {Colors.BOLD}Fields Extracted:{Colors.ENDC} {total_fields}")
        
        if topic == "archive.completed":
             artifacts = payload.get("artifacts_created", [])
             if artifacts:
                 print(f"  {Colors.BOLD}Artifacts:{Colors.ENDC} {', '.join(artifacts)}")

        # Metadata inspection
        metadata = payload.get("metadata", {})
        if metadata:
            print(f"  {Colors.BOLD}Metadata:{Colors.ENDC}")
            for k, v in metadata.items():
                print(f"    - {k}: {v}")

        # Raw Detailed Payload (if requested via env var or if unexpected keys present)
        handled_keys = {
            "request_id", "url", "status", "message", "error_message", "error_type", 
            "failed_stage", "processing_time_seconds", "created_at", "metadata",
            "mappers_used", "artifacts_created", "total_fields_extracted"
        }
        
        remaining_data = {k: v for k, v in payload.items() if k not in handled_keys}
        
        verbose = os.getenv("VERBOSE", "false").lower() == "true"
        
        if verbose or remaining_data:
            if remaining_data:
                print(f"  {Colors.OKCYAN}Other Data:{Colors.ENDC}")
                for k, v in remaining_data.items():
                    # Format nested dicts nicely
                    if isinstance(v, dict):
                        print(f"    - {k}: {json.dumps(v, indent=6)}")
                    else:
                        print(f"    - {k}: {v}")
            
            if verbose:
                print(f"  {Colors.OKCYAN}Full JSON:{Colors.ENDC}")
                print(f"    {json.dumps(payload, indent=4).replace('\n', '\n    ')}")

        print("-" * 80)

    def stop(self):
        self.running = False

def load_kafka_config() -> str:
    """Load Kafka config using civers unified configuration loader."""
    config = load_script_config()
    return get_kafka_bootstrap(config)

if __name__ == "__main__":
    bootstrap_servers = load_kafka_config()
    monitor = KafkaFlowMonitor(bootstrap_servers=bootstrap_servers)
    
    try:
        asyncio.run(monitor.start())
    except KeyboardInterrupt:
        logger.info("\nStopping monitor...")
        monitor.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
