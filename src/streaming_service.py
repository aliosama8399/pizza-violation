from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import pika
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamingService:
    """
    Service that receives processed results and streams them to clients
    """
    def __init__(self, frames_dir="violation_frames"):
        self.frames_dir = Path(frames_dir)
        self.frames_dir.mkdir(exist_ok=True)
        self.setup_rabbitmq()
        self.setup_fastapi()
        self.violation_count = 0

    def setup_rabbitmq(self):
        """Setup RabbitMQ consumer for receiving results"""
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost')
            )
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue='streaming_results', durable=True)
            logger.info("Streaming Service connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def setup_fastapi(self):
        """Setup FastAPI backend for REST API and WebSocket"""
        self.app = FastAPI()

        # Serve static files (CSS and JS)
        self.app.mount("/static", StaticFiles(directory="static"), name="static")

        @self.app.get("/", response_class=HTMLResponse)
        async def read_root():
            """Serve the main HTML page"""
            return Path("templates/index.html").read_text()

        @self.app.get("/violations/count")
        async def get_violation_count():
            """Endpoint to get the total violation count"""
            return {"violation_count": self.violation_count}
        
    def process_results(self, ch, method, properties, body):
        """Process results and stream to clients"""
        try:
            result_data = json.loads(body)
            self.violation_count += result_data['violations']
            logger.info(f"Frame {result_data['frame_number']}: "
                       f"{len(result_data['detections'])} detections, "
                       f"{result_data['violations']} violations")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Error processing results: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    def start_streaming(self):
        """Start streaming service"""
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue='streaming_results',
            on_message_callback=self.process_results
        )
        
        logger.info("Streaming Service started. Processing results...")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping Streaming Service...")
            self.channel.stop_consuming()
            self.connection.close()