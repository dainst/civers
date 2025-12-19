import subprocess
import time
import os
import logging
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_kafka_connection():
    """Check if Kafka Docker container is running and accessible."""
    try:
        from kafka import KafkaProducer
        
        producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            request_timeout_ms=10000,  # Longer timeout for Docker
            api_version_auto_timeout_ms=10000
        )
        producer.close()
        logger.info("✅ Kafka connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ Kafka connection failed: {e}")
        return False

def setup_kafka_topics():
    from kafka.admin import KafkaAdminClient, NewTopic
    from kafka.errors import TopicAlreadyExistsError
    import logging

    logger = logging.getLogger(__name__)
    
    topics_to_create = [
        "archive.requests",
        "archive.status", 
        "archive.completed",
        "archive.failed"
    ]
    
    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers='localhost:29092',
            request_timeout_ms=10000
        )

        topic_list = [
            NewTopic(name=topic_name, num_partitions=3, replication_factor=1)
            for topic_name in topics_to_create
        ]

        # Attempt to create topics
        admin_client.create_topics(new_topics=topic_list, validate_only=False)
        
        for topic in topics_to_create:
            logger.info(f"✅ Topic '{topic}' created successfully or already exists.")

        admin_client.close()
        return True

    except TopicAlreadyExistsError as e:
        logger.info(f"✅ Topic already exists: {e}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to setup topics: {e}")
        return False
    
def start_kafka_container():
    """Start Kafka using docker-compose."""
    try:
        logger.info("Starting Kafka container...")
        result = subprocess.run(
            ["docker-compose", "up", "-d", "broker"],
            capture_output=True,
            text=True,
            cwd="."  # Make sure you're in the directory with docker-compose.yml
        )
        
        if result.returncode == 0:
            logger.info("✅ Kafka container started")
            # Wait a bit for Kafka to be ready
            logger.info("Waiting for Kafka to be ready...")
            time.sleep(10)
            return True
        else:
            logger.error(f"❌ Failed to start Kafka: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error starting Kafka container: {e}")
        return False

def check_container_status():
    """Check if Kafka container is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=broker", "--format", "table {{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True
        )
        
        if "broker" in result.stdout and "Up" in result.stdout:
            logger.info("✅ Kafka container is running")
            return True
        else:
            logger.warning("⚠️ Kafka container is not running")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error checking container status: {e}")
        return False

if __name__ == "__main__":
    print("=== Setting up Kafka with Docker ===")
    
    # Check if container is running
    # if not check_container_status():
    #     print("Starting Kafka container...")
    #     if not start_kafka_container():
    #         exit(1)
    
    # Wait a bit more and check connection
    #time.sleep(5)
    if check_kafka_connection():
        print("Setting up topics...")
        setup_kafka_topics()
        print("\n🎉 Kafka setup completed!")
    else:
        print("\n❌ Kafka is not ready. Try running:")
        print("docker-compose up -d broker")
        print("Then wait 10-15 seconds and run this script again.")