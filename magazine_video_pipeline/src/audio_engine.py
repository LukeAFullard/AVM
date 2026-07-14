import os
import json
import logging
import argparse
import wave
import math
import struct
import urllib.request
import urllib.parse
from pathlib import Path

# Try to import external dependencies, fall back gracefully if missing (for early syntax checks)
try:
    from piper import PiperVoice
    import whisper_timestamped as whisper
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class AudioEngine:
    def __init__(self, voice_model: str, workspace_dir: str = "data/workspace"):
        self.workspace_dir = Path(workspace_dir)
        self.dummy_mode = (voice_model == "dummy")
        self.elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")

        if self.dummy_mode:
            logger.info("Initializing AudioEngine in DUMMY mode.")
            self.voice = None
            self.whisper_model = None
        elif self.elevenlabs_api_key:
            logger.info("Initializing AudioEngine in ELEVENLABS mode.")
            self.voice = None
            if not HAS_DEPS:
                 raise ImportError("Required dependencies (whisper_timestamped) are not installed for alignment.")
            logger.info("Loading Whisper model (tiny) for alignment")
            self.whisper_model = whisper.load_model("tiny", device="cpu")
        else:
            if not HAS_DEPS:
                raise ImportError("Required dependencies (piper, whisper_timestamped) are not installed.")

            if not os.path.exists(voice_model):
                logger.warning(f"Voice model path {voice_model} does not exist. Switching to DUMMY mode.")
                self.dummy_mode = True
                self.voice = None
                self.whisper_model = None
            else:
                logger.info(f"Loading Piper voice model from {voice_model}")
                self.voice = PiperVoice.load(voice_model)
                logger.info("Loading Whisper model (tiny) for alignment")
                self.whisper_model = whisper.load_model("tiny", device="cpu")

    def _generate_dummy_wav(self, output_path: Path, text: str):
        """Generates a 1-second 440Hz sine wave to mock TTS output."""
        sample_rate = 16000
        duration = 1.0
        n_samples = int(sample_rate * duration)

        with wave.open(str(output_path), 'w') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            for i in range(n_samples):
                value = int(32767.0 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
                data = struct.pack('<h', value)
                wav_file.writeframesraw(data)
        logger.debug(f"Generated dummy WAV at {output_path}")

    def _generate_dummy_timestamps(self, output_path: Path, text: str):
        """Generates mock timestamps for the given text."""
        words = text.split()
        word_data = []

        current_time = 0.0
        for word in words:
            word_data.append({
                "text": word,
                "start": current_time,
                "end": current_time + 0.4,
                "confidence": 0.99
            })
            current_time += 0.4

        data = {
            "text": text,
            "segments": [
                {
                    "start": 0.0,
                    "end": current_time,
                    "text": text,
                    "words": word_data
                }
            ]
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Generated dummy timestamps at {output_path}")

    def process_all_workspaces(self):
        if not self.workspace_dir.exists():
            logger.warning(f"Workspace directory {self.workspace_dir} does not exist.")
            return

        for workspace in self.workspace_dir.iterdir():
            if workspace.is_dir():
                self.process_workspace(workspace)

    def process_workspace(self, workspace_path: Path):
        logger.info(f"Processing audio for workspace: {workspace_path}")
        storyboard_path = workspace_path / "03_storyboard.json"

        if not storyboard_path.exists():
            logger.warning(f"Storyboard file {storyboard_path} not found. Skipping audio generation.")
            return

        audio_dir = workspace_path / "04_audio_payload"
        audio_dir.mkdir(parents=True, exist_ok=True)

        with open(storyboard_path, "r", encoding="utf-8") as f:
            try:
                storyboard = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse storyboard JSON at {storyboard_path}: {e}")
                return

        # Parse hooks
        hooks = storyboard.get("hooks", [])
        for hook in hooks:
            hook_id = hook.get("hook_id")
            narration = hook.get("spoken_narration")
            if hook_id and narration:
                self.process_narration(audio_dir, hook_id, narration)

        # Parse body scenes
        body_scenes = storyboard.get("body_scenes", [])
        for scene in body_scenes:
            scene_id = scene.get("scene_id")
            narration = scene.get("spoken_narration")
            if scene_id and narration:
                self.process_narration(audio_dir, scene_id, narration)

    def process_narration(self, audio_dir: Path, block_id: str, text: str):
        wav_path = audio_dir / f"narration_{block_id}.wav"
        json_path = audio_dir / f"timestamps_{block_id}.json"

        if wav_path.exists() and json_path.exists():
            logger.debug(f"Audio payload for {block_id} already exists. Skipping.")
            return

        logger.info(f"Generating audio payload for {block_id}")

        if self.dummy_mode:
            self._generate_dummy_wav(wav_path, text)
            self._generate_dummy_timestamps(json_path, text)
        else:
            try:
                if self.elevenlabs_api_key:
                    logger.info(f"Synthesizing speech for {block_id} using ElevenLabs")
                    voice_id = "21m00Tcm4TlvDq8ikWAM" # Rachel
                    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                    headers = {
                        "Accept": "audio/mpeg",
                        "Content-Type": "application/json",
                        "xi-api-key": self.elevenlabs_api_key
                    }
                    data = {
                        "text": text,
                        "model_id": "eleven_monolingual_v1",
                        "voice_settings": {
                            "stability": 0.5,
                            "similarity_boost": 0.5
                        }
                    }

                    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_16000_16_mono"
                    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
                    with urllib.request.urlopen(req) as response:
                        pcm_data = response.read()

                        with wave.open(str(wav_path), 'wb') as wav_file:
                            wav_file.setnchannels(1)
                            wav_file.setsampwidth(2)
                            wav_file.setframerate(16000)
                            wav_file.writeframes(pcm_data)

                else:
                    # Generate TTS
                    logger.info(f"Synthesizing speech for {block_id}")
                    with wave.open(str(wav_path), 'w') as wav_file:
                        self.voice.synthesize(text, wav_file)

                # Extract timestamps using whisper-timestamped
                logger.info(f"Extracting timestamps for {block_id}")
                audio = whisper.load_audio(str(wav_path))
                result = whisper.transcribe(self.whisper_model, audio, language="en")

                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)

            except Exception as e:
                logger.error(f"Failed to generate audio payload for {block_id}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio Synthesis & Timing Engine")

    base_dir = Path(__file__).parent.parent
    default_workspace = base_dir / "data" / "workspace"

    parser.add_argument("--voice_model", type=str, required=True, help="Path to Piper voice model (.onnx), or 'dummy'")
    parser.add_argument("--workspace_dir", type=str, default=str(default_workspace), help="Workspace directory")

    args = parser.parse_args()

    engine = AudioEngine(voice_model=args.voice_model, workspace_dir=args.workspace_dir)
    engine.process_all_workspaces()
