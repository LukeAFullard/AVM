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

You can set up the project automatically using the provided setup script, or manually step-by-step.

### Automated Setup (Recommended)

We provide a bash script that will handle all system dependencies, Python packages, Playwright installation, and optionally, AI model downloads.

1. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Run the setup script. To also automatically download the required Gemma 4 model and the default Piper TTS voice model into a `models/` directory, use the `--download-models` flag. You can also specify a variant (e.g. `2b`, `9b`, `12b`, `27b`) with `--model-variant`:
   ```bash
   bash setup.sh --download-models --model-variant 12b
   ```
   *(If you omit the flag, you will need to download the AI models manually as outlined in Step 4 below.)*

### Manual Setup (Step-by-Step)

If you prefer to install things manually or are not on a Debian/Ubuntu system, follow these steps exactly:

#### Step 1: Install System Dependencies
You need to install the core system dependencies required for video rendering, optical character recognition, and audio synthesis.

For **Ubuntu/Debian** systems, run:
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg poppler-utils tesseract-ocr fluidsynth fluid-soundfont-gm wget curl
```

For **macOS** systems, run:
```bash
brew install ffmpeg poppler tesseract fluidsynth fluid-synth wget curl
```

#### Step 2: Set Up Python Environment
Install the required Python packages. It is highly recommended to use a virtual environment to avoid conflicts.

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
2. Activate the virtual environment:
   - On Linux/macOS:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
3. Install the required Python packages. Ensure you are in the directory with `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

#### Step 3: Install Playwright
The rendering engine uses Playwright (Chromium) to stream HTML5 canvas animations directly to FFmpeg. You must install the Playwright browsers.

Run the following commands:
1. Install the Chromium browser:
   ```bash
   playwright install chromium
   ```
2. Install necessary system dependencies for Chromium (Ubuntu/Debian only):
   ```bash
   python -m playwright install-deps chromium
   ```

#### Step 4: AI Models Setup (LLM & TTS)
Gemma 4 is a Large Language Model (LLM), and Piper is a Text-To-Speech (TTS) engine. Their model weights **are not** installed via `requirements.txt` (which only installs the inference engines/Python wrappers like `llama-cpp-python` and `piper-tts`). Model weights are large binary files that must be downloaded separately.

If you did not use the `--download-models` flag with `setup.sh`, you must download the weights manually.

1. **Create a models directory:**
   ```bash
   mkdir -p models
   ```
2. **Download Gemma 4 Model Weights (.gguf):** Download the appropriate Gemma 4 model weights (in `.gguf` format) from a source like Hugging Face. Place the downloaded `.gguf` file inside your `models/` folder. You will pass the path to this file to the pipeline using the `--model_path` argument (e.g., `--model_path models/gemma-4-12b-unified.gguf`).
3. **Download Piper Voice Model (.onnx and .onnx.json):** Download the Piper voice model weights you wish to use from the [Piper Voices repository](https://huggingface.co/rhasspy/piper-voices). You need **both** the `.onnx` file and the `.onnx.json` file. Place them in your `models/` folder. You will pass the path to the `.onnx` file using the `--voice_model` argument (e.g., `--voice_model models/en_US-lessac-medium.onnx`).

### Step 5: API Keys & Local B-Roll (Optional)
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
