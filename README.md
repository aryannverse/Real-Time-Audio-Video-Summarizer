# Real-Time Video/Audio Summarization Engine

An industry-standard, end-to-end AI pipeline that transcribes video or audio files and URL links (like YouTube) locally for free, and generates structured executive summaries, key takeaways, action items, and topic lists using the Gemini API. 

## Key Features
* 🎙️ **Local Speech-to-Text**: Free local transcription using `faster-whisper` (runs efficiently on CPU with `int8` quantization). No cloud APIs needed for transcription.
* 🤖 **AI Summarizer**: Leverages Google Gemini API (`gemini-2.5-flash` model, free tier) with native Pydantic structured output parsing.
* ⚡ **Real-Time Streaming**: Streamlit frontend connects to FastAPI backend over WebSockets to display scrolling live transcripts and server logs.
* 📁 **History Viewer**: Database layer powered by SQLite tracks past recordings, summaries, transcripts, and metadata. Fully searchable from the dashboard.
* 📊 **Exportable Reports**: Download summary reports as cleanly formatted Markdown files or copy summaries directly.
* 🎨 **Premium Modern Design**: Sleek dark UI with glassmorphism elements, CSS-animated bouncing audio waveforms, and AI "thinking" pulse.

---

## Project Structure
```
.
├── backend/
│   ├── __init__.py
│   ├── main.py          # FastAPI application & WebSocket endpoints
│   ├── database.py      # SQLAlchemy SQLite session management
│   ├── models.py        # Database models & Pydantic schemas
│   ├── pipeline.py      # Transcription & Gemini pipeline orchestrator
│   └── utils.py         # Subprocess FFmpeg audio extraction & yt-dlp downloading
├── frontend/
│   └── app.py           # Streamlit dashboard & live streaming client
├── scratch/
│   └── test_pipeline.py # Backend database and Whisper model loader test
├── Dockerfile           # Unified Python base image with FFmpeg installed
├── docker-compose.yml   # Multi-service setup (FastAPI + Streamlit)
├── requirements.txt     # Complete Python dependencies list
├── .env.example         # Template configuration file
└── README.md            # Documentation
```

---

## Prerequisites
1. **Python 3.10+**: Ensure Python is installed locally.
2. **FFmpeg**: Required to extract audio from video uploads.
   * *macOS (Homebrew)*: `brew install ffmpeg` (already installed on this machine)
   * *Windows (Scoop/Choco)*: `scoop install ffmpeg` or `choco install ffmpeg`
   * *Linux (APT)*: `sudo apt install ffmpeg`
3. **Google Gemini API Key**: Get a free API Key from [Google AI Studio](https://aistudio.google.com/).

---

## Getting Started

### Option A: Local Run (Recommended for Development)

1. **Clone & Set Up Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Open the `.env` file and insert your Gemini API Key:
   ```env
   GEMINI_API_KEY=AIzaSy...
   ```

3. **Start FastAPI Backend**:
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```
   *The API will be available at `http://localhost:8000` and API docs at `http://localhost:8000/docs`.*

4. **Start Streamlit Frontend** (in a separate terminal tab):
   ```bash
   streamlit run frontend/app.py --server.port=8501 --server.address=0.0.0.0
   ```
   *Open your browser and navigate to `http://localhost:8501` to use the application.*

---

### Option B: Run via Docker Compose

Docker builds both containers and installs all required packages (including FFmpeg) inside the containers.

1. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your `GEMINI_API_KEY` key.

2. **Spin Up Containers**:
   ```bash
   docker-compose up --build
   ```

3. **Access Services**:
   * **Streamlit Dashboard**: `http://localhost:8501`
   * **FastAPI Docs**: `http://localhost:8000/docs`

---

## How It Works Under the Hood
1. **Upload / Submission**: User uploads a file or inputs a video link.
2. **Audio Pre-processing**: If it's a URL, `yt-dlp` fetches the audio. If it's a local video, `FFmpeg` extracts it and saves it as a 16kHz mono `.wav` file (ideal format for Whisper).
3. **Local STT**: `faster-whisper` processes the wav file segment-by-segment in a background thread, pushing live segments and timestamps into a queue.
4. **WebSocket Stream**: FastAPI WebSocket server reads from the queue and sends logs/segments to the Streamlit frontend where they render instantly.
5. **AI Summarization**: Once transcription concludes, the full text is dispatched to the Gemini API. Gemini returns structured JSON matching our Pydantic schema (`StructuredSummary`).
6. **Persistence**: The final transcript, log trace, summaries, and metadata are saved to the local SQLite database.
