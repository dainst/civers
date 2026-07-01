import sys
import time
import argparse
import logging
from typing import Dict, Any, Callable, Optional
from transport_services.transport_service_interface import TransportServiceInterface
from configs.models import ConfigDataModel
from archive_services.archive_service_interface import ArchiveServiceInterface

logger = logging.getLogger(__name__)

class CliTransportService(TransportServiceInterface):
    """
    CLI transport service for running individual archive tasks.
    Parses a target URL and priority, triggers the ArchiveService directly, 
    and outputs the result to the console before exiting.
    """
    def __init__(self, config: ConfigDataModel, archive_service: ArchiveServiceInterface, args: Optional[list[str]] = None):
        self.config = config
        self.archive_service = archive_service
        self.args = args if args is not None else sys.argv[1:]
        self.running = False
        
    async def start(self) -> None:
        self.running = True
        parser = argparse.ArgumentParser(description="CiVers Archive Generator CLI Mode")
        parser.add_argument("--url", required=True, help="URL to archive")
        parser.add_argument("--request-id", default=None, help="Trace request ID")
        parser.add_argument("--priority", type=int, default=1, help="Job priority")
        
        parsed_args, _ = parser.parse_known_args(self.args)
        url = parsed_args.url
        request_id = parsed_args.request_id or f"cli-request-{int(time.time())}"
        priority = parsed_args.priority
        
        logger.info(f"🚀 CLI Transport: Archiving {url} (Request ID: {request_id})")
        start_time = time.time()
        
        try:
            result = await self.archive_service.create_archive(url, request_id, priority)
            elapsed = time.time() - start_time
            if result.get('success'):
                logger.info(f"✅ Successfully archived {url} in {elapsed:.2f}s")
                logger.info(f"   Archive path: {result.get('archive_path')}")
                logger.info(f"   Artifacts: {result.get('artifacts_created')}")
            else:
                raise RuntimeError(f"Archiving failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"❌ Critical error during archiving: {e}")
            raise
        finally:
            self.running = False

    async def stop(self) -> None:
        self.running = False

    def register_handler(self, topic: str, handler: Callable) -> None:
        pass

    async def health_check(self) -> Dict[str, Any]:
        return {
            "healthy": True,
            "service_name": "CliTransportService",
            "details": {"running": self.running}
        }

    async def send_response(self, destination: str, message: Dict[str, Any], **kwargs) -> bool:
        logger.info(f"📤 CLI Event Response [{destination}]: {message}")
        return True

    def get_transport_info(self) -> Dict[str, Any]:
        return {"type": "CLI"}
