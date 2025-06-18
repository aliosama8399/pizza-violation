import pika
import json
import logging
import time
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Queues to listen to
VIOLATION_QUEUE = 'violation_queue'
RESULTS_QUEUE = 'results_queue'
# API endpoint to forward messages to
API_ENDPOINT = "http://127.0.0.1:8000/violation_event"

def forward_event_to_api(ch, method, properties, body):
    """
    Callback function to forward a received message to the main web app's API.
    """
    try:
        # The body is binary, so decode it to a string, then parse JSON
        event_data = json.loads(body.decode())
        logger.info(f"Received event from queue '{method.routing_key}': {event_data}")
        
        # Forward the entire JSON payload to the FastAPI app's endpoint
        try:
            response = requests.post(API_ENDPOINT, json=event_data)
            # Raise an exception for bad status codes (4xx or 5xx)
            response.raise_for_status()
            logger.info(f"Successfully forwarded event to {API_ENDPOINT}.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to forward event to web app: {e}")
            # Potentially add a retry mechanism here or a dead-letter queue
            
        # Acknowledge the message was processed successfully
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from message body: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False) # Discard malformed message
    except Exception as e:
        logger.error(f"An unknown error occurred while processing message: {e}", exc_info=True)
        # Re-queueing might not be safe here, depending on the error
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost', heartbeat=600))
    channel = connection.channel()

    # Declare the queues this worker will consume from
    channel.queue_declare(queue=VIOLATION_QUEUE, durable=True)
    channel.queue_declare(queue=RESULTS_QUEUE, durable=True)
    
    logger.info(f"Results Worker started. Listening on '{VIOLATION_QUEUE}' and '{RESULTS_QUEUE}'.")
    
    # Set Quality of Service to handle one message at a time
    channel.basic_qos(prefetch_count=1)
    
    # Set up consumers for both queues
    channel.basic_consume(queue=VIOLATION_QUEUE, on_message_callback=forward_event_to_api)
    channel.basic_consume(queue=RESULTS_QUEUE, on_message_callback=forward_event_to_api)
    
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("Shutting down Results Worker.")
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == '__main__':
    while True:
        try:
            main()
        except pika.exceptions.AMQPConnectionError:
            logger.error("Connection to RabbitMQ failed. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred in results worker: {e}", exc_info=True)
            time.sleep(5) 