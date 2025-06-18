import cv2
import pika
from pika.exceptions import AMQPConnectionError
import logging
import json
from pathlib import Path
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define queue names
VIDEO_QUEUE = 'video_queue'
FRAME_QUEUE = 'frame_queue'
ASSEMBLY_QUEUE = 'assembly_queue'

def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost', heartbeat=600))
    channel = connection.channel()

    # Declare all necessary queues
    channel.queue_declare(queue=VIDEO_QUEUE, durable=True)
    channel.queue_declare(queue=FRAME_QUEUE, durable=True)
    channel.queue_declare(queue=ASSEMBLY_QUEUE, durable=True)
    
    logger.info("Video Splitter Worker started, waiting for video paths.")

    def callback(ch, method, properties, body):
        video_path_str = body.decode()
        video_path = Path(video_path_str)
        video_name = video_path.stem
        logger.info(f"Processing video: {video_path}")

        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            cap = cv2.VideoCapture(str(video_path))
            frame_number = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                _, frame_encoded = cv2.imencode('.jpg', frame)
                frame_bytes = frame_encoded.tobytes()

                frame_message = {
                    'video_path': video_path_str,
                    'frame_number': frame_number,
                    'frame': frame_bytes.hex()
                }
                channel.basic_publish(
                    exchange='',
                    routing_key=FRAME_QUEUE,
                    body=json.dumps(frame_message),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                frame_number += 1
            
            cap.release()
            logger.info(f"Finished splitting video {video_name}. Sent {frame_number} frames.")

            # After all frames are sent, send an assembly message
            assembly_message = {
                'video_name': video_name,
                'total_frames': frame_number,
                'video_path': video_path_str
            }
            channel.basic_publish(
                exchange='',
                routing_key=ASSEMBLY_QUEUE,
                body=json.dumps(assembly_message)
            )
            logger.info(f"Sent assembly instruction for {video_name}.")

        except Exception as e:
            logger.error(f"Error processing video {video_path}: {e}")
        finally:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=VIDEO_QUEUE, on_message_callback=callback)
    channel.start_consuming()

if __name__ == '__main__':
    while True:
        try:
            main()
        except AMQPConnectionError:
            logger.error("Connection to RabbitMQ failed. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}. Restarting worker...")
            time.sleep(5) 