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

        if self.llm == "dummy":
            # Generate dummy output for testing based on expected structures
            schema_title = schema.get("title", "")
            if schema_title == "TopicEvaluationResult":
                return {
                    "article_id": "dummy_1",
                    "headline": "Dummy Headline",
                    "summary": "Dummy Summary",
                    "target_block_ids": ["b1"],
                    "scores": {
                        "novelty": 5, "historical_value": 5, "humor": 5, "controversy": 5, "surprise": 5, "visual_quality": 5, "overall_estimate": 5.0
                    }
                }
            elif schema_title == "StorySelectorBlueprint":
                return {
                    "project_id": "dummy_p1",
                    "selected_article_id": "dummy_1",
                    "hooks": [
                        {"hook_id": "hook_a", "variant_type": "retro_absurdity", "spoken_narration": "A dummy hook.", "estimated_duration": 2.0},
                        {"hook_id": "hook_b", "variant_type": "historical_irony", "spoken_narration": "Another hook.", "estimated_duration": 3.0},
                        {"hook_id": "hook_c", "variant_type": "modern_parallel", "spoken_narration": "A third hook.", "estimated_duration": 4.0}
                    ],
                    "body_scenes": [
                        {"scene_id": "s1", "chronological_order": 1, "spoken_narration": "Dummy body scene narration.", "estimated_duration": 5.0, "narrative_purpose": "context_setup"},
                        {"scene_id": "s2", "chronological_order": 2, "spoken_narration": "Second dummy body scene.", "estimated_duration": 6.0, "narrative_purpose": "escalation"},
                        {"scene_id": "s3", "chronological_order": 3, "spoken_narration": "And today, it is still remembered.", "estimated_duration": 4.0, "narrative_purpose": "aftermath"}
                    ]
                }
            elif schema_title == "VisualRenderManifest":
                return {
                    "project_id": "dummy_p1",
                    "global_style": {
                        "color_palette": "vintage", "caption_style": "bold", "background_texture": "grain",
                        "font_family": "Oswald", "primary_color": "#00FF00", "secondary_color": "#FF00FF", "animation_easing": "quad"
                    },
                    "scene_manifests": [
                        {
                            "scene_ref_id": "hook_a", "template_component": "headline_zoom",
                            "visual_source": {"source_type": "magazine_scan", "target_page_number": 1, "crop_bbox_pct": [10.0, 10.0, 50.0, 50.0], "broll_search_query": ""},
                            "transition_in": "fade", "foley_trigger": "none"
                        },
                        {
                            "scene_ref_id": "s1", "template_component": "column_drift",
                            "visual_source": {"source_type": "magazine_scan", "target_page_number": 1, "crop_bbox_pct": [20.0, 20.0, 80.0, 80.0], "broll_search_query": ""},
                            "transition_in": "cut", "foley_trigger": "none"
                        },
                        {
                            "scene_ref_id": "s3", "template_component": "headline_zoom",
                            "visual_source": {"source_type": "external_broll", "target_page_number": 1, "crop_bbox_pct": [10.0, 10.0, 90.0, 90.0], "broll_search_query": "vintage train"},
                            "transition_in": "fade", "foley_trigger": "none"
                        }
                    ]
                }
            else:
                return {}

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

    def process_workspace(self, workspace_path: Path, story_feedback: str = None, visual_feedback: str = None):
        logger.info(f"Processing editorial for workspace: {workspace_path}")
        try:
            # 1. Topic Detector
            topic_eval_path = workspace_path / "02_topic_evaluation.json"
            if not topic_eval_path.exists():
                self.run_topic_detector(workspace_path)

            # 2. Story Selector
            storyboard_path = workspace_path / "03_storyboard.json"
            if not storyboard_path.exists() or story_feedback:
                self.run_story_selector(workspace_path, feedback=story_feedback)

            # 3. Visual Planner
            render_manifest_path = workspace_path / "05_render_manifest.json"
            if not render_manifest_path.exists() or visual_feedback:
                self.run_visual_planner(workspace_path, feedback=visual_feedback)
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
You must also extract a list of 'key_entities' (names of important people, organizations, or places) and 'key_quotes' (exact interesting phrases or quotes).

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

    def run_story_selector(self, workspace_path: Path, feedback: str = None):
        logger.info("Running Story Selector Agent...")
        input_file = workspace_path / "02_topic_evaluation.json"
        if not input_file.exists():
            logger.warning(f"Input file {input_file} not found. Skipping Story Selector.")
            return

        with open(input_file, "r", encoding="utf-8") as f:
            topic_data = json.load(f)

        prompt = f"""You are an expert story selector and scriptwriter.
Based on the following topic evaluation from a vintage magazine article, generate a compelling short-form video script.

CRITICAL TIKTOK HOOK FRAMEWORK:
The first 3 seconds (hooks) must be hyper-engaging to maximize retention. Use techniques such as:
1. Negative Hooks (e.g., "Stop doing X", "The dark truth about Y").
2. Open Loops (e.g., "This one secret changed everything...").
3. Controversial or Absurd Statements (e.g., "Why everyone in the 1950s was wrong about Z").
The spoken narration for each hook MUST be punchy, curiosity-inducing, and under 15 words.

Provide exactly 3 distinct hooks and between 2 and 5 body scenes.
You must include an 'aftermath' scene at the end that acts as a conclusion, explicitly addressing "Where are they now?" or "What happened next?" to link the past historical events to the present day.
Use the extracted 'key_entities' and 'key_quotes' to drive the script. For body scenes involving a specific entity (like a person), you should specify a 'key_entity_focus' and a 'visual_focus_keyword' to guide the visual editor.

Topic Evaluation:
{json.dumps(topic_data, indent=2)}
"""
        if feedback:
            prompt += f"\nPrevious attempt failed quality gates. Please fix the following issue:\n{feedback}\n"

        prompt += "\nProvide the storyboard in strict JSON format according to the requested schema.\n"

        schema = self._load_schema("storyboard.schema.json")
        result = self._generate_json(prompt, schema)

        output_file = workspace_path / "03_storyboard.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Saved {output_file}")

    def run_visual_planner(self, workspace_path: Path, feedback: str = None):
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
For the final 'aftermath' or modern-day parallel scenes, you must set the visual source type to 'external_broll' and provide a highly descriptive, cinematic 'broll_search_query' (e.g., "frantic 1920s wall street trading floor" instead of "money") so the pipeline can fetch a relevant, emotionally resonant stock video or image.

Additionally, for any scene that has a 'key_entity_focus', you should strongly consider using 'external_broll' to find a relevant image of that person or place, using that entity in a highly specific 'broll_search_query'. The B-roll query must be professional and visually engaging.
You must also provide an array of 'highlight_words' (e.g. ['money', 'danger', 'secret']) that appear in the spoken narration to be semantically highlighted in the video captions for increased engagement.

Storyboard Narrative:
{json.dumps(storyboard_data, indent=2)}
"""
        if feedback:
            prompt += f"\nPrevious attempt failed quality gates. Please fix the following issue:\n{feedback}\n"

        prompt += "\nProvide the render manifest in strict JSON format according to the requested schema.\n"

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
