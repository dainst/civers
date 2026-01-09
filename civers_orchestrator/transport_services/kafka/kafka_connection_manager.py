"""
Kafka Connection Manager for CiVers Orchestrator.

This module provides centralized management of Kafka producer and consumer connections
using aiokafka for asynchronous messaging.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError

from configs.models import KafkaConfig

logger = logging.getLogger(__name__)


class KafkaConnectionManager:
    """
    Manages Kafka producer and consumer connections with health monitoring.
    """
    
    def __init__(self, kafka_config: KafkaConfig):
        """
        Initialize the Kafka connection manager.
        
        Args:
            kafka_config: Kafka configuration containing bootstrap servers, topics, etc.
        """
        self.kafka_config = kafka_config
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._connection_status = {
            'producer_started': False,
            'consumer_started': False
        }
    
    async def setup_producer(self) -> AIOKafkaProducer:
        """Initialize async Kafka producer."""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks=self.kafka_config.producer.acks,
                request_timeout_ms=30000,
                retry_backoff_ms=1000,
            )
            await self.producer.start()
            self._connection_status['producer_started'] = True
            logger.info("✅ Async Kafka producer initialized successfully")
            return self.producer
        except Exception as e:
            self._connection_status['producer_started'] = False
            logger.error(f"❌ Failed to initialize async Kafka producer: {e}")
            raise KafkaError(f"Producer setup failed: {e}")
    
    async def setup_consumer(self, topics: List[str]) -> AIOKafkaConsumer:
        """Initialize async Kafka consumer for specified topics."""
        if not topics:
            raise ValueError("At least one topic must be provided for consumer setup")
        
        try:
            self.consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                group_id=self.kafka_config.consumer.group_id,
                value_deserializer=self._safe_json_deserializer,
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset=self.kafka_config.consumer.auto_offset_reset,
                enable_auto_commit=True,
                request_timeout_ms=30000,
            )
            await self.consumer.start()
            self._connection_status['consumer_started'] = True
            logger.info(f"✅ Async Kafka consumer initialized for topics: {topics}")
            return self.consumer
        except Exception as e:
            self._connection_status['consumer_started'] = False
            logger.error(f"❌ Failed to initialize async Kafka consumer: {e}")
            raise KafkaError(f"Consumer setup failed: {e}")
    
    async def cleanup(self) -> None:
        """Clean up Kafka connections."""
        logger.info("🧹 Cleaning up Kafka connections")
        if self.producer:
            try:
                await self.producer.stop()
            except Exception as e:
                logger.warning(f"⚠️ Error stopping async Kafka producer: {e}")
            finally:
                self.producer = None
        
        if self.consumer:
            try:
                await self.consumer.stop()
            except Exception as e:
                logger.warning(f"⚠️ Error stopping async Kafka consumer: {e}")
            finally:
                self.consumer = None
        
        self._connection_status = {'producer_started': False, 'consumer_started': False}
    
    @staticmethod
    def _safe_json_deserializer(message_bytes):
        """Safe JSON deserializer."""
        if message_bytes is None:
            return None
        try:
            return json.loads(message_bytes.decode('utf-8'))
        except Exception as e:
            logger.warning(f"⚠️ Failed to deserialize message as JSON: {e}")
            return message_bytes
