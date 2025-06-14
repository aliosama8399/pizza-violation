# ==================== SETUP INSTRUCTIONS ====================
"""
SETUP INSTRUCTIONS:

1. Install RabbitMQ:
   sudo apt-get install rabbitmq-server

2. Install Python dependencies:
   pip install pika ultralytics opencv-python numpy fastapi uvicorn websockets

3. Run the system:
   
   # Terminal 1: Start Detection Service
   python script.py detection
   
   # Terminal 2: Start Streaming Service  
   python script.py streaming
   
   # Terminal 3: Process Video
   python script.py video "path/to/video.mp4"
   
   # Or run everything together:
   python script.py all "path/to/video.mp4"

4. Database and frames will be saved in:
   - violations.db (SQLite database)
   - violation_frames/ (directory for violation frames)

MESSAGE FLOW:
Video Processor → [detections queue] → Detection Service → [streaming_results queue] → Streaming Service
                                    ↓
                                Database + Frame Storage
"""

## How to Use the Website

### Starting the Application
1. Start the FastAPI server:
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

2. Open your web browser and navigate to:
```
http://localhost:8000
```

### Using the Interface

#### Video Upload
1. Click the "Choose File" button in the upload section
2. Select a video file (supported formats: .mp4, .avi, .mov)
3. Click the "Process Video" button to start analysis

#### Monitoring Violations
The interface provides real-time monitoring with several components:

1. **Violation Counter**
   - Located at the top of the results section
   - Updates in real-time as violations are detected
   - Shows total number of violations detected

2. **Violation Frames Grid**
   - Displays frames where violations occurred
   - Most recent violations appear at the top
   - Each frame shows:
     - The violation number
     - Frame number from the video
     - Timestamp of the violation
     - Visual indicators:
       - Yellow polygon: Ingredient area (ROI)
       - Red boxes: Hands violating rules
       - Green boxes: Scoopers

3. **Progress Information**
   - Shows current processing status
   - Indicates which frame is being analyzed
   - Updates continuously during processing

### Understanding Violations

A violation is recorded when:
- A hand leaves the ingredient area (ROI) without a scooper
- The hand was previously detected inside the ROI
- No scooper is detected near the hand when leaving

### Visual Indicators

1. **ROI (Region of Interest)**
   - Yellow polygon marking the ingredient station area
   - This is the monitored zone for violations

2. **Hand Detection**
   - Red boxes around detected hands
   - Shows when a hand is leaving ROI without proper tool

3. **Scooper Detection**
   - Green boxes around detected scoopers
   - Used to verify proper tool usage

### Real-time Updates

- New violations appear immediately at the top of the grid
- Frames are highlighted briefly when first displayed
- Violation counter updates automatically
- Processing continues until video completion

### Error Handling

If you encounter any issues:
1. Check that your video file is in a supported format
2. Ensure the video file is not corrupted
3. Verify that the file size is reasonable (< 100MB recommended)
4. Check the browser console for any error messages

### Best Practices

1. **Video Requirements**
   - Good lighting conditions
   - Clear view of ingredient station
   - Stable camera position
   - Recommended resolution: 720p or higher

2. **Processing Time**
   - Depends on video length and resolution
   - GPU acceleration recommended for faster processing
   - Progress is shown in real-time

3. **Browser Compatibility**
   - Chrome (recommended)
   - Firefox
   - Edge
   - Safari
