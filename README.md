# Pizza Violation Detection System

## Overview
A real-time monitoring system that detects food safety violations in pizza preparation, specifically tracking whether workers are using proper utensils (scoopers) when handling ingredients.

## Features
- Real-time detection of hand movements in ingredient areas
- Violation detection when ingredients are handled without proper utensils
- Live visualization of violations with annotated frames
- WebSocket-based real-time updates
- Frame-by-frame analysis with YOLO object detection
- Region of Interest (ROI) monitoring for ingredient stations

## Prerequisites
- Python 3.8+
- CUDA-compatible GPU (recommended for real-time processing)
- Windows 10/11

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pizza-violation-detection.git
cd pizza-violation-detection
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
.\venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Project Structure
```
pizza-violation-detection/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── video_processor.py
│   └── detection_service.py
├── static/
│   ├── style.css
│   └── script.js
├── templates/
│   └── index.html
├── uploaded_videos/
├── violation_frames/
├── README.md
└── requirements.txt
```

## Usage

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

## Configuration

The system can be configured by modifying the following parameters in `video_processor.py`:
- ROI coordinates for ingredient stations
- Violation cooldown period
- Hand-scooper proximity threshold
- Detection confidence thresholds

## Contributing
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

