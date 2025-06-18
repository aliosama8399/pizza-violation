from fastapi import FastAPI, Request, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.rabbit_mq_service import RabbitMQService
import shutil
import os
import logging
from pathlib import Path
import json

# Define and create necessary directories
PROCESSED_VIDEOS_DIR = Path("processed_videos")
UPLOADED_VIDEOS_DIR = Path("uploaded_videos")
VIOLATION_FRAMES_DIR = Path("violation_frames")

PROCESSED_VIDEOS_DIR.mkdir(exist_ok=True)
UPLOADED_VIDEOS_DIR.mkdir(exist_ok=True)
VIOLATION_FRAMES_DIR.mkdir(exist_ok=True)


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Setup static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/processed_videos", StaticFiles(directory=PROCESSED_VIDEOS_DIR), name="processed_videos")
templates = Jinja2Templates(directory="templates")

# Initialize RabbitMQ service
rabbitmq_service = RabbitMQService()
VIDEO_QUEUE = 'video_queue'
VIOLATION_QUEUE = 'violation_queue'

@app.on_event("startup")
def startup_event():
    rabbitmq_service.connect()
    rabbitmq_service.declare_queue(VIDEO_QUEUE)
    rabbitmq_service.declare_queue(VIOLATION_QUEUE)

@app.on_event("shutdown")
def shutdown_event():
    rabbitmq_service.close()

# Store active websocket connections
active_connections = []

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    frames = []
    if VIOLATION_FRAMES_DIR.exists():
        frames = sorted(
            [f.name for f in VIOLATION_FRAMES_DIR.glob("*.jpg")],
            key=lambda x: os.path.getctime(VIOLATION_FRAMES_DIR / x),
            reverse=True
        )
    return templates.TemplateResponse("index.html", {"request": request, "initial_frames": frames})

@app.get("/violations/count")
async def get_violation_count():
    frames = []
    if VIOLATION_FRAMES_DIR.exists():
        frames = sorted(
            [f.name for f in VIOLATION_FRAMES_DIR.glob("*.jpg")],
            key=lambda x: os.path.getctime(VIOLATION_FRAMES_DIR / x),
            reverse=True
        )
    
    return {
        "violation_count": len(frames),
        "frames": frames
    }

@app.post("/process_video_upload")
async def process_video_upload(file: UploadFile = File(...)):
    try:
        if not file.filename:
            return JSONResponse(
                {"error": "Missing filename."},
                status_code=400
            )

        if not file.filename.lower().endswith(('.mp4', '.avi', '.mov')):
            return JSONResponse(
                {"error": "Invalid file type. Please upload a video file."},
                status_code=400
            )

        file_path = UPLOADED_VIDEOS_DIR / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Publish video path to RabbitMQ
        rabbitmq_service.publish_message(VIDEO_QUEUE, str(file_path))
        
        return JSONResponse({
            "message": "Video uploaded and is being processed.",
            "file_name": file.filename
        })

    except Exception as e:
        logger.error(f"Error processing video upload: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )

@app.get("/violation_frames/{frame_name}")
async def get_violation_frame(frame_name: str):
    frame_path = VIOLATION_FRAMES_DIR / frame_name
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="Frame not found")
    return FileResponse(frame_path)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        active_connections.remove(websocket)

@app.post("/violation_event")
async def violation_event(event_data: dict):
    # Broadcast violation event to all connected clients
    for connection in active_connections:
        try:
            await connection.send_json(event_data)
        except:
            active_connections.remove(connection)
    return JSONResponse({"status": "event broadcasted"})