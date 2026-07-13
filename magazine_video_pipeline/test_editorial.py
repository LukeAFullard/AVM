import json
import logging
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

# Import the class we want to test
from src.editorial_engine import EditorialEngine

logging.basicConfig(level=logging.INFO)

class TestEditorialEngine(unittest.TestCase):
    def setUp(self):
        self.workspace_dir = Path("data/workspace")
        self.test_workspace = self.workspace_dir / "test_page_1"
        self.schemas_dir = Path("schemas")

    @patch("src.editorial_engine.LlamaGrammar.from_json_schema")
    @patch("src.editorial_engine.Llama")
    def test_full_pipeline(self, MockLlama, MockGrammar):
        MockGrammar.return_value = MagicMock()
        # We need to mock the Llama call. It returns a dictionary.
        # We can make it return different JSONs depending on the call.

        # We need realistic valid outputs based on the schema.
        topic_output = {
            "article_id": "test_1",
            "headline": "Test Headline",
            "summary": "Test Summary",
            "target_block_ids": ["b1"],
            "scores": {
                "novelty": 5, "historical_value": 5, "humor": 5, "controversy": 5, "surprise": 5, "visual_quality": 5, "overall_estimate": 5.0
            }
        }
        storyboard_output = {
            "project_id": "p1",
            "selected_article_id": "test_1",
            "hooks": [
                {"hook_id": "hook_a", "variant_type": "retro_absurdity", "spoken_narration": "A", "estimated_duration": 2.0},
                {"hook_id": "hook_b", "variant_type": "retro_absurdity", "spoken_narration": "B", "estimated_duration": 2.0},
                {"hook_id": "hook_c", "variant_type": "retro_absurdity", "spoken_narration": "C", "estimated_duration": 2.0}
            ],
            "body_scenes": [
                {"scene_id": "s1", "chronological_order": 1, "spoken_narration": "S1", "estimated_duration": 5.0, "narrative_purpose": "context_setup"},
                {"scene_id": "s2", "chronological_order": 2, "spoken_narration": "S2", "estimated_duration": 5.0, "narrative_purpose": "escalation"}
            ]
        }
        manifest_output = {
            "project_id": "p1",
            "global_style": {
                "color_palette": "p", "caption_style": "c", "background_texture": "t"
            },
            "scene_manifests": [
                {
                    "scene_ref_id": "s1", "template_component": "headline_zoom",
                    "visual_source": {"source_type": "magazine_scan", "target_page_number": 1, "crop_bbox_pct": [10.0, 10.0, 50.0, 50.0], "broll_search_query": ""},
                    "transition_in": "fade", "foley_trigger": "none"
                }
            ]
        }

        # We will create a side effect function for the mock call
        call_count = [0]
        def mock_llm_call(*args, **kwargs):
            if call_count[0] == 0:
                ret = topic_output
            elif call_count[0] == 1:
                ret = storyboard_output
            else:
                ret = manifest_output
            call_count[0] += 1
            return {"choices": [{"text": json.dumps(ret)}]}

        mock_instance = MagicMock()
        mock_instance.side_effect = mock_llm_call
        MockLlama.return_value = mock_instance

        engine = EditorialEngine(model_path="dummy", workspace_dir=str(self.workspace_dir), schemas_dir=str(self.schemas_dir))
        engine.llm = mock_instance

        # Process the specific workspace
        engine.process_workspace(self.test_workspace)

        # Check if files were created
        self.assertTrue((self.test_workspace / "02_topic_evaluation.json").exists())
        self.assertTrue((self.test_workspace / "03_storyboard.json").exists())
        self.assertTrue((self.test_workspace / "05_render_manifest.json").exists())

    def tearDown(self):
        # Clean up files created during testing
        if (self.test_workspace / "02_topic_evaluation.json").exists():
            (self.test_workspace / "02_topic_evaluation.json").unlink()
        if (self.test_workspace / "03_storyboard.json").exists():
            (self.test_workspace / "03_storyboard.json").unlink()
        if (self.test_workspace / "05_render_manifest.json").exists():
            (self.test_workspace / "05_render_manifest.json").unlink()

if __name__ == '__main__':
    unittest.main()
