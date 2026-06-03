import os
import json
import asyncio
import datetime
import requests
import streamlit as st
import websockets
from dotenv import load_dotenv
import threading
import uvicorn
import time
load_dotenv()
BACKEND_URL = os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')
WS_URL = os.getenv('WS_URL', 'ws://127.0.0.1:8000')
def start_backend():
    try:
        requests.get(f'{BACKEND_URL}/api/history', timeout=0.2)
    except requests.exceptions.RequestException:
        try:
            import sys
            p_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            if p_root not in sys.path:
                sys.path.insert(0, p_root)
            from backend.main import app as fastapi_app
            host = '127.0.0.1'
            port = 8000
            if '://' in BACKEND_URL:
                netloc = BACKEND_URL.split('://')[1]
                if ':' in netloc:
                    h, p = netloc.split(':')
                    if h != 'backend':
                        host = h
                    try:
                        port = int(p)
                    except ValueError:
                        pass
            thread = threading.Thread(target=lambda: uvicorn.run(fastapi_app, host=host, port=port, log_level='warning'), daemon=True)
            thread.start()
            time.sleep(1.0)
        except Exception as e:
            import sys
            print(f'Backend start error: {str(e)}', file=sys.stderr)
start_backend()
st.set_page_config(page_title='AI Audio/Video Summarizer', page_icon='🎙️', layout='wide', initial_sidebar_state='expanded')
if 'pipeline_running' not in st.session_state:
    st.session_state.pipeline_running = False
if 'task_id' not in st.session_state:
    st.session_state.task_id = None
st.markdown("\n<style>\n    /* Main Layout */\n    .stApp {\n        background-color: #0b0c10;\n        color: #c5c6c7;\n        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;\n    }\n    \n    /* Header Card styling */\n    .header-container {\n        background: linear-gradient(135deg, rgba(138, 43, 226, 0.15) 0%, rgba(69, 162, 158, 0.05) 100%);\n        border: 1px solid rgba(138, 43, 226, 0.25);\n        border-radius: 12px;\n        padding: 24px;\n        margin-bottom: 24px;\n        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);\n    }\n    \n    .header-title {\n        font-size: 2.2rem;\n        font-weight: 800;\n        background: linear-gradient(90deg, #8A2BE2 0%, #45A29E 100%);\n        -webkit-background-clip: text;\n        -webkit-text-fill-color: transparent;\n        margin-bottom: 8px;\n    }\n    \n    /* Sleek Cards */\n    .glass-card {\n        background: rgba(22, 27, 34, 0.8);\n        border: 1px solid rgba(138, 43, 226, 0.15);\n        border-radius: 10px;\n        padding: 20px;\n        margin-bottom: 16px;\n        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);\n    }\n    \n    .glass-card-title {\n        color: #45A29E;\n        font-size: 1.15rem;\n        font-weight: 600;\n        margin-bottom: 12px;\n        border-bottom: 1px solid rgba(69, 162, 158, 0.15);\n        padding-bottom: 6px;\n    }\n    \n    /* Scrolling boxes for Live components */\n    .scroll-container {\n        height: 400px;\n        overflow-y: auto;\n        padding: 12px;\n        background-color: #0d1117;\n        border-radius: 6px;\n        border: 1px solid rgba(255, 255, 255, 0.05);\n        font-family: 'Courier New', Courier, monospace;\n        font-size: 0.9rem;\n        line-height: 1.5;\n    }\n    \n    .segment-timestamp {\n        color: #8A2BE2;\n        font-weight: bold;\n        margin-right: 8px;\n    }\n    \n    .segment-text {\n        color: #c5c6c7;\n    }\n    \n    /* Waveform Animation */\n    .waveform-container {\n        display: flex;\n        align-items: center;\n        justify-content: center;\n        gap: 6px;\n        height: 60px;\n        margin: 20px 0;\n        background: rgba(138, 43, 226, 0.05);\n        border-radius: 8px;\n        border: 1px dashed rgba(138, 43, 226, 0.3);\n    }\n    .bar {\n        width: 6px;\n        height: 12px;\n        background: linear-gradient(180deg, #8A2BE2 0%, #45A29E 100%);\n        border-radius: 3px;\n        animation: bounce 1.2s ease-in-out infinite;\n    }\n    .bar:nth-child(2) { animation-delay: 0.15s; height: 35px; }\n    .bar:nth-child(3) { animation-delay: 0.3s; height: 45px; }\n    .bar:nth-child(4) { animation-delay: 0.45s; height: 25px; }\n    .bar:nth-child(5) { animation-delay: 0.6s; height: 40px; }\n    .bar:nth-child(6) { animation-delay: 0.75s; height: 15px; }\n    .bar:nth-child(7) { animation-delay: 0.9s; height: 30px; }\n    @keyframes bounce {\n        0%, 100% { transform: scaleY(1); }\n        50% { transform: scaleY(2.2); }\n    }\n    \n    /* Pulsing AI thinking circle */\n    .ai-pulse-container {\n        text-align: center;\n        padding: 30px;\n    }\n    .ai-pulse {\n        width: 80px;\n        height: 80px;\n        background: radial-gradient(circle, rgba(138, 43, 226, 0.25) 0%, rgba(138, 43, 226, 0) 70%);\n        border-radius: 50%;\n        border: 3px solid #8A2BE2;\n        box-shadow: 0 0 20px rgba(138, 43, 226, 0.6);\n        animation: pulse 2.2s infinite ease-in-out;\n        margin: 0 auto 16px auto;\n    }\n    @keyframes pulse {\n        0% { transform: scale(0.9); opacity: 0.5; box-shadow: 0 0 10px rgba(138, 43, 226, 0.4); }\n        50% { transform: scale(1.1); opacity: 1; box-shadow: 0 0 30px rgba(138, 43, 226, 0.9); }\n        100% { transform: scale(0.9); opacity: 0.5; box-shadow: 0 0 10px rgba(138, 43, 226, 0.4); }\n    }\n    \n    /* Badge styling */\n    .status-badge {\n        display: inline-block;\n        padding: 4px 10px;\n        border-radius: 20px;\n        font-size: 0.8rem;\n        font-weight: bold;\n        text-transform: uppercase;\n        margin-left: 10px;\n    }\n    .badge-completed { background: rgba(46, 204, 113, 0.2); color: #2ecc71; border: 1px solid #2ecc71; }\n    .badge-processing { background: rgba(241, 196, 15, 0.2); color: #f1c40f; border: 1px solid #f1c40f; }\n    .badge-transcribing { background: rgba(52, 152, 219, 0.2); color: #3498db; border: 1px solid #3498db; }\n    .badge-summarizing { background: rgba(155, 89, 182, 0.2); color: #9b59b6; border: 1px solid #9b59b6; }\n    .badge-failed { background: rgba(231, 76, 60, 0.2); color: #e74c3c; border: 1px solid #e74c3c; }\n    \n    /* Action items checklist override */\n    .stCheckbox {\n        margin-bottom: 6px;\n    }\n</style>\n", unsafe_allow_html=True)

