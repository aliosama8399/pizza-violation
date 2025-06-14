from fastapi import WebSocket
import json
import logging
import pika
import sqlite3
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DetectionService:
    """
    Service that receives detection data, applies business logic, and stores violations
    """
    def __init__(self, db_path="violations.db", frames_dir="violation_frames"):
        self.db_path = db_path
        self.frames_dir = Path(frames_dir)
        self.frames_dir.mkdir(exist_ok=True)
        
        # Setup database
        self.setup_database()
        
        # Setup RabbitMQ consumer
        self.setup_rabbitmq()
        
        # Violation tracking
        self.violation_count = 0
        
    def setup_database(self):
        """Initialize SQLite database for violations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                violation_id TEXT UNIQUE,
                timestamp TEXT,
                frame_number INTEGER,
                frame_path TEXT,
                hand_bbox TEXT,
                hand_position TEXT,
                violation_type TEXT,
                confidence REAL,
                roi_coordinates TEXT,
                metadata TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")
    
    def setup_rabbitmq(self):
        """Setup RabbitMQ consumer for receiving detection data"""
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost')
            )
            self.channel = self.connection.channel()
            
            # Declare queues
            self.channel.queue_declare(queue='detections', durable=True)
            logger.info("RabbitMQ consumer connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def check_violation_logic(self, detections):
        """
        Apply business logic to check for violations
        Logic: Hand took ingredient without scooper
        """
        hands = [d for d in detections if d['label'] == 'hand' and d['inside_roi']]
        scoopers = [d for d in detections if d['label'] == 'scooper']
        
        violations = []
        
        for hand in hands:
            hx, hy = hand['center']
            
            # Check if any scooper is nearby (within 80 pixels)
            has_scooper = False
            for scooper in scoopers:
                sx, sy = scooper['center']
                if np.hypot(sx - hx, sy - hy) < 80:
                    has_scooper = True
                    break
            
            if not has_scooper:
                violations.append({
                    'hand_detection': hand,
                    'violation_type': 'bare_hand_contact',
                    'severity': 'HIGH'
                })
        
        return violations
    
    def process_detection_data(self, ch, method, properties, body):
        """Process incoming detection data and check for violations"""
        try:
            frame_data = json.loads(body)
            
            # Apply violation detection logic
            violations = self.check_violation_logic(frame_data['detections'])
            self.violation_count += len(violations)
            
            # Prepare result data for streaming service
            result_data = {
                'timestamp': frame_data['timestamp'],
                'frame_number': frame_data['frame_number'],
                'detections': frame_data['detections'],
                'violations': len(violations),
                'violation_count': self.violation_count
            }
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
            logger.info(f"Processed frame {frame_data['frame_number']} with {len(violations)} violations")
            
        except Exception as e:
            logger.error(f"Error processing detection data: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def start_consuming(self):
        """Start consuming detection data from message broker"""
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(
            queue='detections',
            on_message_callback=self.process_detection_data
        )
        
        logger.info("Detection Service started. Waiting for detection data...")
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping Detection Service...")
            self.channel.stop_consuming()
            self.connection.close()