"""
Kafka Connection Manager

This module provides centralized management of Kafka producer and consumer connections
with robust error handling, configuration validation, and health monitoring.
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
    
    This class provides centralized management of Kafka connections, including:
    - Producer and consumer setup with proper configuration
    - Connection health checking and validation
    - Resource cleanup and error handling
    - Connection status monitoring
    """
    
    def __init__(self, kafka_config: KafkaConfig):
        """
        Initialize the Kafka connection manager.
        
        Args:
            kafka_config: Kafka configuration containing bootstrap servers, topics, etc.
        """
        self.kafka_config = kafka_config
        # Optional for lazy initialization - connections created only when needed
        self.producer: Optional[AIOKafkaProducer] = None  # Created via setup_producer()
        self.consumer: Optional[AIOKafkaConsumer] = None  # Created via setup_consumer() with topics
        self._connection_status = {
            'producer_started': False,
            'consumer_started': False
        }
    
    async def setup_producer(self) -> AIOKafkaProducer:
        """
        Initialize async Kafka producer with robust error handling.
        
        Returns:
            AIOKafkaProducer: Configured async Kafka producer instance
            
        Raises:
            KafkaError: If producer initialization fails
        """
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks=1,  # Wait for leader acknowledgment
                request_timeout_ms=30000,  # Longer timeout for Docker
                retry_backoff_ms=1000,  # Backoff time between retries
                max_request_size=1048576,  # 1MB max request size
            )
            
            # Start the async producer
            await self.producer.start()
            
            self._connection_status['producer_started'] = True
            logger.info("✅ Async Kafka producer initialized and started successfully")
            return self.producer
            
        except Exception as e:
            self._connection_status['producer_started'] = False
            logger.error(f"❌ Failed to initialize async Kafka producer: {e}")
            raise KafkaError(f"Producer setup failed: {e}")
    
    async def setup_consumer(self, topics: List[str]) -> AIOKafkaConsumer:
        """
        Initialize async Kafka consumer for specified topics.
        
        Args:
            topics: List of topic names to consume from
            
        Returns:
            AIOKafkaConsumer: Configured async Kafka consumer instance
            
        Raises:
            KafkaError: If consumer initialization fails
            ValueError: If no topics provided
        """
        if not topics:
            raise ValueError("At least one topic must be provided for consumer setup")
        
        try:
            self.consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=self.kafka_config.bootstrap_servers,
                group_id=self.kafka_config.consumer_group,
                value_deserializer=self._safe_json_deserializer,
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset='earliest',  # Start from beginning for testing
                enable_auto_commit=True,
                request_timeout_ms=30000,  # 30 second timeout for Docker
            )
            
            # Start the async consumer
            await self.consumer.start()
            
            self._connection_status['consumer_started'] = True
            logger.info(f"✅ Async Kafka consumer initialized and started for topics: {topics}")
            return self.consumer
            
        except Exception as e:
            self._connection_status['consumer_started'] = False
            logger.error(f"❌ Failed to initialize async Kafka consumer: {e}")
            raise KafkaError(f"Consumer setup failed: {e}")
    
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get current connection status without performing new health checks.
        
        Returns:
            Dict containing current connection status information
        """
        return self._connection_status.copy()
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate Kafka configuration settings.
        
        Returns:
            Dict containing validation results:
            - valid: Overall validity (bool)
            - errors: List of validation errors (List[str])
            - warnings: List of validation warnings (List[str])
        """
        errors = []
        warnings = []
        
        # Validate bootstrap servers
        if not self.kafka_config.bootstrap_servers:
            errors.append("Bootstrap servers not configured")
        elif not isinstance(self.kafka_config.bootstrap_servers, str):
            errors.append("Bootstrap servers must be a string")
        
        # Validate consumer group
        if not self.kafka_config.consumer_group:
            errors.append("Consumer group not configured")
        
        # Validate topics
        if not self.kafka_config.topics:
            warnings.append("No topics configured")
        elif not isinstance(self.kafka_config.topics, dict):
            errors.append("Topics must be a dictionary")
        
        # Validate at least one topic is configured
        if isinstance(self.kafka_config.topics, dict) and len(self.kafka_config.topics) == 0:
            errors.append("At least one topic must be configured")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'topics_count': len(self.kafka_config.topics) if self.kafka_config.topics else 0
        }
    
    async def cleanup(self) -> None:
        """
        Clean up Kafka connections and resources.
        
        Safely closes producer and consumer connections with proper error handling.
        """
        logger.info("🧹 Cleaning up Kafka connections")
        
        # Stop async producer
        if self.producer:
            try:
                await self.producer.stop()
                logger.info("✅ Async Kafka producer stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping async Kafka producer: {e}")
            finally:
                self.producer = None
        
        # Stop async consumer
        if self.consumer:
            try:
                await self.consumer.stop()
                logger.info("✅ Async Kafka consumer stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping async Kafka consumer: {e}")
            finally:
                self.consumer = None
        
        # Reset connection status
        self._connection_status = {
            'producer_started': False,
            'consumer_started': False
        }
        
        logger.info("✅ Kafka connection cleanup completed")
    
    @staticmethod
    def _safe_json_deserializer(message_bytes):
        """
        Safe JSON deserializer that handles malformed messages gracefully.
        
        Args:
            message_bytes: Raw message bytes
            
        Returns:
            Dict, str, or bytes: Deserialized JSON object, or original data if deserialization fails
        """
        if message_bytes is None:
            return None
            
        try:
            # Decode bytes to string
            decoded_string = message_bytes.decode('utf-8')
            
            # Parse JSON
            parsed_data = json.loads(decoded_string)
            
            return parsed_data
            
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            # Log the error but return the raw bytes for downstream handling
            logger.warning(f"⚠️ Failed to deserialize message as JSON: {e}")
            logger.debug(f"   Raw bytes (first 100): {message_bytes[:100]}...")
            
            # Return raw bytes - let downstream code handle it
            return message_bytes
        except Exception as e:
            logger.error(f"❌ Unexpected error in JSON deserializer: {e}")
            return message_bytes