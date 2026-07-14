import os
import json
import subprocess
import urllib.request
import urllib.parse
import wave
import math
import struct
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

        visual_source = scene_config.get("visual_source", {})
        source_type = visual_source.get("source_type", "magazine_scan")

        image_path = self.project_dir / "00_source_page.png"
        bbox = visual_source.get("crop_bbox_pct", [0, 0, 100, 100])

        if source_type == "external_broll":
            broll_query = visual_source.get("broll_search_query", "")
            pexels_api_key = os.environ.get("PEXELS_API_KEY")
            if broll_query:
                try:
                    encoded_query = urllib.parse.quote(broll_query)
                    image_url = None

                    if pexels_api_key:
                        try:
                            url = f"https://api.pexels.com/v1/search?query={encoded_query}&orientation=portrait&per_page=1"
                            req = urllib.request.Request(url, headers={'Authorization': pexels_api_key})
                            with urllib.request.urlopen(req) as response:
                                data = json.loads(response.read().decode())
                                photos = data.get("photos", [])
                                if photos:
                                    image_url = photos[0].get("src", {}).get("large2x") or photos[0].get("src", {}).get("original")
                        except Exception as e:
                            print(f"Failed to fetch external broll from Pexels: {e}")

                    if not image_url:
                        # Fallback to Wikimedia Commons
                        try:
                            url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=filetype:bitmap%20{encoded_query}&gsrnamespace=6&gsrlimit=1&prop=imageinfo&iiprop=url&format=json"
                            req = urllib.request.Request(url, headers={'User-Agent': 'AVM-Pipeline/1.0'})
                            with urllib.request.urlopen(req) as response:
                                data = json.loads(response.read().decode())
                                pages = data.get("query", {}).get("pages", {})
                                if pages:
                                    first_page = list(pages.values())[0]
                                    image_info = first_page.get("imageinfo", [])
                                    if image_info:
                                        image_url = image_info[0].get("url")
                        except Exception as e:
                            print(f"Failed to fetch external broll from Wikimedia Commons: {e}")

                    if image_url:
                        scene_id = scene_config.get("scene_ref_id", "temp")
                        temp_broll_path = self.project_dir / f"00_broll_{scene_id}.png"

                        # Use custom user-agent for download too, just in case
                        download_req = urllib.request.Request(image_url, headers={'User-Agent': 'AVM-Pipeline/1.0'})
                        with urllib.request.urlopen(download_req) as dl_response:
                            with open(temp_broll_path, 'wb') as f:
                                f.write(dl_response.read())

                        image_path = temp_broll_path
                        bbox = [10.0, 10.0, 90.0, 90.0]
                except Exception as e:
                    print(f"Failed to fetch external broll for query '{broll_query}': {e}")
                    # Fallback to source page if API fails
                    pass

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

    def _generate_sfx_track(self, timestamps: list, duration_sec: float, output_path: Path):
        """Generates a synchronized pop sound effect track."""
        sample_rate = 48000
        n_samples = int(sample_rate * duration_sec)
        audio_data = [0.0] * n_samples

        for ts in timestamps:
            start_time = ts.get("start", 0.0)
            start_sample = int(start_time * sample_rate)

            # Simple "pop" sound: quick sine wave burst with exponential decay
            pop_duration = 0.05
            pop_samples = int(pop_duration * sample_rate)
            pop_freq = 800.0

            for i in range(pop_samples):
                idx = start_sample + i
                if idx < n_samples:
                    t = i / sample_rate
                    decay = math.exp(-t * 60) # Fast decay
                    val = 0.15 * math.sin(2.0 * math.pi * pop_freq * t) * decay
                    audio_data[idx] += val

        with wave.open(str(output_path), 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            # Pack data
            packed_data = bytearray()
            for sample in audio_data:
                # clamp and convert to 16-bit int
                clamped = max(-1.0, min(1.0, sample))
                int_val = int(clamped * 32767)
                packed_data.extend(struct.pack('<h', int_val))

            wav_file.writeframesraw(packed_data)


    def render_scene_to_mp4(self, scene_id: str, duration_sec: float):
        with open(self.project_dir / "05_render_manifest.json") as f:
            manifest = json.load(f)

        scene_config, timestamps = self.load_artifacts(scene_id)

        temp_html_path = self.build_html_payload(scene_config, timestamps, duration_sec, global_style=manifest.get("global_style"))

        audio_path = self.project_dir / "04_audio_payload" / f"narration_{scene_id}.wav"
        sfx_path = self.project_dir / "04_audio_payload" / f"sfx_pops_{scene_id}.wav"

        # Generate the synchronized sound effects track
        self._generate_sfx_track(timestamps, duration_sec, sfx_path)

        output_mp4 = self.project_dir / "06_exports" / f"{scene_id}.mp4"
        os.makedirs(output_mp4.parent, exist_ok=True)
        total_frames = int(duration_sec * self.fps)

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-f", "image2pipe", "-vcodec", "png", "-r", str(self.fps),
            "-i", "-",
            "-i", str(audio_path),
            "-i", str(sfx_path),
            "-f", "lavfi", "-i", "anoisesrc=c=pink:r=48000:a=0.015",
            "-f", "lavfi", "-i", "aevalsrc='0.02*sin(2*PI*50*t):s=48000'",
            "-f", "lavfi", "-i", "aevalsrc='0.1*sin(2*PI*110*t)+0.05*sin(2*PI*220*t):s=48000',chorus=0.7:0.9:55:0.4:0.25:2",
            "-filter_complex", "[1:a][2:a][3:a][4:a][5:a]amix=inputs=5:duration=first:dropout_transition=2:weights=1.0 0.8 0.5 0.5 0.3[a]",
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