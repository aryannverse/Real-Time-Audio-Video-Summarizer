import os
import uuid
import json
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import init_db, get_db
from .models import TaskModel, TaskResponse, TaskCreate, TaskURLCreate, TranscriptSegment
from .pipeline import start_pipeline, register_listener, unregister_listener
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)
UPLOAD_DIR = os.getenv('UPLOAD_DIR', './uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('Initializing SQLite database...')
    init_db()
    yield
    logger.info('Shutting down backend server...')
app = FastAPI(title='Real-Time Audio/Video Summarizer API', description='Backend API for transcribing and summarizing audio/video files and URLs.', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

def parse_db_task(task: TaskModel) -> TaskResponse:
    transcript_parsed = json.loads(task.transcript) if task.transcript else None
    key_points_parsed = json.loads(task.key_points) if task.key_points else None
    action_items_parsed = json.loads(task.action_items) if task.action_items else None
    discussion_topics_parsed = json.loads(task.discussion_topics) if task.discussion_topics else None
    return TaskResponse(task_id=task.task_id, file_name=task.file_name, status=task.status, created_at=task.created_at, updated_at=task.updated_at, transcript=transcript_parsed, summary=task.summary, key_points=key_points_parsed, action_items=action_items_parsed, discussion_topics=discussion_topics_parsed, logs=task.logs or '', error_message=task.error_message)

@app.post('/api/upload', response_model=TaskResponse)
async def upload_file(file: UploadFile=File(...), db: Session=Depends(get_db)):
    task_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    temp_filename = f'{task_id}_source{ext}'
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)
    logger.info(f'Receiving file upload: {file.filename} -> saving to {temp_path}')
    try:
        with open(temp_path, 'wb') as buffer:
            while (content := (await file.read(1024 * 1024))):
                buffer.write(content)
    except Exception as e:
        logger.error(f'Failed to save uploaded file: {str(e)}')
        raise HTTPException(status_code=500, detail=f'File save failed: {str(e)}')
    db_task = TaskModel(task_id=task_id, file_name=file.filename, status='pending', logs=f'[SYSTEM] Uploaded file saved to disk.\n')
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    asyncio.create_task(start_pipeline(task_id, temp_path, is_url=False))
    return parse_db_task(db_task)

@app.post('/api/url', response_model=TaskResponse)
async def process_url(payload: TaskURLCreate, db: Session=Depends(get_db)):
    url = payload.url
    if not url:
        raise HTTPException(status_code=400, detail='URL cannot be empty')
    task_id = str(uuid.uuid4())
    logger.info(f'Processing URL target: {url} (task: {task_id})')
    db_task = TaskModel(task_id=task_id, file_name=url, status='pending', logs=f'[SYSTEM] Registered URL processing pipeline.\n')
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    asyncio.create_task(start_pipeline(task_id, url, is_url=True))
    return parse_db_task(db_task)

@app.get('/api/history', response_model=List[TaskResponse])
async def get_history(db: Session=Depends(get_db)):
    tasks = db.query(TaskModel).order_by(TaskModel.created_at.desc()).all()
    return [parse_db_task(t) for t in tasks]

@app.get('/api/history/{task_id}', response_model=TaskResponse)
async def get_task(task_id: str, db: Session=Depends(get_db)):
    task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    return parse_db_task(task)

@app.delete('/api/history/{task_id}')
async def delete_task(task_id: str, db: Session=Depends(get_db)):
    task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    db.delete(task)
    db.commit()
    cache_wav = os.path.join(UPLOAD_DIR, f'{task_id}.wav')
    if os.path.exists(cache_wav):
        try:
            os.remove(cache_wav)
        except Exception as e:
            logger.warning(f'Could not delete cache file {cache_wav}: {str(e)}')
    return {'message': 'Task deleted successfully'}

@app.websocket('/ws/task/{task_id}')
async def task_websocket(websocket: WebSocket, task_id: str):
    await websocket.accept()
    logger.info(f'WebSocket client connected for task: {task_id}')
    db = next(get_db())
    task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
    if not task:
        logger.warning(f'WebSocket reject: Task {task_id} not found.')
        await websocket.send_json({'type': 'error', 'message': 'Task not found.'})
        await websocket.close(code=1008)
        return
    transcript_list = json.loads(task.transcript) if task.transcript else []
    key_points_list = json.loads(task.key_points) if task.key_points else []
    action_items_list = json.loads(task.action_items) if task.action_items else []
    discussion_topics_list = json.loads(task.discussion_topics) if task.discussion_topics else []
    await websocket.send_json({'type': 'catchup', 'status': task.status, 'logs': task.logs or '', 'transcript': transcript_list, 'summary': task.summary, 'key_points': key_points_list, 'action_items': action_items_list, 'discussion_topics': discussion_topics_list})
    if task.status in ['completed', 'failed']:
        logger.info(f"WebSocket terminal close: Task {task_id} is already in state '{task.status}'.")
        await websocket.close()
        return

    async def send_event(event: dict):
        try:
            await websocket.send_json(event)
        except Exception as e:
            logger.warning(f'Failed to send WS message on task {task_id}: {str(e)}')
    register_listener(task_id, send_event)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f'WebSocket client disconnected for task: {task_id}')
    finally:
        unregister_listener(task_id, send_event)