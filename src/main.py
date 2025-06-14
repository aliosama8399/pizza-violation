from fastapi import FastAPI, Request, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from src.detection_service import DetectionService
from src.video_processor import VideoProcessor
import shutil
import os
import asyncio
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Setup static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize services
detection_service = DetectionService()
video_processor = VideoProcessor()

# Store active websocket connections
active_connections = []

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/violations/count")
async def get_violation_count():
    frames_dir = Path("violation_frames")
    frames = []
    if frames_dir.exists():
        frames = sorted(
            [f.name for f in frames_dir.glob("*.jpg")],
            key=lambda x: os.path.getctime(frames_dir / x),
            reverse=True
        )
    
    return {
        "violation_count": video_processor.violation_count,
        "frames": frames
    }

@app.post("/process_video_upload")
async def process_video_upload(file: UploadFile = File(...)):
    try:
        if not file.filename.lower().endswith(('.mp4', '.avi', '.mov')):
            return JSONResponse(
                {"error": "Invalid file type. Please upload a video file."},
                status_code=400
            )

        upload_dir = Path("uploaded_videos")
        upload_dir.mkdir(exist_ok=True)
        file_path = upload_dir / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        violation_count = await video_processor.process_video(file_path)
        
        return JSONResponse({
            "message": "Video processing completed",
            "violation_count": violation_count,
            "file_name": file.filename
        })

    except Exception as e:
        logger.error(f"Error processing video upload: {e}")
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )

async def run_video_processing(video_path: str):
    try:
        await video_processor.process_video(video_path)
        logger.info(f"Finished processing video: {video_path}")
    except Exception as e:
        logger.error(f"Error in video processing task: {e}")
        raise

@app.get("/violation_frames/{frame_name}")
async def get_violation_frame(frame_name: str):
    frame_path = Path("violation_frames") / frame_name
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