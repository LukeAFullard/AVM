# Future Plans: Automated Vintage Magazine Video Pipeline

This document outlines the remaining features and scripts required to fully complete the 6-stage programmatic media engine. The initial scaffold (directory structure, schemas, render engine, and HTML templates) has been built and verified. The following pipeline stages need to be implemented:

## Phase 1: Data Ingestion & OCR
**Goal:** Process raw PDF magazine scans into structured layout-aware JSON.
- **Component to Build:** `src/ingestion_engine.py`
- **Responsibilities:**
  - Read PDFs from `data/raw_pdfs/`.
  - Extract images per page and store them as `00_source_page.png` in project workspaces.
  - Utilize layout-aware OCR (e.g., Docling, PaddleOCR, or Tesseract with layout analysis) to generate bounding boxes and text blocks.
  - Output results as `01_layout_ocr.json` (normalized coordinates and extracted text).

## Phase 2: Editorial Orchestration (LLM Agents)
**Goal:** Implement the three micro-agents defined in the original specification using a local instance of Gemma 4 12B Unified via `llama-cpp-python`.
- **Component to Build:** `src/editorial_engine.py`
- **Dependencies:** `llama-cpp-python`, local model weights.
- **Responsibilities:**
  - **Agent 1 (Topic Detector):** Ingest `01_layout_ocr.json`. Use strict JSON grammar enforcement based on `schemas/topic_evaluation.schema.json` to score and identify high-value stories. Output `02_topic_evaluation.json`.
  - **Agent 2 (Story Selector):** Read the evaluated topic and generate 3 distinct hooks and body scenes. Enforce JSON grammar based on `schemas/storyboard.schema.json`. Output `03_storyboard.json`.
  - **Agent 3 (Visual Planner):** Translate the storyboard narratives into visual parameters (crop percentages, components, transitions). Enforce JSON grammar based on `schemas/render_manifest.schema.json`. Output `05_render_manifest.json`.

## Phase 3: Audio Synthesis & Timing
**Goal:** Generate voiceovers and exact word-level timestamps.
- **Component to Build:** `src/audio_engine.py`
- **Responsibilities:**
  - Ingest `03_storyboard.json`.
  - Use a local Text-to-Speech (TTS) engine (e.g., Coqui TTS, Piper, or equivalent local engine) to synthesize `.wav` files for each narration block into `04_audio_payload/`.
  - Use an alignment model (e.g., Whisper timestamping) to generate exact word start/end times.
  - Output timestamps as JSON payloads corresponding to the generated `.wav` files (e.g., `timestamps_hook_a.json`).

## Phase 4: Integration & Workflow Automation
**Goal:** Tie all stages together into a single master script.
- **Component to Build:** `src/main_pipeline.py`
- **Responsibilities:**
  - Read input arguments (e.g., PDF path).
  - Sequentially trigger the ingestion, editorial (LLMs), audio, and quality gatekeeper modules.
  - If the quality gatekeeper fails, automatically feed the error messages back to the responsible LLM agent to heal and regenerate the content.
  - Finally, trigger `src/render_engine.py` to produce the final `.mp4` artifacts.

## Summary
By following these phases, the current foundational render and validation layer will be augmented by the upstream AI parsing, planning, and audio generation modules, realizing the vision of an entirely local, decoupled media engine.