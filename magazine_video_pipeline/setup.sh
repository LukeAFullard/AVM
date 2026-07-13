#!/bin/bash
sudo apt-get update && sudo apt-get install -y ffmpeg poppler-utils tesseract-ocr
pip install -r requirements.txt
playwright install chromium