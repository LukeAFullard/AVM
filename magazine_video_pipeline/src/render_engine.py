import os
import json
import subprocess
import urllib.request
import urllib.parse
import wave
import math
import struct
import random
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from midiutil import MIDIFile
from playwright.sync_api import sync_playwright

class PlaywrightRenderEngine:
    def __init__(self, project_dir: str, fps: int = 60, bgm_path: str = None):
        self.project_dir = Path(project_dir)
        self.fps = fps
        self.bgm_path = bgm_path
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
        highlight_words = [w.lower() for w in scene_config.get("highlight_words", [])]
        source_type = visual_source.get("source_type", "magazine_scan")
        transition_in = scene_config.get("transition_in", "cut")
        template_component = scene_config.get("template_component", "headline_zoom")

        image_path = self.project_dir / "00_source_page.png"
        bbox = visual_source.get("crop_bbox_pct", [0, 0, 100, 100])

        media_type = "image"
        media_attribution = ""

        if source_type == "external_broll":
            broll_query = visual_source.get("broll_search_query", "")
            pexels_api_key = os.environ.get("PEXELS_API_KEY")
            if broll_query:
                try:
                    encoded_query = urllib.parse.quote(broll_query)
                    media_url = None
                    downloaded_ext = "png"

                    if pexels_api_key:
                        # 1. Try to fetch video first
                        try:
                            url = f"https://api.pexels.com/videos/search?query={encoded_query}&orientation=portrait&per_page=1"
                            req = urllib.request.Request(url, headers={'Authorization': pexels_api_key})
                            with urllib.request.urlopen(req) as response:
                                data = json.loads(response.read().decode())
                                videos = data.get("videos", [])
                                if videos:
                                    video_files = videos[0].get("video_files", [])
                                    if video_files:
                                        # Prefer hd or higher quality
                                        best_video = max(video_files, key=lambda v: (v.get("width", 0) * v.get("height", 0)))
                                        media_url = best_video.get("link")
                                        if media_url:
                                            media_type = "video"
                                            downloaded_ext = "mp4"
                                            video_author = videos[0].get("user", {}).get("name", "Unknown Artist")
                                            media_attribution = f"Video by {video_author} on Pexels"
                        except Exception as e:
                            print(f"Failed to fetch external video broll from Pexels: {e}")

                        # 2. Fallback to image from Pexels
                        if not media_url:
                            try:
                                url = f"https://api.pexels.com/v1/search?query={encoded_query}&orientation=portrait&per_page=1"
                                req = urllib.request.Request(url, headers={'Authorization': pexels_api_key})
                                with urllib.request.urlopen(req) as response:
                                    data = json.loads(response.read().decode())
                                    photos = data.get("photos", [])
                                    if photos:
                                        media_url = photos[0].get("src", {}).get("large2x") or photos[0].get("src", {}).get("original")
                                        photo_author = photos[0].get("photographer", "Unknown Artist")
                                        media_attribution = f"Photo by {photo_author} on Pexels"
                            except Exception as e:
                                print(f"Failed to fetch external image broll from Pexels: {e}")

                    if not media_url:
                        # Fallback to Wikimedia Commons (images only)
                        try:
                            # Enforce Public Domain / CC0 for legal monetization without complex attribution
                            url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=filetype:bitmap%20{encoded_query}%20incategory:%22Public_domain%22&gsrnamespace=6&gsrlimit=1&prop=imageinfo&iiprop=url|extmetadata&format=json"
                            req = urllib.request.Request(url, headers={'User-Agent': 'AVM-Pipeline/1.0'})
                            with urllib.request.urlopen(req) as response:
                                data = json.loads(response.read().decode())
                                pages = data.get("query", {}).get("pages", {})
                                if pages:
                                    first_page = list(pages.values())[0]
                                    image_info = first_page.get("imageinfo", [])
                                    if image_info:
                                        media_url = image_info[0].get("url")
                                        photo_author = image_info[0].get("extmetadata", {}).get("Artist", {}).get("value", "Unknown Artist")
                                        # Strip HTML tags if present in author
                                        import re
                                        photo_author = re.sub('<[^<]+>', '', photo_author)
                                        media_attribution = f"Media by {photo_author} (Wikimedia Commons)"
                        except Exception as e:
                            print(f"Failed to fetch external broll from Wikimedia Commons: {e}")

                    if media_url:
                        scene_id = scene_config.get("scene_ref_id", "temp")
                        temp_broll_path = self.project_dir / f"00_broll_{scene_id}.{downloaded_ext}"

                        # Use custom user-agent for download too, just in case
                        download_req = urllib.request.Request(media_url, headers={'User-Agent': 'AVM-Pipeline/1.0'})
                        with urllib.request.urlopen(download_req) as dl_response:
                            with open(temp_broll_path, 'wb') as f:
                                f.write(dl_response.read())

                        image_path = temp_broll_path
                        bbox = [10.0, 10.0, 90.0, 90.0]
                except Exception as e:
                    print(f"Failed to fetch external broll for query '{broll_query}': {e}")

            # Local fallback if APIs are disabled or fail
            if image_path == self.project_dir / "00_source_page.png":
                local_broll_dir = self.project_dir.parent.parent / "local_broll"
                if local_broll_dir.exists() and any(local_broll_dir.iterdir()):
                    print(f"Using random local B-roll from {local_broll_dir}")
                    import random
                    valid_files = [f for f in local_broll_dir.iterdir() if f.suffix.lower() in ['.mp4', '.mov', '.png', '.jpg', '.jpeg']]
                    if valid_files:
                        chosen_broll = random.choice(valid_files)
                        image_path = chosen_broll
                        media_type = "video" if chosen_broll.suffix.lower() in ['.mp4', '.mov'] else "image"
                        bbox = [0, 0, 100, 100]
                        media_attribution = f"Local Media ({chosen_broll.name})"
                    # Fallback to source page if API fails
                    pass

        secondary_media_path = ""
        secondary_media_type = ""

        if template_component == "split_screen_broll":
            pexels_api_key = os.environ.get("PEXELS_API_KEY")
            secondary_media_url = None
            if pexels_api_key:
                try:
                    # Query for something satisfying
                    sec_query = urllib.parse.quote("satisfying kinetic sand")
                    url = f"https://api.pexels.com/videos/search?query={sec_query}&orientation=portrait&per_page=1"
                    req = urllib.request.Request(url, headers={'Authorization': pexels_api_key})
                    with urllib.request.urlopen(req) as response:
                        data = json.loads(response.read().decode())
                        videos = data.get("videos", [])
                        if videos:
                            video_files = videos[0].get("video_files", [])
                            if video_files:
                                best_video = max(video_files, key=lambda v: (v.get("width", 0) * v.get("height", 0)))
                                secondary_media_url = best_video.get("link")
                except Exception as e:
                    print(f"Failed to fetch secondary broll from Pexels: {e}")

            scene_id = scene_config.get("scene_ref_id", "temp_sec")
            temp_sec_path = self.project_dir / f"00_secondary_broll_{scene_id}.mp4"

            if secondary_media_url:
                try:
                    download_req = urllib.request.Request(secondary_media_url, headers={'User-Agent': 'AVM-Pipeline/1.0'})
                    with urllib.request.urlopen(download_req) as dl_response:
                        with open(temp_sec_path, 'wb') as f:
                            f.write(dl_response.read())
                    secondary_media_path = temp_sec_path
                    secondary_media_type = "video"
                except Exception as e:
                    print(f"Failed to download secondary broll: {e}")
            else:
                local_broll_dir = self.project_dir.parent.parent / "local_broll"
                if local_broll_dir.exists() and any(local_broll_dir.iterdir()):
                    import random
                    valid_files = [f for f in local_broll_dir.iterdir() if f.suffix.lower() in ['.mp4', '.mov']]
                    if valid_files:
                        chosen_broll = random.choice(valid_files)
                        secondary_media_path = chosen_broll
                        secondary_media_type = "video"

        if global_style is None:
            global_style = {
                "font_family": "Bebas Neue",
                "primary_color": "#FFD700",
                "secondary_color": "#FF0055",
                "animation_easing": "cubic"
            }

        render_kwargs = {
            "image_path": f"file://{image_path.absolute()}",
            "media_type": media_type,
            "bbox": bbox,
            "timestamps": timestamps,
            "duration_sec": duration_sec,
            "global_style": global_style,
            "highlight_words": highlight_words,
            "source_type": source_type,
            "media_attribution": media_attribution,
            "transition_in": transition_in,
            "template_component": template_component
        }
        if secondary_media_path:
            render_kwargs["secondary_media_path"] = f"file://{secondary_media_path.absolute()}"
            render_kwargs["secondary_media_type"] = secondary_media_type

        html_content = template.render(**render_kwargs)
        temp_html = self.project_dir / "temp_render.html"
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        return temp_html

    def _generate_sfx_track(self, timestamps: list, duration_sec: float, output_path: Path, highlight_words: list = None):
        """Generates advanced cinematic SFX using MIDI & FluidSynth."""
        if highlight_words is None:
            highlight_words = []
        track = 0
        time = 0
        tempo = 120

        MyMIDI = MIDIFile(1)
        MyMIDI.addTempo(track, time, tempo)

        # Setup channels/instruments (Program Change)
        MyMIDI.addProgramChange(track, 0, 0, 48) # Strings (drone)
        MyMIDI.addProgramChange(track, 1, 0, 47) # Timpani (impact)
        MyMIDI.addProgramChange(track, 2, 0, 115) # Woodblock (word ticks)
        MyMIDI.addProgramChange(track, 3, 0, 119) # Reverse Cymbal (whoosh approximation)

        # 1. Cinematic Impact (Timpani) at T=0
        MyMIDI.addNote(track, 1, 36, 0, 2, 110)

        # 2. Transition Whoosh (Reverse Cymbal) at T=0
        MyMIDI.addNote(track, 3, 49, 0, 1, 90)

        # Drone (Low Strings) for entire duration
        duration_beats = duration_sec * (tempo / 60.0)
        MyMIDI.addNote(track, 0, 36, 0, duration_beats, 70)
        MyMIDI.addNote(track, 0, 43, 0, duration_beats, 70)

        # 3. UI ticks for each word
        for ts in timestamps:
            start_time = ts.get("start", 0.0)
            beat = start_time * (tempo / 60.0)

            raw_word = ts.get("text", ts.get("word", ""))
            clean_word = raw_word.replace(",", "").replace(".", "").replace("!", "").replace("?", "").lower()

            if clean_word in highlight_words:
                MyMIDI.addNote(track, 2, 65, beat, 0.25, 120)
            else:
                MyMIDI.addNote(track, 2, 60, beat, 0.25, 90)

        temp_midi = output_path.with_suffix(".mid")
        with open(temp_midi, "wb") as output_file:
            MyMIDI.writeFile(output_file)

        # Render MIDI to WAV using FluidSynth
        sf2_path = "/usr/share/sounds/sf2/FluidR3_GM.sf2"
        try:
            subprocess.run([
                "fluidsynth", "-ni", sf2_path, str(temp_midi),
                "-F", str(output_path), "-r", "48000"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            print(f"Failed to render MIDI to WAV: {e}")
            raise e

        temp_midi.unlink(missing_ok=True)


    def render_scene_to_mp4(self, scene_id: str, duration_sec: float):
        with open(self.project_dir / "05_render_manifest.json") as f:
            manifest = json.load(f)

        scene_config, timestamps = self.load_artifacts(scene_id)

        temp_html_path = self.build_html_payload(scene_config, timestamps, duration_sec, global_style=manifest.get("global_style"))

        audio_path = self.project_dir / "04_audio_payload" / f"narration_{scene_id}.wav"
        sfx_path = self.project_dir / "04_audio_payload" / f"sfx_pops_{scene_id}.wav"

        highlight_words = [w.lower() for w in scene_config.get("highlight_words", [])]

        # Generate the synchronized sound effects track
        self._generate_sfx_track(timestamps, duration_sec, sfx_path, highlight_words)

        output_mp4 = self.project_dir / "06_exports" / f"{scene_id}.mp4"
        temp_video_mkv = self.project_dir / "06_exports" / f"temp_{scene_id}_video.mkv"
        os.makedirs(output_mp4.parent, exist_ok=True)
        total_frames = int(duration_sec * self.fps)

        # Pass 1: Render video only to MKV (immune to missing moov atoms if piped)
        ffmpeg_cmd_video = [
            "ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-vcodec", "png", "-r", str(self.fps),
            "-i", "-",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
            "-frames:v", str(total_frames),
            str(temp_video_mkv)
        ]

        print(f"[{scene_id}] Pass 1: Launching FFmpeg and Playwright ({total_frames} frames @ {self.fps} FPS)...")
        # We don't pipe stderr to avoid blocking if the buffer fills up since we use communicate at the very end
        ffmpeg_proc = subprocess.Popen(ffmpeg_cmd_video, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=None)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1080, "height": 1920})
            page.goto(f"file://{temp_html_path.absolute()}")
            page.wait_for_load_state("networkidle")

            try:
                for frame in range(total_frames):
                    page.evaluate(f"window.seekToFrame({frame}, {self.fps})")
                    try:
                        png_bytes = page.screenshot(type="png", omit_background=False)
                        if ffmpeg_proc.poll() is not None:
                            break
                        ffmpeg_proc.stdin.write(png_bytes)
                        # Remove flush, or ignore flush error
                        try:
                            ffmpeg_proc.stdin.flush()
                        except Exception:
                            pass
                    except BrokenPipeError:
                        break
                    except Exception as e:
                        if "closed file" in str(e):
                            break
                        print(f"Failed to stream frame {frame}: {e}")
                        break

                    if frame % 30 == 0:
                        print(f"[{scene_id}] Progress: {round((frame/total_frames)*100, 1)}%", end="\r")
            finally:
                browser.close()
                if temp_html_path.exists(): os.remove(temp_html_path)

        try:
            ffmpeg_proc.stdin.close()
        except Exception:
            pass

        ffmpeg_proc.communicate()
        if ffmpeg_proc.returncode != 0:
            print(f"FFmpeg Pass 1 failed with return code {ffmpeg_proc.returncode}")

        # Pass 2: Mux Audio into MP4
        print(f"\n[{scene_id}] Pass 2: Muxing Audio...")

        ffmpeg_cmd_mux = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(temp_video_mkv),
            "-i", str(audio_path),
            "-i", str(sfx_path),
            "-t", str(duration_sec), "-f", "lavfi", "-i", "anoisesrc=c=pink:r=48000:a=0.015",
            "-t", str(duration_sec), "-f", "lavfi", "-i", "aevalsrc='0.02*sin(2*PI*50*t):s=48000'",
            "-t", str(duration_sec), "-f", "lavfi", "-i", "aevalsrc='0.1*sin(2*PI*110*t)+0.05*sin(2*PI*220*t):s=48000',chorus=0.7:0.9:55:0.4:0.25:2"
        ]

        if self.bgm_path and os.path.exists(self.bgm_path):
            ffmpeg_cmd_mux.extend(["-stream_loop", "-1", "-i", self.bgm_path])
            ffmpeg_cmd_mux.extend([
                "-filter_complex",
                "[1:a]asplit=2[narr_mix][narr_sc];"
                "[6:a]volume=0.3[bgm_vol];"
                "[bgm_vol][narr_sc]sidechaincompress=threshold=0.015:ratio=4:attack=5:release=50[bgm_ducked];"
                "[narr_mix][2:a][3:a][4:a][5:a][bgm_ducked]amix=inputs=6:duration=first:dropout_transition=2:weights=1.0 0.8 0.5 0.5 0.3 1.0[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_mp4)
            ])
        else:
            ffmpeg_cmd_mux.extend([
                "-filter_complex", "[1:a][2:a][3:a][4:a][5:a]amix=inputs=5:duration=first:dropout_transition=2:weights=1.0 0.8 0.5 0.5 0.3[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_mp4)
            ])

        subprocess.run(ffmpeg_cmd_mux, stdout=subprocess.DEVNULL, stderr=None)
        if temp_video_mkv.exists(): os.remove(temp_video_mkv)

        print(f"[{scene_id}] Render complete -> {output_mp4}")