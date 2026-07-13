import sys
import os

# Add src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from render_engine import PlaywrightRenderEngine

# Ensure Playwright browser is available
engine = PlaywrightRenderEngine(project_dir="data/workspace/time_1986_page_36", fps=30)
engine.render_scene_to_mp4(scene_id="hook_a", duration_sec=2.0)
