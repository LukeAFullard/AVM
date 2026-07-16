#!/bin/bash
set -e

# Default settings
DOWNLOAD_MODELS=false
MODEL_VARIANT="12b"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --download-models) DOWNLOAD_MODELS=true ;;
        --model-variant) MODEL_VARIANT="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

echo "Starting AVM setup..."

echo "[1/4] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y ffmpeg poppler-utils tesseract-ocr fluidsynth fluid-soundfont-gm wget curl

echo "[2/4] Installing Python packages..."
pip install -r requirements.txt

echo "[3/4] Installing Playwright and its dependencies..."
playwright install chromium
python -m playwright install-deps chromium

echo "[4/4] Handling AI Models..."
if [ "$DOWNLOAD_MODELS" = true ]; then
    echo "Downloading AI models into 'models' directory..."
    mkdir -p models

    # Determine the model URL and expected filename based on the variant for Gemma 4
    case $MODEL_VARIANT in
        2b)
            MODEL_URL="https://huggingface.co/google/gemma-4-2b-it-GGUF/resolve/main/gemma-4-2b-it-Q4_K_M.gguf?download=true"
            MODEL_FILENAME="gemma-4-2b-it-Q4_K_M.gguf"
            ;;
        9b)
            MODEL_URL="https://huggingface.co/google/gemma-4-9b-it-GGUF/resolve/main/gemma-4-9b-it-Q4_K_M.gguf?download=true"
            MODEL_FILENAME="gemma-4-9b-it-Q4_K_M.gguf"
            ;;
        12b)
            MODEL_URL="https://huggingface.co/google/gemma-4-12b-it-GGUF/resolve/main/gemma-4-12b-it-Q4_K_M.gguf?download=true"
            MODEL_FILENAME="gemma-4-12b-unified.gguf"
            ;;
        27b)
            MODEL_URL="https://huggingface.co/google/gemma-4-27b-it-GGUF/resolve/main/gemma-4-27b-it-Q4_K_M.gguf?download=true"
            MODEL_FILENAME="gemma-4-27b-it-Q4_K_M.gguf"
            ;;
        *)
            echo "Unknown model variant: $MODEL_VARIANT. Supported: 2b, 9b, 12b, 27b."
            exit 1
            ;;
    esac

    echo "Downloading Gemma 4 ${MODEL_VARIANT} model into models/..."
    if [ ! -f "models/$MODEL_FILENAME" ]; then
        wget -q --show-progress -O "models/$MODEL_FILENAME" "$MODEL_URL"
    else
        echo "Model $MODEL_FILENAME already exists in models/."
    fi

    echo "Downloading Piper TTS voice model (en_US-lessac-medium)..."
    if [ ! -f "models/en_US-lessac-medium.onnx" ]; then
        wget -q -O models/en_US-lessac-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx?download=true"
        wget -q -O models/en_US-lessac-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json?download=true"
    else
        echo "Piper voice models already exist in models/."
    fi
    echo "Models downloaded successfully."
else
    echo "Skipping model downloads. Use --download-models to automate this step."
    echo "Please ensure you manually download Gemma 4 (or another GGUF model) and a Piper voice model."
fi

echo "Setup complete! You can now run the pipeline."
