import argparse
import logging
import json
import shutil
from pathlib import Path

from src.ingestion_engine import IngestionEngine
from src.editorial_engine import EditorialEngine
from src.audio_engine import AudioEngine
from src.quality_gatekeeper import VideoQualityGatekeeper, QualityGateException
from src.render_engine import PlaywrightRenderEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Automated Vintage Magazine Video Pipeline")
    parser.add_argument("--pdf_path", type=str, required=True, help="Path to the raw PDF file")
    parser.add_argument("--model_path", type=str, default="dummy", help="Path to the local LLM model (e.g., Gemma 4 12B GGUF)")
    parser.add_argument("--voice_model", type=str, default="dummy", help="Path to Piper voice model (.onnx), or 'dummy'")
    parser.add_argument("--workspace_dir", type=str, default="data/workspace", help="Directory for output workspaces")
    parser.add_argument("--bgm_path", type=str, default=None, help="Path to background music file (mp3/wav)")

    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        return

    workspace_dir = Path(args.workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ingestion
    logger.info("Starting Ingestion...")
    ingestion = IngestionEngine(raw_pdfs_dir=str(pdf_path.parent), workspace_dir=str(workspace_dir))
    ingestion.process_pdf(pdf_path)

    # 2. Find newly created workspaces for this PDF
    pdf_name = pdf_path.stem
    workspaces = [d for d in workspace_dir.iterdir() if d.is_dir() and d.name.startswith(f"{pdf_name}_page_")]

    if not workspaces:
        logger.warning(f"No workspaces generated for PDF: {pdf_path}")
        return

    editorial = EditorialEngine(model_path=args.model_path, workspace_dir=str(workspace_dir))
    audio = AudioEngine(voice_model=args.voice_model, workspace_dir=str(workspace_dir))
    gatekeeper = VideoQualityGatekeeper()

    for workspace in workspaces:
        logger.info(f"Processing pipeline for workspace: {workspace}")

        story_feedback = None
        visual_feedback = None
        max_retries = 3

        for attempt in range(max_retries):
            logger.info(f"Attempt {attempt + 1} of {max_retries} for {workspace}")

            # Orchestrate Editorial
            try:
                editorial.process_workspace(workspace, story_feedback=story_feedback, visual_feedback=visual_feedback)
            except Exception as e:
                logger.error(f"Error in editorial engine: {e}")
                break

            # Audio Engine
            audio.process_workspace(workspace)

            # Load artifacts for validation
            storyboard_path = workspace / "03_storyboard.json"
            render_manifest_path = workspace / "05_render_manifest.json"

            if not storyboard_path.exists() or not render_manifest_path.exists():
                logger.error("Missing JSON artifacts for validation.")
                break

            with open(storyboard_path, "r", encoding="utf-8") as f:
                storyboard = json.load(f)
            with open(render_manifest_path, "r", encoding="utf-8") as f:
                render_manifest = json.load(f)

            # Gather timestamps
            audio_dir = workspace / "04_audio_payload"
            whisper_timestamps = {}
            all_units = storyboard.get("hooks", []) + storyboard.get("body_scenes", [])
            for unit in all_units:
                ref_id = unit.get("hook_id") or unit.get("scene_id")
                if not ref_id:
                    continue
                ts_path = audio_dir / f"timestamps_{ref_id}.json"
                if ts_path.exists():
                    with open(ts_path, "r", encoding="utf-8") as f:
                        ts_payload = json.load(f)

                    # Handle both pre-formatted lists and whisper segment format
                    formatted_ts = []
                    if isinstance(ts_payload, list):
                        formatted_ts = ts_payload
                    elif isinstance(ts_payload, dict) and "segments" in ts_payload:
                        for seg in ts_payload.get("segments", []):
                            for w in seg.get("words", []):
                                formatted_ts.append({
                                    "word": w.get("text", ""),
                                    "start": w.get("start", 0.0),
                                    "end": w.get("end", 0.0)
                                })
                    whisper_timestamps[ref_id] = formatted_ts

            try:
                gatekeeper.validate_project(storyboard, render_manifest, whisper_timestamps)
                logger.info(f"Quality gatekeeper passed for {workspace}")

                # Render the scenes
                render_engine = PlaywrightRenderEngine(project_dir=str(workspace), bgm_path=args.bgm_path)
                for scene_manifest in render_manifest.get("scene_manifests", []):
                    scene_id = scene_manifest["scene_ref_id"]
                    timestamps = whisper_timestamps.get(scene_id, [])
                    duration_sec = timestamps[-1]["end"] if timestamps else 2.0
                    render_engine.render_scene_to_mp4(scene_id, duration_sec)

                break # Success, exit retry loop
            except QualityGateException as e:
                logger.warning(f"Quality Gate failed: {e}")
                story_feedback = None
                visual_feedback = None

                # Prioritize story violations first, then visual violations
                story_viol = next((v for v in e.violations if v.gate_name in ["ReadingSpeedWPM", "CaptionOverflow"]), None)
                if story_viol:
                    story_feedback = story_viol.reprompt_instruction
                    logger.info(f"Triggering story regeneration: {story_feedback}")
                    if storyboard_path.exists(): storyboard_path.unlink()
                    if render_manifest_path.exists(): render_manifest_path.unlink()
                    if audio_dir.exists(): shutil.rmtree(audio_dir)
                    continue

                visual_viol = next((v for v in e.violations if v.gate_name == "CropBoundaries"), None)
                if visual_viol:
                    visual_feedback = visual_viol.reprompt_instruction
                    logger.info(f"Triggering visual regeneration: {visual_feedback}")
                    if render_manifest_path.exists(): render_manifest_path.unlink()
                    continue

                break # If unknown violation, just break

if __name__ == "__main__":
    main()
