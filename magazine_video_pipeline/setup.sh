#!/bin/bash
sudo apt-get update && sudo apt-get install -y ffmpeg poppler-utils tesseract-ocr fluidsynth fluid-soundfont-gm
pip install -r requirements.txt
playwright install chromium