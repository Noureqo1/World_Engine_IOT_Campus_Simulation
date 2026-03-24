"""
MQTT Publisher Module

Provides async MQTT publishing functionality using aiomqtt.
Handles connection management and graceful reconnection.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiomqtt

logger = logging.getLogger(__name__)


class MQTTPublisher:
    """
    Async MQTT publisher with connection pooling.

    This class manages a single MQTT connection that can be shared
    across multiple room coroutines for efficient broker communication.
    """

    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        client_id: str = "world_engine"
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self._client: aiomqtt.Client | None = None
        self._connected = False
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiomqtt.Client, None]:
        """
        Context manager for MQTT connection.

        Yields an active MQTT client connection. The connection is
        maintained for the lifetime of the context.

        Usage:
            async with publisher.connection() as client:
                await client.publish(topic, payload)
        """
        async with aiomqtt.Client(
            hostname=self.broker_host,
            port=self.broker_port,
            identifier=self.client_id
        ) as client:
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            yield client

    async def publish(
        self,
        client: aiomqtt.Client,
        topic: str,
        payload: str,
        qos: int = 0
    ) -> None:
        """
        Publish a message to an MQTT topic.

        This method is non-blocking and safe for concurrent use.

        Args:
            client: Active aiomqtt client
            topic: MQTT topic path
            payload: JSON string payload
            qos: Quality of Service level (0, 1, or 2)
        """
        try:
            await client.publish(topic, payload, qos=qos)
            logger.debug(f"Published to {topic}")
        except aiomqtt.MqttError as e:
            logger.error(f"MQTT publish error: {e}")
            raise


class MockMQTTClient:
    """
    Mock MQTT client for testing without a broker.

    Logs all publish operations instead of sending to broker.
    """

    def __init__(self, log_publishes: bool = False):
        self.log_publishes = log_publishes
        self.message_count = 0

    async def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        """Mock publish that just counts messages."""
        self.message_count += 1
        if self.log_publishes:
            logger.info(f"[MOCK] {topic}: {payload[:100]}...")
        elif self.message_count % 100 == 0:
            logger.info(f"[MOCK] Published {self.message_count} messages")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@asynccontextmanager
async def get_mqtt_client(
    broker_host: str = "localhost",
    broker_port: int = 1883,
    client_id: str = "world_engine",
    use_mock: bool = False,
    max_retries: int = 10,
    retry_delay: float = 3.0
) -> AsyncGenerator[aiomqtt.Client | MockMQTTClient, None]:
    """
    Factory function to get an MQTT client (real or mock).

    Includes connection retry logic for Docker environments where
    the broker might not be immediately available.

    Args:
        broker_host: MQTT broker hostname
        broker_port: MQTT broker port
        client_id: Client identifier
        use_mock: If True, return a mock client for testing
        max_retries: Maximum connection attempts
        retry_delay: Seconds between retry attempts

    Yields:
        MQTT client instance
    """
    if use_mock:
        client = MockMQTTClient(log_publishes=False)
        yield client
        logger.info(f"Mock session complete: {client.message_count} messages")
    else:
        # Retry logic for Docker environments
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Connecting to MQTT broker at {broker_host}:{broker_port} "
                    f"(attempt {attempt}/{max_retries})"
                )
                async with aiomqtt.Client(
                    hostname=broker_host,
                    port=broker_port,
                    identifier=client_id
                ) as client:
                    logger.info(f"Connected to MQTT broker at {broker_host}:{broker_port}")
                    yield client
                    return  # Success - exit after context manager completes
            except aiomqtt.MqttError as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"MQTT connection failed: {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"MQTT connection failed after {max_retries} attempts")
                    raise
