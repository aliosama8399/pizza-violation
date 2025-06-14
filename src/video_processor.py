from ultralytics import YOLO
import cv2
import numpy as np
from datetime import datetime
import logging
import os
from pathlib import Path
import pika
import asyncio
import aiohttp

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoProcessor:
    """
    Service that processes video and sends detection data to message broker
    """
    def __init__(self, model_path="yolo12m-v2.pt"):
        self.model = YOLO(model_path)
        # Define ROI polygon for ingredient bowls
        self.ingredient_roi = np.array([
            (400, 260), (560, 260), (460, 740), (300, 740)
        ], dtype=np.int32)
        self.violation_count = 0
        self.last_violation_time = 0  # To prevent duplicate violations
        self.violation_cooldown = 30  # Frames between violations
        self.connection = None
        self.channel = None
        
        # Create violation frames directory
        self.frames_dir = Path("violation_frames")
        self.frames_dir.mkdir(exist_ok=True)

        # Track hands that entered ROI
        self.hands_in_roi = {}  # Format: {hand_id: {'entered_with_scooper': bool, 'last_pos': (x,y)}}
        self.next_hand_id = 0

    def ensure_connection(self):
        """Ensure RabbitMQ connection is active"""
        try:
            if not self.connection or self.connection.is_closed:
                self.connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host='localhost',
                        heartbeat=600,
                        blocked_connection_timeout=300
                    )
                )
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue='detections', durable=True)
                logger.info("RabbitMQ connection established")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    def send_detection_data(self, frame_data):
        """Send detection data to message broker"""
        try:
            self.ensure_connection()
            message = json.dumps(frame_data)
            self.channel.basic_publish(
                exchange='',
                routing_key='detections',
                body=message,
                properties=pika.BasicProperties(delivery_mode=2)
            )
        except Exception as e:
            logger.error(f"Failed to send detection data: {e}")
            # Try to reconnect once
            try:
                self.close()
                self.ensure_connection()
                self.channel.basic_publish(
                    exchange='',
                    routing_key='detections',
                    body=message,
                    properties=pika.BasicProperties(delivery_mode=2)
                )
            except Exception as retry_error:
                logger.error(f"Retry failed: {retry_error}")
                raise

    async def process_video(self, video_path):
        """Process video and detect violations"""
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"Failed to open video file: {video_path}")

            frame_number = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_number += 1
                results = self.model(frame)[0]
                
                # Process detections
                violations = self.track_hands_and_check_violations(frame, results, frame_number)
                if violations:
                    self.save_violation_frame(frame, violations, frame_number)

            logger.info(f"Processed {frame_number} frames with {self.violation_count} violations")
            return self.violation_count

        except Exception as e:
            logger.error(f"Error in process_video: {e}")
            raise
        finally:
            if 'cap' in locals():
                cap.release()

    def track_hands_and_check_violations(self, frame, results, frame_number):
        current_hands = []
        current_scoopers = []
        violations = []

        # Get current detections
        for *box, conf, cls in results.boxes.data.cpu().numpy():
            x1, y1, x2, y2 = map(int, box)
            label = self.model.names[int(cls)]
            cx, cy = (x1 + x2)//2, (y1 + y2)//2
            
            detection = {
                'bbox': [x1, y1, x2, y2],
                'center': (cx, cy),
                'confidence': float(conf)
            }

            if label == 'hand':
                current_hands.append(detection)
            elif label == 'scooper':
                current_scoopers.append(detection)

        # Update hand tracking and check for violations
        self.update_hand_tracking(current_hands, current_scoopers, frame_number, violations)

        if violations:
            return {
                'hands': violations,
                'scoopers': current_scoopers,
                'violation_type': 'left_roi_without_scooper'
            }
        return None

    def update_hand_tracking(self, current_hands, current_scoopers, frame_number, violations):
        # Update existing hands and check for leaving ROI
        hands_to_remove = []
        for hand_id, hand_info in self.hands_in_roi.items():
            hand_found = False
            last_pos = hand_info['last_pos']

            # Try to match with current hands
            for hand in current_hands:
                cx, cy = hand['center']
                dist = np.hypot(cx - last_pos[0], cy - last_pos[1])
                
                if dist < 50:  # Maximum distance for same hand
                    hand_found = True
                    hand_info['last_pos'] = (cx, cy)
                    
                    # Check if hand left ROI
                    in_roi = cv2.pointPolygonTest(self.ingredient_roi, (cx, cy), False) >= 0
                    if not in_roi and not hand_info.get('left_checked', False):
                        # Check if there's a scooper nearby when leaving
                        has_scooper = any(
                            np.hypot(s['center'][0] - cx, s['center'][1] - cy) < 100 
                            for s in current_scoopers
                        )
                        
                        if not has_scooper and frame_number - self.last_violation_time >= self.violation_cooldown:
                            self.violation_count += 1
                            self.last_violation_time = frame_number
                            violations.append(hand)
                        
                        hand_info['left_checked'] = True
                    break

            if not hand_found:
                hands_to_remove.append(hand_id)

        # Remove hands that are no longer tracked
        for hand_id in hands_to_remove:
            del self.hands_in_roi[hand_id]

        # Add new hands that entered ROI
        for hand in current_hands:
            cx, cy = hand['center']
            if cv2.pointPolygonTest(self.ingredient_roi, (cx, cy), False) >= 0:
                # Check if this is a new hand
                if not any(
                    np.hypot(cx - info['last_pos'][0], cy - info['last_pos'][1]) < 50 
                    for info in self.hands_in_roi.values()
                ):
                    # Record if hand entered with scooper
                    has_scooper = any(
                        np.hypot(s['center'][0] - cx, s['center'][1] - cy) < 100 
                        for s in current_scoopers
                    )
                    self.hands_in_roi[self.next_hand_id] = {
                        'entered_with_scooper': has_scooper,
                        'last_pos': (cx, cy),
                        'left_checked': False
                    }
                    self.next_hand_id += 1

    def save_violation_frame(self, frame, violations, frame_number):
        frame_copy = frame.copy()
        
        # Draw ROI
        cv2.polylines(frame_copy, [self.ingredient_roi], True, (0, 255, 255), 2)
        
        # Draw hands (red for violations)
        for hand in violations['hands']:
            x1, y1, x2, y2 = hand['bbox']
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame_copy, 'VIOLATION: Left ROI without Scooper', 
                       (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, (0, 0, 255), 2)

        # Draw scoopers (green)
        for scooper in violations['scoopers']:
            x1, y1, x2, y2 = scooper['bbox']
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Save frame with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        frame_path = self.frames_dir / f"violation_{self.violation_count}_{frame_number}_{timestamp}.jpg"
        cv2.imwrite(str(frame_path), frame_copy)
        return str(frame_path)

    async def emit_violation_event(self, frame_path, frame_number):
        """Emit violation event for real-time display"""
        event_data = {
            'violation_count': self.violation_count,
            'frame_path': frame_path,
            'frame_number': frame_number,
            'timestamp': datetime.now().isoformat()
        }
        # Send event to FastAPI endpoint
        async with aiohttp.ClientSession() as session:
            await session.post(
                'http://localhost:8000/violation_event',
                json=event_data
            )