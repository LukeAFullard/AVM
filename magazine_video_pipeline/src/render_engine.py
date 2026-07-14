import os
import json
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

class PlaywrightRenderEngine:
    def __init__(self, project_dir: str, fps: int = 60):
        self.project_dir = Path(project_dir)
        self.fps = fps
        # Assumes this script is run from project root, templates are in ../templates
        self.env = Environment(loader=FileSystemLoader(searchpath=str(self.project_dir.parent.parent.parent / "templates")))

    def load_artifacts(self, scene_id: str):
        with open(self.project_dir / "05_render_manifest.json") as f:
            manifest = json.load(f)
        with open(self.project_dir / "04_audio_payload" / f"timestamps_{scene_id}.json") as f:
            ts_payload = json.load(f)

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

        scene_config = next(s for s in manifest["scene_manifests"] if s["scene_ref_id"] == scene_id)
        return scene_config, formatted_ts

    def build_html_payload(self, scene_config: dict, timestamps: list, duration_sec: float, global_style: dict = None) -> Path:
        template = self.env.get_template("template.html.j2")
        image_path = self.project_dir / "00_source_page.png"
        bbox = scene_config["visual_source"].get("crop_bbox_pct", [0, 0, 100, 100])

        if global_style is None:
            global_style = {
                "font_family": "Bebas Neue",
                "primary_color": "#FFD700",
                "secondary_color": "#FF0055",
                "animation_easing": "cubic"
            }

        html_content = template.render(
            image_path=f"file://{image_path.absolute()}",
            bbox=bbox,
            timestamps=timestamps,
            duration_sec=duration_sec,
            global_style=global_style
        )
        temp_html = self.project_dir / "temp_render.html"
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        return temp_html

    def render_scene_to_mp4(self, scene_id: str, duration_sec: float):
        with open(self.project_dir / "05_render_manifest.json") as f:
            manifest = json.load(f)

        scene_config, timestamps = self.load_artifacts(scene_id)

        temp_html_path = self.build_html_payload(scene_config, timestamps, duration_sec, global_style=manifest.get("global_style"))

        audio_path = self.project_dir / "04_audio_payload" / f"narration_{scene_id}.wav"
        output_mp4 = self.project_dir / "06_exports" / f"{scene_id}.mp4"
        os.makedirs(output_mp4.parent, exist_ok=True)
        total_frames = int(duration_sec * self.fps)

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-f", "image2pipe", "-vcodec", "png", "-r", str(self.fps),
            "-i", "-", "-i", str(audio_path),
            "-f", "lavfi", "-i", "anoisesrc=c=pink:r=48000:a=0.02",
            "-f", "lavfi", "-i", "aevalsrc='0.05*sin(2*PI*50*t):s=48000'",
            "-filter_complex", "[1:a][2:a][3:a]amix=inputs=3:duration=first:dropout_transition=2:weights=1.0 0.5 0.5[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output_mp4)
        ]

        print(f"[{scene_id}] Launching FFmpeg and Playwright ({total_frames} frames @ {self.fps} FPS)...")
        ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=None)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.goto(f"file://{temp_html_path.absolute()}")
            page.wait_for_load_state("networkidle")

            try:
                for frame in range(total_frames):
                    page.evaluate(f"window.seekToFrame({frame}, {self.fps})")
                    try:
                        ffmpeg_proc.stdin.write(page.screenshot(type="png", omit_background=False))
                    except BrokenPipeError:
                        # ffmpeg gracefully finished processing frames due to -shortest flag
                        break

                    if frame % 30 == 0:
                        print(f"[{scene_id}] Progress: {round((frame/total_frames)*100, 1)}%", end="\r")
            finally:
                browser.close()
                if temp_html_path.exists(): os.remove(temp_html_path)

        ffmpeg_proc.stdin.close()
        ffmpeg_proc.wait()
        print(f"\n[{scene_id}] Render complete -> {output_mp4}")