#!/usr/bin/env python3
"""
Create all required Kafka topics based on app_config.yaml configuration.
"""

import asyncio

import yaml
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError


def load_topics_from_config(config_path="app_config.yaml"):
    """Load topic configuration from YAML file."""
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        topics = config.get("app", {}).get("transport", {}).get("kafka", {}).get("topics", {})
        return topics
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return {}


async def create_topics():
    """Create all required topics using async admin client."""
    print("🔧 Creating Kafka topics...")

    # Load topic configuration
    topic_config = load_topics_from_config()
    if not topic_config:
        print("❌ No topic configuration found")
        return False

    # Create async admin client
    try:
        admin_client = AIOKafkaAdminClient(
            bootstrap_servers="localhost:29092", request_timeout_ms=30000
        )
        await admin_client.start()
        print("✅ Connected to async Kafka admin client")
    except Exception as e:
        print(f"❌ Failed to connect to Kafka: {e}")
        return False

    # Create topic objects
    topics_to_create = []
    for topic_key, topic_name in topic_config.items():
        topic_obj = NewTopic(name=topic_name, num_partitions=3, replication_factor=1)
        topics_to_create.append(topic_obj)
        print(f"📋 Prepared topic: {topic_name}")

    # Create topics
    try:
        await admin_client.create_topics(topics_to_create, validate_only=False)
        print(f"✅ Successfully created {len(topics_to_create)} topics")

        # Wait a moment for topics to be fully created
        await asyncio.sleep(2)

        # List created topics to verify
        cluster_metadata = await admin_client.describe_cluster()
        if hasattr(cluster_metadata, "topics"):
            created_topics = list(cluster_metadata.topics.keys())

            print("📋 Currently available topics:")
            for topic in sorted(created_topics):
                print(f"   - {topic}")
        else:
            print("📋 Topics created successfully")

        return True

    except TopicAlreadyExistsError:
        print("⚠️ Some topics already exist, which is fine")
        return True
    except Exception as e:
        print(f"❌ Failed to create topics: {e}")
        return False
    finally:
        await admin_client.close()


async def main():
    """Async main function."""
    success = await create_topics()
    return 0 if success else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
