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
Run the included setup script to install system dependencies and python packages:
```bash
./setup.sh
```
