import cv2
import pika
import logging
import json
from pathlib import Path
import numpy as np
from ultralytics import YOLO
from datetime import datetime
import time
from pika.exceptions import AMQPConnectionError
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MODEL_PATH = "yolo12m-v2.pt"
FRAME_QUEUE = 'frame_queue'
VIOLATION_QUEUE = 'violation_queue'
PROCESSED_FRAMES_DIR = Path("processed_frames")
VIOLATION_FRAMES_DIR = Path("violation_frames")
ROI = np.array([(400, 260), (560, 260), (460, 740), (300, 740)], dtype=np.int32)
VIOLATION_COOLDOWN = 30

HANDS_IN_ROI = {}
NEXT_HAND_ID = {}
VIOLATION_COUNT = {}
LAST_VIOLATION_TIME = {}

def process_frame_message(ch, method, properties, body, model):
    try:
        data = json.loads(body)
        video_path = Path(data['video_path'])
        video_name = video_path.stem
        frame_number = data['frame_number']

        if video_name not in HANDS_IN_ROI:
            HANDS_IN_ROI[video_name] = {}
            NEXT_HAND_ID[video_name] = 0
            VIOLATION_COUNT[video_name] = 0
            LAST_VIOLATION_TIME[video_name] = {}

        frame = cv2.imdecode(np.frombuffer(bytes.fromhex(data['frame']), np.uint8), cv2.IMREAD_COLOR)
        processed_frame = frame.copy()
        cv2.polylines(processed_frame, [ROI], True, (0, 255, 255), 2)
        results = model(frame, verbose=False)[0]

        current_hands = []
        current_scoopers = []
        for *box, conf, cls in results.boxes.data.cpu().numpy():
            x1, y1, x2, y2 = map(int, box)
            label = model.names[int(cls)]
            color = (0, 255, 0) if label == 'scooper' else (255, 0, 0)
            cv2.rectangle(processed_frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(processed_frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            detection = {'bbox': [x1, y1, x2, y2], 'center': ((x1 + x2) // 2, (y1 + y2) // 2)}
            if label == 'hand':
                current_hands.append(detection)
            elif label == 'scooper':
                current_scoopers.append(detection)

        hands_to_remove = []
        for hand_id, hand_info in HANDS_IN_ROI[video_name].items():
            hand_is_present = False
            for hand in current_hands:
                if np.hypot(hand['center'][0] - hand_info['last_pos'][0], hand['center'][1] - hand_info['last_pos'][1]) < 75:
                    hand_is_present = True
                    hand_info['last_pos'] = hand['center']
                    in_roi = cv2.pointPolygonTest(ROI, hand['center'], False) >= 0
                    if not in_roi and not hand_info.get('left_checked'):
                        has_scooper = any(np.hypot(s['center'][0] - hand['center'][0], s['center'][1] - hand['center'][1]) < 100 for s in current_scoopers)
                        if not has_scooper and (frame_number - LAST_VIOLATION_TIME[video_name].get(hand_id, -VIOLATION_COOLDOWN)) > VIOLATION_COOLDOWN:
                            VIOLATION_COUNT[video_name] += 1
                            LAST_VIOLATION_TIME[video_name][hand_id] = frame_number
                            
                            timestamp = datetime.now()
                            v_frame_path = VIOLATION_FRAMES_DIR / f"violation_{video_name}_{VIOLATION_COUNT[video_name]}_{frame_number}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
                            cv2.imwrite(str(v_frame_path), processed_frame)
                            
                            web_frame_path = f"/violation_frames/{v_frame_path.name}"
                            violation_type = "Hand left ROI without scooper"
                            
                            violation_message = {
                                'type': 'violation',
                                'video_name': video_name,
                                'violation_frame_path': web_frame_path,
                                'frame_number': frame_number,
                                'timestamp': timestamp.isoformat(),
                                'violation_type': violation_type,
                                'bbox': hand['bbox'] # Add the bounding box
                            }
                            ch.basic_publish(exchange='', routing_key=VIOLATION_QUEUE, body=json.dumps(violation_message))
                            logger.info(f"Violation detected for {video_name} at frame {frame_number}.")

                        hand_info['left_checked'] = True
                    break
            if not hand_is_present:
                hands_to_remove.append(hand_id)
        
        for hand_id in hands_to_remove:
            del HANDS_IN_ROI[video_name][hand_id]

        for hand in current_hands:
            if cv2.pointPolygonTest(ROI, hand['center'], False) >= 0:
                is_new = not any(np.hypot(hand['center'][0] - i['last_pos'][0], hand['center'][1] - i['last_pos'][1]) < 75 for i in HANDS_IN_ROI[video_name].values())
                if is_new:
                    hand_id = NEXT_HAND_ID[video_name]
                    HANDS_IN_ROI[video_name][hand_id] = {'last_pos': hand['center'], 'left_checked': False}
                    NEXT_HAND_ID[video_name] += 1

        video_frame_dir = PROCESSED_FRAMES_DIR / video_name
        video_frame_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(video_frame_dir / f"frame_{frame_number:04d}.jpg"), processed_frame)

    except Exception as e:
        logger.error(f"Error processing frame message: {e}", exc_info=True)
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    model = YOLO(MODEL_PATH)
    VIOLATION_FRAMES_DIR.mkdir(exist_ok=True)
    PROCESSED_FRAMES_DIR.mkdir(exist_ok=True)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost', heartbeat=600))
    channel = connection.channel()
    channel.queue_declare(queue=FRAME_QUEUE, durable=True)
    channel.queue_declare(queue=VIOLATION_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=FRAME_QUEUE, on_message_callback=lambda ch, method, properties, body: process_frame_message(ch, method, properties, body, model))
    logger.info("Detection Service worker started.")
    channel.start_consuming()

if __name__ == '__main__':
    while True:
        try:
            main()
        except AMQPConnectionError:
            logger.error("Connection to RabbitMQ failed. Retrying...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            time.sleep(5)