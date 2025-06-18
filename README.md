# Pizza Violation Detection System

## 1. Overview

This project is a real-time video processing application designed to detect "pizza violations." It allows a user to upload a video, which is then processed in the background to identify specific actions, such as a hand entering a designated area without a tool.

The system is built with a decoupled, event-driven architecture using **RabbitMQ** as a message broker. This allows for scalable and resilient background processing of video frames. The frontend is powered by **FastAPI** serving a simple HTML page with vanilla JavaScript, using **WebSockets** to display results in real-time without needing to refresh the page.

### Core Technologies
- **Backend:** Python, FastAPI
- **Frontend:** HTML, CSS, JavaScript
- **Video Processing:** OpenCV
- **Object Detection:** YOLOv12
- **Messaging:** RabbitMQ
- **Web Server:** Uvicorn

## 2. System Architecture

The application is composed of a central web server and several independent worker services that communicate through a message queue.


1.  **Video Upload**: The user selects a video file from the browser interface.
2.  **Web Server (main.py)**: The FastAPI server receives the video, saves it to the `uploaded_videos` directory, and sends a message to the `video_queue` in RabbitMQ containing the video's path.
3.  **Video Splitter Worker**: This worker consumes the message, splits the video into individual frames, and publishes each frame as a new message to the `frame_queue`. It also sends a final message to the `assembly_queue` indicating the total number of frames.
4.  **Detection Service Worker**: This worker consumes frames from the `frame_queue`. It runs the YOLO model to detect objects (hands, tools). If it detects a violation, it saves the frame to the `violation_frames` directory and sends a message with violation details to the `results_queue`. Each processed frame is saved to the `processed_frames` directory.
5.  **Video Assembler Worker**: After all frames for a video have been processed, this worker consumes the job message from the `assembly_queue`. It reassembles the processed frames into a new MP4 video and saves it to the `processed_videos` directory. It then sends a message to the `results_queue` with the URL of the final video.
6.  **Results Worker**: This worker listens to the `results_queue` for both violation and final video messages. It forwards these results to a dedicated endpoint on the FastAPI server.
7.  **WebSocket Broadcast**: The FastAPI server receives the results from the worker and instantly broadcasts them to all connected clients via a WebSocket connection.
8.  **Real-time Updates**: The frontend JavaScript captures the WebSocket messages and dynamically updates the page to display violation images and a link to the final processed video.


## 3. Project Structure
```
/my-pizza-app
|-- .gitignore
|-- README.md
|-- requirements.txt
|-- yolo12m-v2.pt               # YOLO model file
|-- src/                        # Source code
|   |-- main.py                 # FastAPI Web Server, WebSocket endpoint
|   |-- video_splitter_worker.py  # Worker to split video into frames
|   |-- detection_service.py    # Worker for violation detection
|   |-- video_assembler_worker.py # Worker to create the final video
|   |-- results_worker.py       # Worker to push results to frontend
|-- static/                     # Frontend assets
|   |-- script.js               # Client-side logic for WebSocket, UI updates
|   |-- style.css               # Styles for the webpage
|-- templates/
|   |-- index.html              # Main HTML page
|-- uploaded_videos/            # Storage for original uploaded videos
|-- processed_frames/           # Storage for processed frames with detections
|-- violation_frames/           # Storage for frames where violations occurred
|-- processed_videos/           # Storage for final re-assembled videos
```

## 4. Setup and Installation

### Prerequisites
- Python 3.10+
- [RabbitMQ](https://www.rabbitmq.com/download.html) (Ensure the service is running before starting the application)
- [Git](https://git-scm.com/downloads)

### Installation Steps
1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd my-pizza-app
    ```

2.  **Download the Model:**
    Ensure the YOLO model file `yolo12m-v2.pt` is present in the root directory of the project.

3.  **Set up a Python virtual environment:**
    ```bash
    # For Windows
    python -m venv venv
    venv\\Scripts\\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## 5. How to Run the System

To run the application, you must start the RabbitMQ service, all four worker scripts, and the FastAPI web server. **Each worker must be run in a separate terminal.**

1.  **Start RabbitMQ:**
    Make sure your RabbitMQ server is running. Refer to the RabbitMQ documentation for instructions.

2.  **Start the Workers:**
    Open four separate terminals, activate the virtual environment in each one, and run the following commands:

    *   **Terminal 1: Video Splitter**
        ```bash
        python src/video_splitter_worker.py
        ```
    *   **Terminal 2: Detection Service**
        ```bash
        python src/detection_service.py
        ```
    *   **Terminal 3: Video Assembler**
        ```bash
        python src/video_assembler_worker.py
        ```
    *   **Terminal 4: Results Worker**
        ```bash
        python src/results_worker.py
        ```

3.  **Start the Web Server:**
    Open a fifth terminal, activate the virtual environment, and run the Uvicorn server:
    ```bash
    uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
    ```

4.  **Access the Application:**
    Open your web browser and navigate to:
    [http://localhost:8000](http://localhost:8000)
5. **Access the Rabbitmq service:**
    Open your web browser and navigate to:
    http://localhost:15672/

## 6. Usage
- Click the "Choose File" button to select a video file (.mp4).
- Click "Upload".
- The system will begin processing the video. As violations are detected, they will appear in the "Violations Log" in real-time.
- Once processing is complete, a link to the final video with detection overlays will appear in the "Processed Video" section.
