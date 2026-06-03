import os
import subprocess
import logging
from typing import Dict, Any
import yt_dlp
logger = logging.getLogger(__name__)

def extract_audio_from_video(video_path: str, output_audio_path: str) -> str:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f'Video file not found: {video_path}')
    cmd = ['ffmpeg', '-y', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', output_audio_path]
    logger.info(f'Extracting audio using command: {' '.join(cmd)}')
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        logger.info('Audio extraction completed successfully.')
        return output_audio_path
    except subprocess.CalledProcessError as e:
        logger.error(f'FFmpeg error: {e.stderr}')
        raise RuntimeError(f'FFmpeg audio extraction failed: {e.stderr}')

def download_audio_from_url(url: str, output_directory: str, task_id: str) -> str:
    if not os.path.exists(output_directory):
        os.makedirs(output_directory, exist_ok=True)
    output_template = os.path.join(output_directory, f'{task_id}_temp.%(ext)s')
    final_output_path = os.path.join(output_directory, f'{task_id}.wav')
    cookies_path = None
    for p in ['cookies.txt', 'backend/cookies.txt', 'data/cookies.txt']:
        if os.path.exists(p):
            cookies_path = p
            break
    ydl_opts: Dict[str, Any] = {'format': 'bestaudio/best', 'outtmpl': output_template, 'nocheckcertificate': True, 'referer': 'https://www.youtube.com/', 'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-us,en;q=0.5', 'Sec-Fetch-Mode': 'navigate'}, 'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web_embedded', 'default']}}, 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}], 'postprocessor_args': ['-ar', '16000', '-ac', '1'], 'prefer_ffmpeg': True, 'quiet': True, 'no_warnings': True}
    if cookies_path:
        ydl_opts['cookiefile'] = cookies_path
    logger.info(f'Downloading audio from URL: {url}')
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'URL Video')
            logger.info(f"Successfully downloaded audio for title: '{title}'")
            temp_expected_path = os.path.join(output_directory, f'{task_id}_temp.wav')
            if os.path.exists(temp_expected_path):
                os.rename(temp_expected_path, final_output_path)
                return final_output_path
            elif os.path.exists(final_output_path):
                return final_output_path
            else:
                files = os.listdir(output_directory)
                for f in files:
                    if f.startswith(task_id) and f.endswith('.wav'):
                        return os.path.join(output_directory, f)
                raise FileNotFoundError('Could not locate download output file from yt-dlp.')
    except Exception as e:
        logger.error(f'yt-dlp download failed: {str(e)}')
        raise RuntimeError(f'Failed to download audio from URL: {str(e)}')