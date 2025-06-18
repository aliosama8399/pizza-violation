import cv2
import pika
import json
import logging
from pathlib import Path
import time
import os
from urllib.parse import quote # Import the URL encoder
from pika.exceptions import AMQPConnectionError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ASSEMBLY_QUEUE = 'assembly_queue'
PROCESSED_FRAMES_DIR = Path("processed_frames")
PROCESSED_VIDEOS_DIR = Path("processed_videos")
RESULTS_QUEUE = 'results_queue'

def assemble_video(ch, method, properties, body):
    try:
        data = json.loads(body)
        video_name = data['video_name']
        total_frames = data['total_frames']
        logger.info(f"Received assembly request for {video_name} with {total_frames} frames.")

        video_frame_dir = PROCESSED_FRAMES_DIR / video_name
        output_video_path = PROCESSED_VIDEOS_DIR / f"{video_name}_processed.mp4"

        # Wait for all frames to be ready
        max_wait_seconds = 300
        start_time = time.time()
        while True:
            ready_frames = len(list(video_frame_dir.glob("frame_*.jpg")))
            if ready_frames >= total_frames:
                logger.info(f"All {total_frames} frames for {video_name} are ready.")
                break
            if time.time() - start_time > max_wait_seconds:
                logger.error(f"Timeout waiting for frames for {video_name}. Aborting.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            time.sleep(2)

        frames = sorted(video_frame_dir.glob("frame_*.jpg"), key=lambda f: int(f.stem.split('_')[1]))
        if not frames:
            logger.error(f"No frames found in {video_frame_dir} to assemble.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        first_frame = cv2.imread(str(frames[0]))
        height, width, _ = first_frame.shape
        fourcc = cv2.VideoWriter.fourcc(*'avc1')
        video_writer = cv2.VideoWriter(str(output_video_path), fourcc, 25.0, (width, height))

        if not video_writer.isOpened():
            logger.error(f"Could not open video writer for path {output_video_path}.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        for frame_path in frames:
            video_writer.write(cv2.imread(str(frame_path)))
        video_writer.release()
        
        if not output_video_path.exists() or output_video_path.stat().st_size == 0:
            logger.error(f"Video assembly failed for {video_name}. Output file is missing or empty.")
        else:
            logger.info(f"Successfully assembled video: {output_video_path}")
            
            # --- THIS IS THE FIX: URL-encode the filename to handle spaces ---
            encoded_filename = quote(output_video_path.name)
            
            notification = {
                'type': 'video_ready',
                'video_name': video_name,
                'video_url': f"/processed_videos/{encoded_filename}" # Use the encoded name
            }
            ch.basic_publish(exchange='', routing_key=RESULTS_QUEUE, body=json.dumps(notification))

    except Exception as e:
        logger.error(f"Error during video assembly for {video_name}: {e}", exc_info=True)
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    PROCESSED_VIDEOS_DIR.mkdir(exist_ok=True)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost', heartbeat=600))
    channel = connection.channel()
    channel.queue_declare(queue=ASSEMBLY_QUEUE, durable=True)
    channel.queue_declare(queue=RESULTS_QUEUE, durable=True)
    logger.info("Video Assembler Worker started.")
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=ASSEMBLY_QUEUE, on_message_callback=assemble_video)
    channel.start_consuming()

if __name__ == '__main__':
    while True:
        try:
            main()
        except AMQPConnectionError:
            logger.error("Connection to RabbitMQ failed. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred in assembler worker: {e}", exc_info=True)
            time.sleep(5)