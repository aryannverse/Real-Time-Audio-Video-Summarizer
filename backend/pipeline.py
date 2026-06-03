import os
import json
import logging
import asyncio
import queue
import threading
from typing import Dict, List, Callable, Awaitable, Any, Optional
from sqlalchemy.orm import Session
from .models import TaskModel, StructuredSummary, TranscriptSegment
from .database import SessionLocal
from .utils import extract_audio_from_video, download_audio_from_url
logger = logging.getLogger(__name__)
_task_listeners: Dict[str, List[Callable[[dict], Awaitable[None]]]] = {}

def register_listener(task_id: str, callback: Callable[[dict], Awaitable[None]]):
    if task_id not in _task_listeners:
        _task_listeners[task_id] = []
    _task_listeners[task_id].append(callback)

def unregister_listener(task_id: str, callback: Callable[[dict], Awaitable[None]]):
    if task_id in _task_listeners:
        if callback in _task_listeners[task_id]:
            _task_listeners[task_id].remove(callback)
        if not _task_listeners[task_id]:
            del _task_listeners[task_id]

async def broadcast_event(task_id: str, event: dict):
    if task_id in _task_listeners:
        listeners = list(_task_listeners[task_id])
        await asyncio.gather(*(cb(event) for cb in listeners), return_exceptions=True)

def append_task_log(db: Session, task_id: str, log_message: str):
    task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
    if task:
        task.logs = (task.logs or '') + log_message + '\n'
        db.commit()

async def update_task_state(db: Session, task_id: str, status: str, log_message: Optional[str]=None):
    task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
    if task:
        task.status = status
        if log_message:
            task.logs = (task.logs or '') + f'[{status.upper()}] {log_message}\n'
        db.commit()
        event = {'type': 'status_update', 'status': status, 'log': f'[{status.upper()}] {log_message}' if log_message else ''}
        await broadcast_event(task_id, event)

def _transcribe_worker(audio_path: str, model_name: str, q: queue.Queue):
    try:
        from faster_whisper import WhisperModel
        logger.info(f'Loading Whisper model: {model_name}')
        q.put({'type': 'log', 'message': 'Loading local Whisper model...'})
        model = WhisperModel(model_name, device='cpu', compute_type='int8')
        q.put({'type': 'log', 'message': 'Whisper model loaded. Starting transcription...'})
        segments, info = model.transcribe(audio_path, beam_size=5)
        logger.info(f'Audio details - Language: {info.language} (Confidence: {info.language_probability:.2f})')
        q.put({'type': 'log', 'message': f'Detected language: {info.language} ({info.language_probability * 100:.1f}%)'})
        for segment in segments:
            q.put({'type': 'segment', 'start': segment.start, 'end': segment.end, 'text': segment.text.strip()})
        q.put({'type': 'done'})
    except Exception as e:
        logger.error(f'Whisper transcription failed: {str(e)}')
        q.put({'type': 'error', 'message': f'Whisper failed: {str(e)}'})

def _run_llm_summarizer(text_content: str) -> StructuredSummary:
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.warning('GEMINI_API_KEY not found. Using fallback mock summarizer.')
        raise ValueError('Missing GEMINI_API_KEY. Please provide a key in your settings or .env file.')
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f'\n    You are an expert executive assistant and summarization model.\n    Analyze the following transcript of an audio/video recording.\n    Produce a structured summary containing:\n    1. A high-level overview summary (2-4 sentences).\n    2. A list of key takeaways or discussion points.\n    3. A list of concrete action items, checklist points, or follow-ups.\n    4. A list of core topics or categories covered in the discussion.\n\n    Be concise, objective, and capture details (including metrics, decisions, and deadlines if mentioned).\n\n    Transcript:\n    {text_content}\n    '
    try:
        response = model.generate_content(prompt, generation_config=genai.GenerationConfig(response_mime_type='application/json', response_schema=StructuredSummary))
        data = json.loads(response.text)
        return StructuredSummary(**data)
    except Exception as e:
        logger.error(f'Gemini API call failed: {str(e)}')
        raise RuntimeError(f'Gemini API request failed: {str(e)}')