def format_time(seconds: float) -> str:
    td = datetime.timedelta(seconds=int(seconds))
    return str(td)

def fetch_history():
    try:
        response = requests.get(f'{BACKEND_URL}/api/history')
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.sidebar.error(f'Cannot connect to backend: {str(e)}')
    return []

def delete_task(task_id: str):
    try:
        requests.delete(f'{BACKEND_URL}/api/history/{task_id}')
        return True
    except Exception as e:
        st.error(f'Failed to delete task: {str(e)}')
    return False
st.sidebar.markdown("<br><h2 style='color:#45A29E;margin-bottom:8px;'>📂 RECORDINGS HISTORY</h2>", unsafe_allow_html=True)
history = fetch_history()
selected_history_task = None
if history:
    history_options = {}
    for task in history:
        created_time = datetime.datetime.fromisoformat(task['created_at'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
        name = task['file_name']
        if len(name) > 30:
            name = name[:27] + '...'
        label = f'{created_time} - {name}'
        history_options[label] = task
    selected_label = st.sidebar.selectbox('Select past summary', options=['-- Select Past Summary --'] + list(history_options.keys()))
    if selected_label != '-- Select Past Summary --':
        selected_history_task = history_options[selected_label]
else:
    st.sidebar.info('No past summarizations found.')
st.markdown('\n<div class="header-container">\n    <div class="header-title">Real-Time Video/Audio Summarization Engine</div>\n    <div style="color: #8b949e; font-size: 1.05rem;">\n        Extract audio, generate real-time transcripts locally via Whisper, and auto-generate structured executive summaries, action items, and key takeaways using Gemini AI.\n    </div>\n</div>\n', unsafe_allow_html=True)
tab1, tab2 = st.tabs(['⚡ Summarize New Content', '📁 History Viewer'])
with tab1:
    col_input, col_info = st.columns([2, 1])
    with col_input:
        st.markdown('\n        <div class="glass-card">\n            <div class="glass-card-title">1. UPLOAD MEDIA SOURCE</div>\n        </div>\n        ', unsafe_allow_html=True)
        source_type = st.radio('Choose Input Type:', ['Local File Upload', 'Video URL (YouTube, Vimeo, etc.)'])
        uploaded_file = None
        url_input = ''
        if source_type == 'Local File Upload':
            uploaded_file = st.file_uploader('Upload Video or Audio File', type=['mp3', 'wav', 'm4a', 'mp4', 'mkv', 'mov', 'avi', 'webm'], help='Maximum file size depends on server limits. Supported audio and video formats.')
        else:
            url_input = st.text_input('Paste Video URL', placeholder='https://www.youtube.com/watch?v=...', help='Accepts YouTube links, generic video streams, and other pages supported by yt-dlp.')
        process_btn = st.button('🚀 Start Real-Time Pipeline', use_container_width=True)
    with col_info:
        st.markdown(f'\n        <div class="glass-card" style="height: 100%;">\n            <div class="glass-card-title">💡 ENGINE SPECIFICATIONS</div>\n            <p><b>Transcription Engine:</b> Local <code>Whisper ({os.getenv('WHISPER_MODEL', 'base')})</code></p>\n            <p><b>Summarization Model:</b> <code>Gemini 2.5 Flash</code></p>\n            <p><b>Required Setup:</b> Ensure your Gemini API key is configured. If the key is missing, the pipeline will still run local transcription and save your transcript with a placeholder warning.</p>\n        </div>\n        ', unsafe_allow_html=True)
    if process_btn:
        task_id = None
        error_msg = None
        if source_type == 'Local File Upload' and uploaded_file is not None:
            with st.spinner('Uploading file to server...'):
                try:
                    files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    response = requests.post(f'{BACKEND_URL}/api/upload', files=files)
                    if response.status_code == 200:
                        task_id = response.json()['task_id']
                    else:
                        error_msg = f'Failed to upload: {response.text}'
                except Exception as e:
                    error_msg = f'Backend communication error: {str(e)}'
        elif source_type == 'Video URL (YouTube, Vimeo, etc.)' and url_input:
            with st.spinner('Registering URL pipeline...'):
                try:
                    response = requests.post(f'{BACKEND_URL}/api/url', json={'url': url_input})
                    if response.status_code == 200:
                        task_id = response.json()['task_id']
                    else:
                        error_msg = f'Failed to process URL: {response.text}'
                except Exception as e:
                    error_msg = f'Backend communication error: {str(e)}'
        else:
            st.warning('Please provide a valid file upload or video URL source.')
        if error_msg:
            st.error(error_msg)
        if task_id:
            st.session_state.pipeline_running = True
            st.session_state.task_id = task_id
            st.rerun()
    if st.session_state.get('pipeline_running', False) and st.session_state.get('task_id'):
        task_id = st.session_state.task_id
        st.success(f'Pipeline active! Task ID: `{task_id}`. Establishing live stream...')
        status_container = st.empty()
        waveform_placeholder = st.empty()
        col_live_left, col_live_right = st.columns(2)
        with col_live_left:
            st.markdown('\n            <div class="glass-card">\n                <div class="glass-card-title">📢 LIVE TRANSCRIPT</div>\n            </div>\n            ', unsafe_allow_html=True)
            transcript_placeholder = st.empty()
        with col_live_right:
            st.markdown('\n            <div class="glass-card">\n                <div class="glass-card-title">🤖 AI ANALYSIS & LOGS</div>\n            </div>\n            ', unsafe_allow_html=True)
            logs_placeholder = st.empty()
            ai_thinking_placeholder = st.empty()
            summary_placeholder = st.empty()
        state = {'logs_text': '', 'transcript_segments': [], 'final_summary': None}

        async def run_websocket_client():
            ws_endpoint = f'{WS_URL}/ws/task/{task_id}'
            try:
                async with websockets.connect(ws_endpoint) as websocket:
                    while True:
                        message = await websocket.recv()
                        event = json.loads(message)
                        if event['type'] == 'catchup':
                            state['logs_text'] = event['logs']
                            state['transcript_segments'] = event['transcript']
                            if event['status'] in ['completed', 'failed']:
                                if event['summary']:
                                    state['final_summary'] = {'summary': event['summary'], 'key_points': event['key_points'], 'action_items': event['action_items'], 'discussion_topics': event['discussion_topics']}
                                break
                        elif event['type'] == 'status_update':
                            status_name = event['status']
                            status_log = event['log']
                            if status_log:
                                state['logs_text'] += status_log + '\n'
                            badge_class = f'badge-{status_name}'
                            status_container.markdown(f'\n                            <div style="display:flex; align-items:center; margin-bottom: 12px;">\n                                <b>Current Pipeline State:</b> \n                                <span class="status-badge {badge_class}">{status_name}</span>\n                            </div>\n                            ', unsafe_allow_html=True)
                            if status_name in ['processing_audio', 'transcribing']:
                                waveform_placeholder.markdown('\n                                <div class="waveform-container">\n                                    <div class="bar"></div>\n                                    <div class="bar"></div>\n                                    <div class="bar"></div>\n                                    <div class="bar"></div>\n                                    <div class="bar"></div>\n                                    <div class="bar"></div>\n                                    <div class="bar"></div>\n                                </div>\n                                ', unsafe_allow_html=True)
                            else:
                                waveform_placeholder.empty()
                            if status_name == 'summarizing':
                                ai_thinking_placeholder.markdown('\n                                <div class="ai-pulse-container">\n                                    <div class="ai-pulse"></div>\n                                    <div style="font-weight:bold; color:#8A2BE2;">AI Summarizer is thinking...</div>\n                                </div>\n                                ', unsafe_allow_html=True)
                            else:
                                ai_thinking_placeholder.empty()
                        elif event['type'] == 'log':
                            state['logs_text'] += f'[LOG] {event['message']}\n'
                        elif event['type'] == 'segment':
                            state['transcript_segments'].append(event['segment'])
                        elif event['type'] == 'completed':
                            state['final_summary'] = {'summary': event['summary'], 'key_points': event['key_points'], 'action_items': event['action_items'], 'discussion_topics': event['discussion_topics']}
                            status_container.markdown(f'\n                            <div style="display:flex; align-items:center; margin-bottom: 12px;">\n                                <b>Current Pipeline State:</b> \n                                <span class="status-badge badge-completed">completed</span>\n                            </div>\n                            ', unsafe_allow_html=True)
                            break
                        elif event['type'] == 'error':
                            st.error(f'Pipeline Error: {event['message']}')
                            status_container.markdown(f'\n                            <div style="display:flex; align-items:center; margin-bottom: 12px;">\n                                <b>Current Pipeline State:</b> \n                                <span class="status-badge badge-failed">failed</span>\n                            </div>\n                            ', unsafe_allow_html=True)
                            break
                        transcript_html = "<div class='scroll-container'>"
                        for seg in state['transcript_segments']:
                            ts = format_time(seg['start'])
                            transcript_html += f"<div><span class='segment-timestamp'>[{ts}]</span><span class='segment-text'>{seg['text']}</span></div>"
                        transcript_html += '</div>'
                        transcript_placeholder.markdown(transcript_html, unsafe_allow_html=True)
                        if not state['final_summary']:
                            with logs_placeholder.container():
                                st.markdown('<b>System Logs</b>', unsafe_allow_html=True)
                                st.code(state['logs_text'], language='text')
            except Exception as e:
                st.error(f'WebSocket connection failure: {str(e)}')
        asyncio.run(run_websocket_client())
        if state['final_summary']:
            ai_thinking_placeholder.empty()
            logs_placeholder.empty()
            with summary_placeholder.container():
                st.markdown('### 📝 AI Executive Summary')
                st.info(state['final_summary']['summary'])
                col_sum_left, col_sum_right = st.columns(2)
                with col_sum_left:
                    st.markdown('#### 💡 Key Takeaways')
                    for pt in state['final_summary']['key_points']:
                        st.markdown(f'- {pt}')
                    st.markdown('<br>#### 🏷️ Topics Covered', unsafe_allow_html=True)
                    for topic in state['final_summary']['discussion_topics']:
                        st.markdown(f'`{topic}`')
                with col_sum_right:
                    st.markdown('#### ✅ Action Items Checklist')
                    for idx, item in enumerate(state['final_summary']['action_items']):
                        st.checkbox(item, key=f'live_action_{idx}')
            st.markdown('---')
            st.info('🎉 Processing complete! You can retrieve this recording from the **History Viewer** tab anytime.')
            st.session_state.pipeline_running = False
            if st.button('🔄 Summarize Another Video/Audio', use_container_width=True):
                st.session_state.task_id = None
                st.rerun()
with tab2:
    if selected_history_task:
        task = selected_history_task
        task_id = task['task_id']
        with st.spinner('Loading summary details...'):
            try:
                res = requests.get(f'{BACKEND_URL}/api/history/{task_id}')
                if res.status_code == 200:
                    task = res.json()
            except Exception as e:
                st.error(f'Failed to fetch task details: {str(e)}')
        st.markdown(f'\n        <div style="display:flex; align-items:center; margin-bottom: 20px;">\n            <h2 style="margin:0; color:#45A29E;">{task['file_name']}</h2>\n            <span class="status-badge badge-{task['status']}">{task['status']}</span>\n        </div>\n        ', unsafe_allow_html=True)
        col_act1, col_act2, col_act3, _ = st.columns([1, 1.2, 1, 4])
        markdown_report = f'# Executive Summary Report\n**File Name:** {task['file_name']}\n**Generated At:** {task['created_at']}\n**Task ID:** {task['task_id']}\n\n## 1. Executive Summary\n{task['summary'] or 'No summary generated.'}\n\n## 2. Key Takeaways\n'
        if task['key_points']:
            for kp in task['key_points']:
                markdown_report += f'- {kp}\n'
        else:
            markdown_report += 'No key takeaways extracted.\n'
        markdown_report += '\n## 3. Action Items\n'
        if task['action_items']:
            for ai in task['action_items']:
                markdown_report += f'- [ ] {ai}\n'
        else:
            markdown_report += 'No action items extracted.\n'
        markdown_report += '\n## 4. Topics Covered\n'
        if task['discussion_topics']:
            for topic in task['discussion_topics']:
                markdown_report += f'- `{topic}`\n'
        markdown_report += '\n## 5. Full Transcript\n'
        if task['transcript']:
            for seg in task['transcript']:
                ts = format_time(seg['start'])
                markdown_report += f'[{ts}] {seg['text']}\n'
        else:
            markdown_report += 'No transcript segments available.\n'
        col_act1.download_button(label='📥 Download Report (.md)', data=markdown_report, file_name=f'Summary_Report_{task_id[:8]}.md', mime='text/markdown', use_container_width=True)
        if col_act2.button('🗑️ Delete Recording', use_container_width=True):
            if delete_task(task_id):
                st.success('Task deleted successfully! Reloading...')
                st.rerun()
        col_hist_left, col_hist_right = st.columns(2)
        with col_hist_left:
            st.markdown('\n            <div class="glass-card">\n                <div class="glass-card-title">📝 EXAMINING TRANSCRIPT</div>\n            </div>\n            ', unsafe_allow_html=True)
            transcript_html = "<div class='scroll-container'>"
            if task['transcript']:
                for seg in task['transcript']:
                    ts = format_time(seg['start'])
                    transcript_html += f"<div><span class='segment-timestamp'>[{ts}]</span><span class='segment-text'>{seg['text']}</span></div>"
            else:
                transcript_html += '<div>No transcription segments available for this task.</div>'
            transcript_html += '</div>'
            st.markdown(transcript_html, unsafe_allow_html=True)
        with col_hist_right:
            st.markdown('\n            <div class="glass-card">\n                <div class="glass-card-title">🤖 EXECUTIVE AI SUMMARY</div>\n            </div>\n            ', unsafe_allow_html=True)
            if task['status'] == 'completed':
                st.info(task['summary'])
                col_sub_left, col_sub_right = st.columns(2)
                with col_sub_left:
                    st.markdown('#### 💡 Key Takeaways')
                    if task['key_points']:
                        for pt in task['key_points']:
                            st.markdown(f'- {pt}')
                    st.markdown('<br>#### 🏷️ Topics Covered', unsafe_allow_html=True)
                    if task['discussion_topics']:
                        for topic in task['discussion_topics']:
                            st.markdown(f'`{topic}`')
                with col_sub_right:
                    st.markdown('#### ✅ Action Items Checklist')
                    if task['action_items']:
                        for idx, item in enumerate(task['action_items']):
                            st.checkbox(item, key=f'hist_action_{idx}', value=False)
            elif task['status'] == 'failed':
                st.error(f'Task processing failed. Error: {task['error_message']}')
                st.text_area('System Logs', value=task['logs'], height=250, disabled=True, key=f'history_logs_failed_{task_id}')
            else:
                st.warning(f'Task is currently in progress. Status: {task['status']}')
                st.text_area('System Logs', value=task['logs'], height=250, disabled=True, key=f'history_logs_prog_{task_id}')
    else:
        st.markdown('\n        <div style="text-align:center; padding: 60px 20px; background:rgba(22, 27, 34, 0.5); border-radius:10px; border: 1px dashed rgba(255,255,255,0.05)">\n            <h3 style="color:#c5c6c7;">No Summary Selected</h3>\n            <p style="color:#8b949e;">Select a past summary from the left sidebar history to examine details, download reports, or review transcripts.</p>\n        </div>\n        ', unsafe_allow_html=True)