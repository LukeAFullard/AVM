import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import http.server
import socketserver
import os

def render_preview():
    base_dir = Path("/app/magazine_video_pipeline")
    template_dir = base_dir / "templates"

    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("template.html.j2")

    bbox = [100, 200, 800, 1000]
    image_path = base_dir / "data" / "workspace" / "time_1986_page_36" / "00_source_page.png"

    timestamps_path = base_dir / "data" / "workspace" / "time_1986_page_36" / "04_audio_payload" / "timestamps_hook_a.json"
    if timestamps_path.exists():
        with open(timestamps_path) as f:
            timestamps = json.load(f)
    else:
        timestamps = [
            {"word": "Interactive", "start": 0.5, "end": 1.0},
            {"word": "Preview", "start": 1.1, "end": 1.6},
        ]

    html_content = template.render(
        bbox=bbox,
        image_path="data/workspace/time_1986_page_36/00_source_page.png",
        timestamps=timestamps
    )

    html_file = base_dir / "_temp_preview.html"
    with open(html_file, "w") as f:
        f.write(html_content)

def start_server():
    os.chdir("/app/magazine_video_pipeline")
    PORT = 8000
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving at port {PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    render_preview()
    start_server()
