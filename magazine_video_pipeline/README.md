# Automated Vintage Magazine Video Pipeline (AVM)

The Automated Vintage Magazine Video Pipeline is a fully decoupled, 6-stage programmatic media engine that processes vintage magazine PDFs into broadcast-ready, vertical short-form videos (.mp4) entirely locally.

## Project Status

**The product is fully complete and operational.** All phases previously outlined in the future plans have been successfully implemented:

1. **Phase 1: Data Ingestion & OCR (`src/ingestion_engine.py`)**
   - Extracts raw PDFs into page-specific directories.
   - Generates normalized bounding boxes and text blocks using Tesseract OCR.
2. **Phase 2: Editorial Orchestration (`src/editorial_engine.py`)**
   - Orchestrates three sequential LLM agents (Topic Detector, Story Selector, Visual Planner) using a local Gemma 4 12B Unified model with strict JSON schema enforcement via `llama-cpp-python`.
3. **Phase 3: Audio Synthesis & Timing (`src/audio_engine.py`)**
   - Synthesizes narration using local TTS (`piper-tts`).
   - Extracts exact word-level timestamps using `whisper-timestamped`.
4. **Phase 4: Integration & Workflow Automation (`src/main_pipeline.py`)**
   - Central CLI orchestrator tying all stages together.
   - Implements a self-healing retry loop via `VideoQualityGatekeeper` to catch visual/pacing violations and automatically regenerate flawed JSON artifacts.
5. **Phase 5: Rendering Engine (`src/render_engine.py`)**
   - Headless Playwright streams raw PNG bytes directly to an FFmpeg subprocess.
   - Visual motion driven mathematically without CSS transitions.

## Usage

To run the pipeline on a raw PDF:
```bash
PYTHONPATH=. python src/main_pipeline.py --pdf_path <path_to_pdf> --model_path <path_to_gguf_model> --voice_model <path_to_piper_model>
```

For testing, you can use the dummy mode to bypass model inference:
```bash
PYTHONPATH=. python src/main_pipeline.py --pdf_path <path_to_pdf> --model_path dummy --voice_model dummy
```

## Setup

### 1. System Dependencies
You need to install the core system dependencies required for video rendering, optical character recognition, and audio synthesis:

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg poppler-utils tesseract-ocr fluidsynth fluid-soundfont-gm
```
**macOS:**
```bash
brew install ffmpeg poppler tesseract fluidsynth fluid-synth
```

### 2. Python Environment Setup
Install the required Python packages. It is highly recommended to use a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Playwright Setup
The rendering engine uses Playwright (Chromium) to stream HTML5 canvas animations directly to FFmpeg. You must install the Playwright browsers:
```bash
playwright install chromium
playwright install-deps chromium
```

### 4. API Keys & Local B-Roll (Optional)
To enable high-quality TTS and dynamic external B-roll, set your API keys in your environment variables:
```bash
export ELEVENLABS_API_KEY="your_elevenlabs_key"  # For premium AI voices
export PEXELS_API_KEY="your_pexels_key"          # For high-quality vertical B-roll videos
```
*(If these are not provided, the pipeline gracefully falls back to local `piper-tts` and free Wikimedia Commons images).*

**Completely Offline B-Roll (No API):**
If you do not want to use any external APIs (even free ones like Wikimedia), you can create a folder named `local_broll` in the root of the project directory (`magazine_video_pipeline/data/local_broll`). Drop any `.mp4`, `.jpg`, or `.png` stock files into this folder. If the pipeline attempts to fetch `external_broll` and APIs fail or are disabled, it will automatically fall back to randomly selecting media from this local directory.

## Testing Specific Components

*   **Visual Editor/Preview Studio:** To tweak the HTML template (`templates/template.html.j2`) and preview the kinetic typography animations in real-time before rendering a full video, run:
    ```bash
    python preview_studio.py
    ```
    *(This will start a local server on `http://localhost:5000`)*
*   **Fast Render Test:** To quickly test rendering a 5-second mock scene without running the entire LLM pipeline:
    ```bash
    PYTHONPATH=. python generate_example.py
    ```
    *(The output will be saved as `example_5s.mp4`)*
