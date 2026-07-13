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
            timestamps = json.load(f)
        scene_config = next(s for s in manifest["scene_manifests"] if s["scene_ref_id"] == scene_id)
        return scene_config, timestamps

    def build_html_payload(self, scene_config: dict, timestamps: list) -> Path:
        template = self.env.get_template("template.html.j2")
        image_path = self.project_dir / "00_source_page.png"
        bbox = scene_config["visual_source"].get("crop_bbox_pct", [0, 0, 100, 100])

        html_content = template.render(
            image_path=image_path.absolute(),
            bbox=bbox,
            timestamps=timestamps
        )
        temp_html = self.project_dir / "temp_render.html"
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        return temp_html

    def render_scene_to_mp4(self, scene_id: str, duration_sec: float):
        scene_config, timestamps = self.load_artifacts(scene_id)
        temp_html_path = self.build_html_payload(scene_config, timestamps)

        audio_path = self.project_dir / "04_audio_payload" / f"narration_{scene_id}.wav"
        output_mp4 = self.project_dir / "06_exports" / f"{scene_id}.mp4"
        os.makedirs(output_mp4.parent, exist_ok=True)
        total_frames = int(duration_sec * self.fps)

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-f", "image2pipe", "-vcodec", "png", "-r", str(self.fps),
            "-i", "-", "-i", str(audio_path), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output_mp4)
        ]

        print(f"[{scene_id}] Launching FFmpeg and Playwright ({total_frames} frames @ {self.fps} FPS)...")
        ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.goto(f"file://{temp_html_path.absolute()}")
            page.wait_for_load_state("networkidle")

            try:
                for frame in range(total_frames):
                    page.evaluate(f"window.seekToFrame({frame}, {self.fps}, {total_frames})")
                    ffmpeg_proc.stdin.write(page.screenshot(type="png", omit_background=False))
                    if frame % 30 == 0:
                        print(f"[{scene_id}] Progress: {round((frame/total_frames)*100, 1)}%", end="\r")
            finally:
                browser.close()
                if temp_html_path.exists(): os.remove(temp_html_path)

        ffmpeg_proc.stdin.close()
        ffmpeg_proc.wait()
        print(f"\n[{scene_id}] Render complete -> {output_mp4}")