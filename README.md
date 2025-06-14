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

1. Start the FastAPI server:
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

2. Open your browser and navigate to:
```
http://localhost:8000
```

3. Upload a video file for processing
4. Monitor real-time violations in the web interface

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

