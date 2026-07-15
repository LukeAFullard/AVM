import os
import json
from pathlib import Path
from src.render_engine import PlaywrightRenderEngine
from src.audio_engine import AudioEngine

def generate_example():
    project_root = Path(__file__).parent
    workspace_dir = project_root / "data" / "workspace" / "example_workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # 1. Setup Audio (Mock 5 seconds)
    audio_engine = AudioEngine(voice_model="dummy", workspace_dir=str(project_root / "data" / "workspace"))
    audio_dir = workspace_dir / "04_audio_payload"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Generate 5 seconds of dummy WAV
    text = "listen to this advanced sound design"
    audio_engine._generate_dummy_wav(audio_dir / "narration_example_5s.wav", text)

    # Override dummy WAV with exactly 5 seconds
    import wave
    import math
    import struct
    sample_rate = 16000
    duration = 5.0
    n_samples = int(sample_rate * duration)
    with wave.open(str(audio_dir / "narration_example_5s.wav"), 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(n_samples):
            value = int(32767.0 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate) * 0.05) # quiet tone
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)

    # Generate 5 seconds of dummy timestamps, spacing words out
    words = text.split()
    word_data = []
    current_time = 1.0 # start after 1 sec
    for word in words:
        word_data.append({
            "text": word,
            "start": current_time,
            "end": current_time + 0.4,
            "confidence": 0.99
        })
        current_time += 0.6

    ts_data = {
        "text": text,
        "segments": [{"start": 0.0, "end": 5.0, "text": text, "words": word_data}]
    }
    with open(audio_dir / "timestamps_example_5s.json", "w") as f:
        json.dump(ts_data, f, indent=2)

    # 2. Setup Render Manifest
    manifest = {
        "project_id": "example_p1",
        "global_style": {
            "color_palette": "p", "caption_style": "c", "background_texture": "t",
            "primary_color": "#00FFDD", "secondary_color": "#FF00AA"
        },
        "scene_manifests": [
            {
                "scene_ref_id": "example_5s",
                "template_component": "headline_zoom",
                "visual_source": {"source_type": "magazine_scan", "target_page_number": 1, "crop_bbox_pct": [10.0, 10.0, 50.0, 50.0]},
                "transition_in": "fade",
                "foley_trigger": "none"
            }
        ]
    }
    with open(workspace_dir / "05_render_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # Copy a dummy image
    import shutil
    if (project_root / "data" / "workspace" / "vintage_commuter_page_1" / "00_source_page.png").exists():
        shutil.copy(project_root / "data" / "workspace" / "vintage_commuter_page_1" / "00_source_page.png", workspace_dir / "00_source_page.png")
    else:
        # Create a red square if it doesn't exist
        from PIL import Image
        img = Image.new('RGB', (1080, 1920), color = 'red')
        img.save(workspace_dir / "00_source_page.png")

    # 3. Render
    print("Rendering 5s example...")
    engine = PlaywrightRenderEngine(project_dir=str(workspace_dir), fps=60)
    engine.render_scene_to_mp4("example_5s", duration_sec=5.0)
    print("Example generated at: " + str(workspace_dir / "06_exports" / "example_5s.mp4"))

if __name__ == "__main__":
    generate_example()