async def start_pipeline(task_id: str, source_path: str, is_url: bool=False, file_name: Optional[str]=None):
    db = SessionLocal()
    try:
        await update_task_state(db, task_id, 'processing_audio', 'Processing input file/URL...')
        upload_dir = os.getenv('UPLOAD_DIR', './uploads')
        os.makedirs(upload_dir, exist_ok=True)
        audio_path = os.path.join(upload_dir, f'{task_id}.wav')
        if is_url:
            await update_task_state(db, task_id, 'processing_audio', f'Downloading URL: {source_path}...')
            try:
                loop = asyncio.get_running_loop()
                audio_path = await loop.run_in_executor(None, download_audio_from_url, source_path, upload_dir, task_id)
                await update_task_state(db, task_id, 'processing_audio', 'Audio downloaded successfully.')
            except Exception as e:
                raise RuntimeError(f'Audio download failed: {str(e)}')
        else:
            ext = os.path.splitext(source_path)[1].lower()
            if ext in ['.mp4', '.mkv', '.mov', '.avi', '.webm']:
                await update_task_state(db, task_id, 'processing_audio', 'Extracting audio from video file...')
                try:
                    loop = asyncio.get_running_loop()
                    audio_path = await loop.run_in_executor(None, extract_audio_from_video, source_path, audio_path)
                    await update_task_state(db, task_id, 'processing_audio', 'Audio extracted successfully.')
                except Exception as e:
                    raise RuntimeError(f'Audio extraction failed: {str(e)}')
            else:
                await update_task_state(db, task_id, 'processing_audio', 'Normalizing audio format...')
                try:
                    loop = asyncio.get_running_loop()
                    audio_path = await loop.run_in_executor(None, extract_audio_from_video, source_path, audio_path)
                    await update_task_state(db, task_id, 'processing_audio', 'Audio normalized successfully.')
                except Exception as e:
                    logger.warning(f'Audio normalization failed, using original file: {str(e)}')
                    audio_path = source_path
        await update_task_state(db, task_id, 'transcribing', 'Speech-to-Text transcription starting...')
        whisper_model_name = os.getenv('WHISPER_MODEL', 'base')
        q = queue.Queue()
        thread = threading.Thread(target=_transcribe_worker, args=(audio_path, whisper_model_name, q), daemon=True)
        thread.start()
        transcript_segments = []
        full_text_chunks = []
        while True:
            try:
                event = q.get_nowait()
                if event['type'] == 'done':
                    break
                elif event['type'] == 'error':
                    raise RuntimeError(event['message'])
                elif event['type'] == 'log':
                    append_task_log(db, task_id, f'[WHISPER] {event['message']}')
                    await broadcast_event(task_id, {'type': 'log', 'message': event['message']})
                elif event['type'] == 'segment':
                    segment_data = {'start': event['start'], 'end': event['end'], 'text': event['text']}
                    transcript_segments.append(segment_data)
                    full_text_chunks.append(event['text'])
                    await broadcast_event(task_id, {'type': 'segment', 'segment': segment_data})
            except queue.Empty:
                await asyncio.sleep(0.1)
        task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
        if task:
            task.transcript = json.dumps(transcript_segments)
            db.commit()
        full_text = ' '.join(full_text_chunks).strip()
        await update_task_state(db, task_id, 'transcribing', f'Transcription completed. Total characters: {len(full_text)}')
        if not full_text:
            raise RuntimeError('Transcription produced empty text. Cannot generate summary.')
        await update_task_state(db, task_id, 'summarizing', 'Chaining summaries and requesting Gemini...')
        try:
            loop = asyncio.get_running_loop()
            structured_summary = await loop.run_in_executor(None, _run_llm_summarizer, full_text)
            task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
            if task:
                task.summary = structured_summary.summary
                task.key_points = json.dumps(structured_summary.key_points)
                task.action_items = json.dumps(structured_summary.action_items)
                task.discussion_topics = json.dumps(structured_summary.discussion_topics)
                task.status = 'completed'
                task.logs = (task.logs or '') + '[COMPLETED] Summarization finished successfully.\n'
                db.commit()
            await broadcast_event(task_id, {'type': 'completed', 'summary': structured_summary.summary, 'key_points': structured_summary.key_points, 'action_items': structured_summary.action_items, 'discussion_topics': structured_summary.discussion_topics})
            logger.info(f'Task {task_id} completed successfully.')
        except Exception as e:
            logger.warning(f'Summarizer failed: {str(e)}. Generating fallback summary.')
            fallback_summary = f'Transcript length: {len(full_text)} characters. (Gemini API summary could not be generated: {str(e)})'
            task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
            if task:
                task.summary = fallback_summary
                task.key_points = json.dumps(['Could not generate AI summary due to error or missing API key.'])
                task.action_items = json.dumps(['Please configure GEMINI_API_KEY in your .env file.'])
                task.discussion_topics = json.dumps(['System Status / Configuration'])
                task.status = 'completed'
                task.logs = (task.logs or '') + f'[COMPLETED WITH WARNINGS] Gemini summarization failed, saved transcript. Error: {str(e)}\n'
                db.commit()
            await broadcast_event(task_id, {'type': 'completed', 'summary': fallback_summary, 'key_points': ['Could not generate AI summary due to error or missing API key.'], 'action_items': ['Please configure GEMINI_API_KEY in your .env file.'], 'discussion_topics': ['System Status / Configuration']})
    except Exception as e:
        logger.error(f'Pipeline error in task {task_id}: {str(e)}')
        await update_task_state(db, task_id, 'failed', f'Pipeline failed: {str(e)}')
        task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
        if task:
            task.error_message = str(e)
            db.commit()
    finally:
        db.close()
        try:
            if not is_url and os.path.exists(source_path) and ('uploads' in source_path):
                os.remove(source_path)
        except Exception as cleanup_err:
            logger.warning(f'Failed to delete source upload file {source_path}: {str(cleanup_err)}')