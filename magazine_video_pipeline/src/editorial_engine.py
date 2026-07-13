import os
import json
import logging
from pathlib import Path
from llama_cpp import Llama, LlamaGrammar

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class EditorialEngine:
    def __init__(self, model_path: str, workspace_dir="data/workspace", schemas_dir="schemas"):
        self.workspace_dir = Path(workspace_dir)
        self.schemas_dir = Path(schemas_dir)

        if model_path == "dummy":
            # Allow tests to mock the model
            self.llm = "dummy"
        elif not os.path.exists(model_path):
            logger.warning(f"Model path {model_path} does not exist. Initializing without model.")
            self.llm = None
        else:
            try:
                # Initialize Llama model. Adjusted n_ctx based on typical needs for this context size.
                self.llm = Llama(model_path=model_path, n_ctx=4096, verbose=False)
            except Exception as e:
                logger.error(f"Failed to initialize Llama model: {e}")
                self.llm = None

    def _load_schema(self, schema_filename: str):
        schema_path = self.schemas_dir / schema_filename
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _generate_json(self, prompt: str, schema: dict) -> dict:
        if not self.llm:
            raise ValueError("Llama model is not initialized.")

        grammar = LlamaGrammar.from_json_schema(json.dumps(schema))

        response = self.llm(
            prompt,
            max_tokens=2048,
            grammar=grammar,
            temperature=0.7
        )

        text_output = response["choices"][0]["text"].strip()
        try:
            return json.loads(text_output)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output: {e}\nOutput was: {text_output}")
            raise

    def process_all_workspaces(self):
        if not self.workspace_dir.exists():
            logger.warning(f"Workspace directory {self.workspace_dir} does not exist.")
            return

        for workspace in self.workspace_dir.iterdir():
            if workspace.is_dir():
                self.process_workspace(workspace)

    def process_workspace(self, workspace_path: Path):
        logger.info(f"Processing editorial for workspace: {workspace_path}")
        try:
            # 1. Topic Detector
            topic_eval_path = workspace_path / "02_topic_evaluation.json"
            if not topic_eval_path.exists():
                self.run_topic_detector(workspace_path)

            # 2. Story Selector
            storyboard_path = workspace_path / "03_storyboard.json"
            if not storyboard_path.exists():
                self.run_story_selector(workspace_path)

            # 3. Visual Planner
            render_manifest_path = workspace_path / "05_render_manifest.json"
            if not render_manifest_path.exists():
                self.run_visual_planner(workspace_path)
        except Exception as e:
            logger.error(f"Error processing workspace {workspace_path}: {e}")

    def run_topic_detector(self, workspace_path: Path):
        logger.info("Running Topic Detector Agent...")
        input_file = workspace_path / "01_layout_ocr.json"
        if not input_file.exists():
            logger.warning(f"Input file {input_file} not found. Skipping Topic Detector.")
            return

        with open(input_file, "r", encoding="utf-8") as f:
            layout_data = json.load(f)

        prompt = f"""You are an expert editorial topic detector for a vintage magazine video pipeline.
Analyze the following OCR layout data from a vintage magazine page and identify the most compelling high-value story.
Score it based on novelty, historical value, humor, controversy, surprise, and visual quality.

OCR Layout Data:
{json.dumps(layout_data, indent=2)}

Provide the evaluation in strict JSON format according to the requested schema.
"""
        schema = self._load_schema("topic_evaluation.schema.json")
        result = self._generate_json(prompt, schema)

        output_file = workspace_path / "02_topic_evaluation.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Saved {output_file}")

    def run_story_selector(self, workspace_path: Path):
        logger.info("Running Story Selector Agent...")
        input_file = workspace_path / "02_topic_evaluation.json"
        if not input_file.exists():
            logger.warning(f"Input file {input_file} not found. Skipping Story Selector.")
            return

        with open(input_file, "r", encoding="utf-8") as f:
            topic_data = json.load(f)

        prompt = f"""You are an expert story selector and scriptwriter.
Based on the following topic evaluation from a vintage magazine article, generate a compelling short-form video script.
Provide exactly 3 distinct hooks and between 2 and 5 body scenes.

Topic Evaluation:
{json.dumps(topic_data, indent=2)}

Provide the storyboard in strict JSON format according to the requested schema.
"""
        schema = self._load_schema("storyboard.schema.json")
        result = self._generate_json(prompt, schema)

        output_file = workspace_path / "03_storyboard.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Saved {output_file}")

    def run_visual_planner(self, workspace_path: Path):
        logger.info("Running Visual Planner Agent...")
        input_file = workspace_path / "03_storyboard.json"
        if not input_file.exists():
            logger.warning(f"Input file {input_file} not found. Skipping Visual Planner.")
            return

        with open(input_file, "r", encoding="utf-8") as f:
            storyboard_data = json.load(f)

        prompt = f"""You are an expert visual planner and video editor.
Translate the following storyboard narratives into visual parameters (crop percentages, components, transitions, foley triggers) for rendering.
Assign a specific visual style and transition settings to match the mood of the scenes.

Storyboard Narrative:
{json.dumps(storyboard_data, indent=2)}

Provide the render manifest in strict JSON format according to the requested schema.
"""
        schema = self._load_schema("render_manifest.schema.json")
        result = self._generate_json(prompt, schema)

        output_file = workspace_path / "05_render_manifest.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Saved {output_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Editorial Engine for Magazine Video Pipeline")

    base_dir = Path(__file__).parent.parent
    default_workspace = base_dir / "data" / "workspace"
    default_schemas = base_dir / "schemas"

    parser.add_argument("--model_path", type=str, required=True, help="Path to the local LLM model (e.g., Gemma 4 12B GGUF)")
    parser.add_argument("--workspace_dir", type=str, default=str(default_workspace), help="Directory for workspaces")
    parser.add_argument("--schemas_dir", type=str, default=str(default_schemas), help="Directory for JSON schemas")

    args = parser.parse_args()

    engine = EditorialEngine(
        model_path=args.model_path,
        workspace_dir=args.workspace_dir,
        schemas_dir=args.schemas_dir
    )
    engine.process_all_workspaces()
