import aio_pika
import json
from typing import Any, Dict, Optional, Callable
import asyncio
from contextlib import asynccontextmanager


class RabbitMQClient:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None

    async def connect(self):
        """Establish connection to RabbitMQ"""
        self.connection = await aio_pika.connect_robust(self.connection_string)
        self.channel = await self.connection.channel()

        # Set prefetch count for fair dispatch
        await self.channel.set_qos(prefetch_count=1)

    async def close(self):
        """Close connection"""
        if self.connection:
            await self.connection.close()

    async def publish(self, queue_name: str, message: Dict[str, Any], persistent: bool = True):
        """Publish message to queue"""
        if not self.channel:
            await self.connect()

        # Declare queue
        queue = await self.channel.declare_queue(
            queue_name,
            durable=True  # Survive broker restart
        )

        # Create message
        message_body = json.dumps(message).encode()
        rabbitmq_message = aio_pika.Message(
            body=message_body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT if persistent else aio_pika.DeliveryMode.TRANSIENT
        )

        # Publish message
        await self.channel.default_exchange.publish(
            rabbitmq_message,
            routing_key=queue_name
        )

    async def consume(self, queue_name: str, callback: Callable, auto_ack: bool = False):
        """Consume messages from queue"""
        if not self.channel:
            await self.connect()

        # Declare queue
        queue = await self.channel.declare_queue(
            queue_name,
            durable=True
        )

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        message_body = json.loads(message.body.decode())
                        await callback(message_body)

                        if not auto_ack:
                            await message.ack()
                    except Exception as e:
                        if not auto_ack:
                            await message.nack(requeue=False)
                        # Log error
                        print(f"Error processing message: {e}")


# Singleton instance
_rabbitmq_client: Optional[RabbitMQClient] = None


async def get_rabbitmq_client() -> RabbitMQClient:
    global _rabbitmq_client
    if _rabbitmq_client is None:
        _rabbitmq_client = RabbitMQClient("amqp://guest:guest@rabbitmq:5672/")
        await _rabbitmq_client.connect()
    return _rabbitmq_client