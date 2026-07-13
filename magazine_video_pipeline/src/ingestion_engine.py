import os
import json
import logging
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class IngestionEngine:
    def __init__(self, raw_pdfs_dir="data/raw_pdfs", workspace_dir="data/workspace"):
        self.raw_pdfs_dir = Path(raw_pdfs_dir)
        self.workspace_dir = Path(workspace_dir)

    def process_all(self):
        if not self.raw_pdfs_dir.exists():
            logger.warning(f"Directory {self.raw_pdfs_dir} does not exist.")
            return

        pdf_files = list(self.raw_pdfs_dir.glob("*.pdf"))
        if not pdf_files:
            logger.warning(f"No PDFs found in {self.raw_pdfs_dir}.")
            return

        for pdf_file in pdf_files:
            self.process_pdf(pdf_file)

    def process_pdf(self, pdf_path: Path):
        logger.info(f"Processing PDF: {pdf_path}")
        pdf_name = pdf_path.stem

        try:
            # Convert PDF to images
            images = convert_from_path(pdf_path)

            for i, image in enumerate(images):
                page_num = i + 1
                workspace_name = f"{pdf_name}_page_{page_num}"
                page_workspace = self.workspace_dir / workspace_name
                page_workspace.mkdir(parents=True, exist_ok=True)

                # Save 00_source_page.png
                image_path = page_workspace / "00_source_page.png"
                image.save(image_path, "PNG")
                logger.info(f"Saved {image_path}")

                # Perform OCR
                self._perform_ocr(image, page_workspace)
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {e}")

    def _perform_ocr(self, image: Image.Image, workspace_path: Path):
        width, height = image.size

        # Tesseract output format: dictionary with word-level or block-level boxes
        try:
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        except Exception as e:
            logger.error(f"Error during OCR: {e}")
            return

        # We group words by block_num
        blocks_dict = {}
        n_boxes = len(ocr_data['level'])

        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])

            if conf < 0:
                continue

            block_num = ocr_data['block_num'][i]

            if block_num not in blocks_dict:
                blocks_dict[block_num] = {
                    'text': [],
                    'left': ocr_data['left'][i],
                    'top': ocr_data['top'][i],
                    'right': ocr_data['left'][i] + ocr_data['width'][i],
                    'bottom': ocr_data['top'][i] + ocr_data['height'][i]
                }
            else:
                blocks_dict[block_num]['left'] = min(blocks_dict[block_num]['left'], ocr_data['left'][i])
                blocks_dict[block_num]['top'] = min(blocks_dict[block_num]['top'], ocr_data['top'][i])
                blocks_dict[block_num]['right'] = max(blocks_dict[block_num]['right'], ocr_data['left'][i] + ocr_data['width'][i])
                blocks_dict[block_num]['bottom'] = max(blocks_dict[block_num]['bottom'], ocr_data['top'][i] + ocr_data['height'][i])

            if text:
                blocks_dict[block_num]['text'].append(text)

        output_blocks = []
        for b_num, b_data in blocks_dict.items():
            combined_text = " ".join(b_data['text']).strip()
            if not combined_text:
                continue

            b_width = b_data['right'] - b_data['left']
            b_height = b_data['bottom'] - b_data['top']

            normalized_box = {
                "x": b_data['left'] / width,
                "y": b_data['top'] / height,
                "width": b_width / width,
                "height": b_height / height
            }

            output_blocks.append({
                "text": combined_text,
                "box": normalized_box
            })

        output_data = {
            "page_dimensions": {
                "width": width,
                "height": height
            },
            "blocks": output_blocks
        }

        json_path = workspace_path / "01_layout_ocr.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Saved {json_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingestion Engine for PDF processing.")

    # Determine the absolute paths based on this script's location
    base_dir = Path(__file__).parent.parent
    default_raw = base_dir / "data" / "raw_pdfs"
    default_workspace = base_dir / "data" / "workspace"

    parser.add_argument("--raw_dir", type=str, default=str(default_raw), help="Directory containing raw PDFs")
    parser.add_argument("--workspace_dir", type=str, default=str(default_workspace), help="Directory for output workspaces")
    args = parser.parse_args()

    engine = IngestionEngine(raw_pdfs_dir=args.raw_dir, workspace_dir=args.workspace_dir)
    engine.process_all()
