#!/usr/bin/env python3
import os
import json
import uuid
import pika
import ssl
import time
import logging
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RabbitMQ connection parameters
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT'))
RABBITMQ_USER = os.environ.get('RABBITMQ_USER')
RABBITMQ_PASS = os.environ.get('RABBITMQ_PASS')
RABBITMQ_VHOST = os.environ.get('RABBITMQ_VHOST')

# Queue names
REQUEST_QUEUE = 'vectordb_request_queue'
RESPONSE_QUEUE = 'vectordb_response_queue'


class AIEngine:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.response = None
        self.corr_id = None
        self.connect_to_rabbitmq()

    def connect_to_rabbitmq(self):
        """Establish connection to RabbitMQ"""
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        ssl_options = pika.SSLOptions(context=ssl.create_default_context())

        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300,
            ssl_options=ssl_options,
            virtual_host=RABBITMQ_VHOST
        )

        # Retry connection until successful
        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            try:
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()

                # Declare queues
                self.channel.queue_declare(queue=REQUEST_QUEUE, durable=True)
                self.channel.queue_declare(queue=RESPONSE_QUEUE, durable=True)

                # Set up callback queue for responses
                result = self.channel.queue_declare(queue='', exclusive=True)
                self.callback_queue = result.method.queue

                self.channel.basic_consume(
                    queue=self.callback_queue,
                    on_message_callback=self.on_response,
                    auto_ack=True
                )

                logger.info("Successfully connected to RabbitMQ")
                return
            except Exception as e:
                retry_count += 1
                logger.error(f"Failed to connect to RabbitMQ (attempt {retry_count}/{max_retries}): {e}")
                time.sleep(5)

        raise Exception("Failed to connect to RabbitMQ after multiple attempts")

    def on_response(self, ch, method, props, body):
        """Callback when response is received"""
        if self.corr_id == props.correlation_id:
            self.response = body

    def query_vectordb(self, query_text: str, collection_name: str,
                       operation: str = "query", n_results: int = 5,
                       extra_params: dict = None) -> Dict[str, Any]:
        """
        Send a query request to VectorDB through RabbitMQ

        Args:
            query_text: The query text
            collection_name: Name of the collection to query
            operation: Type of operation (query, get_all, add, delete)
            n_results: Number of results to return for query operation
            extra_params: Additional parameters to include in the request

        Returns:
            Dictionary with response from VectorDB
        """
        self.response = None
        self.corr_id = str(uuid.uuid4())

        logger.info(f"AIEngine sending '{operation}' request with query: '{query_text}'")
        # Prepare request payload
        request = {
            "operation": operation,
            "collection": collection_name,
            "query_text": query_text,
            "n_results": n_results,
            "timestamp": time.time()
        }

        # Add any extra parameters
        if extra_params:
            request.update(extra_params)

        # Publish request to queue
        self.channel.basic_publish(
            exchange='',
            routing_key=REQUEST_QUEUE,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
                delivery_mode=2,  # make message persistent
            ),
            body=json.dumps(request)
        )

        logger.info(f"Sent {operation} request for collection: {collection_name}")

        # Wait for response with timeout
        timeout = 30  # seconds
        start_time = time.time()
        while self.response is None:
            self.connection.process_data_events()
            if time.time() - start_time > timeout:
                return {"status": "error", "error": "Request timed out"}
            time.sleep(0.1)

        # Parse and return response
        try:
            return json.loads(self.response)
        except Exception as e:
            return {"status": "error", "error": f"Failed to parse response: {e}",
                    "raw_response": self.response.decode()}

    def close(self):
        """Close the connection to RabbitMQ"""
        if self.connection:
            self.connection.close()
            logger.info("Closed RabbitMQ connection")
