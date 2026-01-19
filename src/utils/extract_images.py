"""Extract labeled figures from PDF files using a class-based approach."""

from __future__ import annotations

import io
import os
import re
import warnings
from typing import TYPE_CHECKING

from loguru import logger
from PIL import Image

if TYPE_CHECKING:
    import fitz as fitz_module


class FigureExtractor:
    """Extract labeled figures from PDF files.

    Uses a caption-based approach that works for both raster images and vector graphics:
    1. Find all figure captions on each page
    2. For each caption, determine the figure region (typically above the caption)
    3. Render that region to capture the figure regardless of its internal format
    """

    # Configuration constants
    MAX_PAGES: int = 20
    MAX_IMAGES: int = 15
    MIN_IMAGE_SIZE: int = 10

    def __init__(self, pdf_path: str, output_folder: str = "images") -> None:
        """Initialize the figure extractor.

        Args:
            pdf_path: Path to the input PDF file.
            output_folder: Folder to save extracted images.
        """
        self.pdf_path = pdf_path
        self.output_folder = output_folder
        self._fitz: fitz_module | None = None

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    def extract(self) -> int:
        """Extract labeled figures from the PDF file.

        Returns:
            int: Number of figures extracted.
        """
        fitz = self._get_fitz()
        doc = fitz.open(self.pdf_path)
        os.makedirs(self.output_folder, exist_ok=True)

        extracted_count = 0
        extracted_figure_ids: set[str] = set()
        caption_position = self._detect_caption_position(doc)

        for page_index, page in enumerate(doc, start=1):
            if page_index > self.MAX_PAGES or extracted_count >= self.MAX_IMAGES:
                break

            extracted_count += self._process_page(
                page,
                page_index,
                caption_position,
                extracted_figure_ids,
                extracted_count,
            )

        doc.close()
        logger.info(f"Extracted {extracted_count} figures from '{self.pdf_path}'")
        return extracted_count

    # -------------------------------------------------------------------------
    # PDF/Fitz utilities
    # -------------------------------------------------------------------------

    def _get_fitz(self) -> fitz_module:
        """Import PyMuPDF with warnings filtered.

        Returns:
            fitz_module: The imported PyMuPDF module.
        """
        if self._fitz is not None:
            return self._fitz

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="builtin type SwigPyPacked has no __module__ attribute",
                category=DeprecationWarning,
            )
            warnings.filterwarnings(
                "ignore",
                message="builtin type SwigPyObject has no __module__ attribute",
                category=DeprecationWarning,
            )
            warnings.filterwarnings(
                "ignore",
                message="builtin type swigvarlink has no __module__ attribute",
                category=DeprecationWarning,
            )
            import fitz  # noqa: PLC0415

        self._fitz = fitz
        return fitz

    def _is_image_too_small(self, blk: dict) -> bool:
        """Check if an image block is too small to be a significant figure.

        Args:
            blk: Block object containing bbox coordinates.

        Returns:
            True if image is too small (should be skipped), False otherwise.
        """
        blk_width = blk["bbox"][2] - blk["bbox"][0]
        blk_height = blk["bbox"][3] - blk["bbox"][1]
        return blk_width <= self.MIN_IMAGE_SIZE or blk_height <= self.MIN_IMAGE_SIZE

    def _collect_image_bboxes(self, page, blocks: list[dict]) -> list[tuple]:
        """Collect image bounding boxes from page blocks and xrefs.

        Args:
            page: PyMuPDF page object.
            blocks: List of page blocks.

        Returns:
            List of deduplicated image bounding boxes.
        """
        image_bboxes: list[tuple] = []

        # From text dict blocks (type 1 = image)
        for blk in blocks:
            if blk.get("type") == 1 and "bbox" in blk:
                bbox = tuple(blk["bbox"])
                if not self._is_image_too_small(blk):
                    image_bboxes.append(bbox)

        # From image xrefs (handles vector / reused images)
        try:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                for rect in page.get_image_rects(xref):
                    bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                    if self._bbox_area(bbox) > self.MIN_IMAGE_SIZE * self.MIN_IMAGE_SIZE:
                        image_bboxes.append(bbox)
        except Exception as exp:
            logger.debug(f"Failed to collect image bboxes: {exp}")

        return self._dedupe_bboxes(image_bboxes)

    # -------------------------------------------------------------------------
    # Bounding box geometry helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _bbox_area(bbox: tuple) -> float:
        """Compute the area of a bounding box.

        Args:
            bbox: Bounding box (x0, y0, x1, y1).

        Returns:
            Area of the bounding box.
        """
        width = max(0, bbox[2] - bbox[0])
        height = max(0, bbox[3] - bbox[1])
        return width * height

    @staticmethod
    def _bbox_center_x(bbox: tuple) -> float:
        """Get horizontal center of a bounding box.

        Args:
            bbox: Bounding box (x0, y0, x1, y1).

        Returns:
            X-coordinate of the center.
        """
        return (bbox[0] + bbox[2]) / 2

    @staticmethod
    def _bbox_center_y(bbox: tuple) -> float:
        """Get vertical center of a bounding box.

        Args:
            bbox: Bounding box (x0, y0, x1, y1).

        Returns:
            Y-coordinate of the center.
        """
        return (bbox[1] + bbox[3]) / 2

    @staticmethod
    def _vertical_distance(bbox1: tuple, bbox2: tuple) -> float:
        """Calculate the vertical distance between two bounding boxes.

        Args:
            bbox1: First bounding box (x0, y0, x1, y1).
            bbox2: Second bounding box (x0, y0, x1, y1).

        Returns:
            Vertical distance (0 if overlapping vertically).
        """
        top1, bottom1 = bbox1[1], bbox1[3]
        top2, bottom2 = bbox2[1], bbox2[3]

        # Check if they overlap vertically
        if bottom1 >= top2 and bottom2 >= top1:
            return 0

        # Return distance between closest edges
        if bottom1 < top2:
            return top2 - bottom1
        return top1 - bottom2

    @staticmethod
    def _horizontal_overlap(bbox1: tuple, bbox2: tuple) -> float:
        """Calculate the horizontal overlap ratio between two bounding boxes.

        Args:
            bbox1: First bounding box (x0, y0, x1, y1).
            bbox2: Second bounding box (x0, y0, x1, y1).

        Returns:
            Overlap ratio (0 to 1) relative to the smaller width.
        """
        left1, right1 = bbox1[0], bbox1[2]
        left2, right2 = bbox2[0], bbox2[2]

        overlap_left = max(left1, left2)
        overlap_right = min(right1, right2)
        overlap = max(0, overlap_right - overlap_left)

        width1 = right1 - left1
        width2 = right2 - left2
        min_width = min(width1, width2)

        if min_width <= 0:
            return 0
        return overlap / min_width

    @staticmethod
    def _merge_bboxes(bbox1: tuple, bbox2: tuple, padding: int = 10) -> tuple:
        """Merge two bounding boxes into one that encompasses both, with padding.

        Args:
            bbox1: First bounding box (x0, y0, x1, y1).
            bbox2: Second bounding box (x0, y0, x1, y1).
            padding: Padding to add around the merged box.

        Returns:
            Merged bounding box with padding.
        """
        return (
            min(bbox1[0], bbox2[0]) - padding,
            min(bbox1[1], bbox2[1]) - padding,
            max(bbox1[2], bbox2[2]) + padding,
            max(bbox1[3], bbox2[3]) + padding,
        )

    @staticmethod
    def _clamp_bbox(bbox: tuple, page_rect: tuple) -> tuple:
        """Clamp a bounding box to page bounds.

        Args:
            bbox: Bounding box to clamp (x0, y0, x1, y1).
            page_rect: Page rectangle (x0, y0, x1, y1).

        Returns:
            Clamped bounding box.
        """
        return (
            max(page_rect[0], bbox[0]),
            max(page_rect[1], bbox[1]),
            min(page_rect[2], bbox[2]),
            min(page_rect[3], bbox[3]),
        )

    @staticmethod
    def _dedupe_bboxes(bboxes: list[tuple], precision: int = 1) -> list[tuple]:
        """Deduplicate bounding boxes by rounding coordinates.

        Args:
            bboxes: List of bounding boxes.
            precision: Decimal precision for rounding.

        Returns:
            List of unique bounding boxes.
        """
        seen: set[tuple] = set()
        unique: list[tuple] = []
        for bbox in bboxes:
            key = tuple(round(coord, precision) for coord in bbox)
            if key in seen:
                continue
            seen.add(key)
            unique.append(bbox)
        return unique

    # -------------------------------------------------------------------------
    # Text and caption parsing
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_block_text(block: dict) -> str:
        """Extract all text from a text block.

        Args:
            block: Page block with type 0 (text).

        Returns:
            The concatenated text from all spans in the block.
        """
        if "lines" not in block:
            return ""
        text = " ".join(span["text"] for line in block["lines"] for span in line["spans"]).strip()
        # Normalize whitespace
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _is_figure_caption(text: str) -> bool:
        """Check if text is a figure caption (not a reference to a figure).

        Distinguishes between:
        - Captions: "Figure 6 Geometry of STEM embeddings. (a) Distribution..."
        - References: "Figure 6a shows that STEM embeddings exhibit..."

        Args:
            text: Text to check.

        Returns:
            True if text appears to be an actual figure caption.
        """
        # Must start with Figure/Fig pattern
        pattern = r"^(Figure|Fig\.?|FIGURE|FIG\.?)\s*(\d+[a-zA-Z]?)"
        match = re.match(pattern, text, re.IGNORECASE)
        if not match:
            return False

        # Get text after the figure reference
        after_ref = text[match.end() :].strip()

        # Reject if followed by verbs that indicate a reference, not a caption
        reference_verbs = (
            r"^(shows?|demonstrates?|illustrates?|presents?|depicts?|displays?|"
            r"contains?|provides?|gives?|describes?|summarizes?|compares?|"
            r"plots?|reports?|indicates?|confirms?|reveals?|highlights?|"
            r"is\s+a\s|is\s+an\s|is\s+the\s|are\s|was\s|were\s|has\s|have\s|"
            r"can\s+be\s|should\s+be\s|also\s)"
        )
        if re.match(reference_verbs, after_ref, re.IGNORECASE):
            return False

        # Captions typically have specific patterns after the figure number
        if after_ref:
            caption_start = r"^([A-Z\(\[]|[:.]\s*[A-Za-z\(])"
            if re.match(caption_start, after_ref):
                return True
            return False

        # Empty after_ref means just "Figure X" which is unusual but accept it
        return True

    @staticmethod
    def _extract_figure_id(text: str) -> str:
        """Extract the figure identifier from caption text.

        Handles formats like: Figure 1, Fig. 2, Fig 3a, Figure 10b, etc.

        Args:
            text: Caption text.

        Returns:
            The figure identifier (e.g., "1", "2a", "10b") or empty string if not found.
        """
        match = re.search(
            r"(?:Figure|Fig\.?|FIGURE|FIG\.?)\s*(\d+[a-zA-Z]?)",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
        return ""

    # -------------------------------------------------------------------------
    # Figure region detection
    # -------------------------------------------------------------------------

    def _find_closest_image(
        self,
        caption_bbox: tuple,
        image_blocks: list[tuple],
        max_vertical_distance: float = 200,
        min_horizontal_overlap: float = 0.3,
    ) -> tuple | None:
        """Find the image block closest to a caption.

        Searches both above and below the caption for the nearest image that has
        sufficient horizontal overlap.

        Args:
            caption_bbox: Bounding box of the caption (x0, y0, x1, y1).
            image_blocks: List of image bounding boxes.
            max_vertical_distance: Maximum vertical distance to consider.
            min_horizontal_overlap: Minimum horizontal overlap ratio required.

        Returns:
            The closest matching image bbox, or None if no match found.
        """
        best_image = None
        best_distance = float("inf")

        for img_bbox in image_blocks:
            v_dist = self._vertical_distance(caption_bbox, img_bbox)
            h_overlap = self._horizontal_overlap(caption_bbox, img_bbox)

            if v_dist > max_vertical_distance:
                continue
            if h_overlap < min_horizontal_overlap:
                continue

            if v_dist < best_distance:
                best_distance = v_dist
                best_image = img_bbox

        return best_image

    @staticmethod
    def _column_bounds(
        caption_bbox: tuple,
        page_rect: tuple,
        margin: float = 50,
        padding: float = 20,
    ) -> tuple | None:
        """Return column bounds for a caption or None for full-width.

        Args:
            caption_bbox: Bounding box of the caption.
            page_rect: Page rectangle.
            margin: Page margin.
            padding: Padding around caption.

        Returns:
            Tuple of (left, right) bounds or None for full-width.
        """
        page_width = page_rect[2] - page_rect[0]
        caption_width = caption_bbox[2] - caption_bbox[0]
        if caption_width < page_width * 0.6:
            left = max(margin, caption_bbox[0] - padding)
            right = min(page_rect[2] - margin, caption_bbox[2] + padding)
            return (left, right)
        return None

    def _expand_bbox_with_neighbors(
        self,
        base_bbox: tuple,
        image_bboxes: list[tuple],
        max_gap: float = 20,
        min_overlap: float = 0.2,
    ) -> tuple:
        """Expand bounding box by merging nearby/overlapping image bboxes.

        Args:
            base_bbox: Base bounding box to expand.
            image_bboxes: List of neighboring image bounding boxes.
            max_gap: Maximum vertical gap for merging.
            min_overlap: Minimum horizontal overlap for merging.

        Returns:
            Expanded bounding box.
        """
        merged = base_bbox
        for bbox in image_bboxes:
            if bbox == base_bbox:
                continue
            v_dist = self._vertical_distance(merged, bbox)
            h_overlap = self._horizontal_overlap(merged, bbox)
            if v_dist <= max_gap or h_overlap >= min_overlap:
                merged = self._merge_bboxes(merged, bbox, padding=2)
        return merged

    def _infer_caption_position(
        self,
        caption_bbox: tuple | None,
        image_bboxes: list[tuple],
    ) -> str:
        """Infer whether captions are above or below figures using the first caption.

        Args:
            caption_bbox: Bounding box of the first caption.
            image_bboxes: List of image bounding boxes on the page.

        Returns:
            Either "above" or "below".
        """
        if caption_bbox is None or not image_bboxes:
            return "below"

        above_images = [bbox for bbox in image_bboxes if bbox[3] <= caption_bbox[1]]
        below_images = [bbox for bbox in image_bboxes if bbox[1] >= caption_bbox[3]]

        if above_images and not below_images:
            return "above"
        if below_images and not above_images:
            return "below"

        closest_above = self._find_closest_image(caption_bbox, above_images) if above_images else None
        closest_below = self._find_closest_image(caption_bbox, below_images) if below_images else None

        if closest_above is not None and closest_below is None:
            return "above"
        if closest_below is not None and closest_above is None:
            return "below"
        return "below"

    def _find_figure_region(
        self,
        caption_bbox: tuple,
        all_blocks: list[dict],
        page_rect: tuple,
        margin: float = 50,
        prefer_full_width: bool = False,
        top_limit: float | None = None,
        bottom_limit: float | None = None,
    ) -> tuple:
        """Determine the figure region above a caption.

        In academic papers, figures are typically placed above their captions.
        This function finds the appropriate region by looking for the nearest
        text block above the caption or using page margins.

        Args:
            caption_bbox: Bounding box of the caption (x0, y0, x1, y1).
            all_blocks: All blocks on the page.
            page_rect: Page rectangle (x0, y0, x1, y1).
            margin: Margin from page edges.
            prefer_full_width: Whether to prefer full page width.
            top_limit: Optional top boundary limit.
            bottom_limit: Optional bottom boundary limit.

        Returns:
            Bounding box for the figure region (x0, y0, x1, y1).
        """
        caption_top = caption_bbox[1]
        caption_left = caption_bbox[0]
        caption_right = caption_bbox[2]

        # Find the nearest text block ABOVE the caption
        nearest_text_bottom = margin

        for blk in all_blocks:
            if blk["type"] != 0:
                continue

            blk_bottom = blk["bbox"][3]
            blk_top = blk["bbox"][1]

            if blk_bottom >= caption_top - 5:
                continue

            blk_height = blk_bottom - blk_top
            if blk_height < 10:
                continue

            text = self._get_block_text(blk)

            if self._is_figure_caption(text):
                nearest_text_bottom = max(nearest_text_bottom, blk_bottom)
                continue

            nearest_text_bottom = max(nearest_text_bottom, blk_bottom)

        # Calculate figure region
        page_width = page_rect[2] - page_rect[0]
        caption_width = caption_right - caption_left

        if not prefer_full_width and caption_width < page_width * 0.6:
            fig_left = max(margin, caption_left - 20)
            fig_right = min(page_rect[2] - margin, caption_right + 20)
        else:
            fig_left = margin
            fig_right = page_rect[2] - margin

        fig_top = nearest_text_bottom + 5
        fig_bottom = caption_top - 2

        if top_limit is not None:
            fig_top = max(fig_top, top_limit)
        if bottom_limit is not None:
            fig_bottom = min(fig_bottom, bottom_limit)

        if fig_bottom - fig_top < 50:
            fig_top = max(margin, fig_bottom - 200)

        return (fig_left, fig_top, fig_right, fig_bottom)

    # -------------------------------------------------------------------------
    # Page processing and image extraction
    # -------------------------------------------------------------------------

    def _detect_caption_position(self, doc) -> str:
        """Detect whether captions are above or below figures in the document.

        Args:
            doc: PyMuPDF document object.

        Returns:
            Either "above" or "below".
        """
        for page_index, page in enumerate(doc, start=1):
            if page_index > self.MAX_PAGES:
                break

            blocks = page.get_text("dict")["blocks"]
            image_bboxes = self._collect_image_bboxes(page, blocks)
            caption_bboxes = []

            for blk in blocks:
                if blk["type"] == 0:
                    text = self._get_block_text(blk)
                    if self._is_figure_caption(text):
                        caption_bboxes.append(tuple(blk["bbox"]))

            if image_bboxes and caption_bboxes:
                position = self._infer_caption_position(caption_bboxes[0], image_bboxes)
                logger.debug(f"Inferred caption position '{position}' for document")
                return position

        logger.debug("Defaulting caption position to 'below'")
        return "below"

    def _collect_captions(self, blocks: list[dict]) -> list[dict]:
        """Collect all figure caption entries from page blocks.

        Args:
            blocks: List of page blocks.

        Returns:
            List of caption entry dictionaries with bbox, figure_id, and description.
        """
        caption_entries: list[dict] = []

        for blk in blocks:
            if blk["type"] == 0:
                text = self._get_block_text(blk)
                if self._is_figure_caption(text):
                    figure_id = self._extract_figure_id(text)
                    if figure_id:
                        caption_entries.append(
                            {
                                "bbox": tuple(blk["bbox"]),
                                "figure_id": figure_id,
                                "description": text,
                            },
                        )

        return caption_entries

    def _compute_caption_limits(
        self,
        caption_entries: list[dict],
        page_rect: tuple,
    ) -> dict[int, tuple[float | None, float | None]]:
        """Compute vertical limits for each caption based on neighboring captions.

        Args:
            caption_entries: List of caption entry dictionaries.
            page_rect: Page rectangle.

        Returns:
            Dictionary mapping caption index to (top_limit, bottom_limit) tuple.
        """
        # Add column bounds to each entry
        for entry in caption_entries:
            entry["column_bounds"] = self._column_bounds(entry["bbox"], page_rect)

        caption_limits: dict[int, tuple[float | None, float | None]] = {}
        vertical_order = sorted(
            range(len(caption_entries)),
            key=lambda i: caption_entries[i]["bbox"][1],
        )

        for pos, idx in enumerate(vertical_order):
            current_bbox = caption_entries[idx]["bbox"]
            prev_bbox = None
            next_bbox = None

            for j in range(pos - 1, -1, -1):
                other_bbox = caption_entries[vertical_order[j]]["bbox"]
                if self._horizontal_overlap(current_bbox, other_bbox) >= 0.2:
                    prev_bbox = other_bbox
                    break

            for j in range(pos + 1, len(vertical_order)):
                other_bbox = caption_entries[vertical_order[j]]["bbox"]
                if self._horizontal_overlap(current_bbox, other_bbox) >= 0.2:
                    next_bbox = other_bbox
                    break

            top_limit = prev_bbox[3] + 2 if prev_bbox else None
            bottom_limit = next_bbox[1] - 2 if next_bbox else None
            caption_limits[idx] = (top_limit, bottom_limit)

        return caption_limits

    def _get_sorted_caption_order(self, caption_entries: list[dict]) -> list[int]:
        """Get caption indices sorted by figure ID.

        Args:
            caption_entries: List of caption entry dictionaries.

        Returns:
            List of indices sorted by figure ID.
        """
        return sorted(
            range(len(caption_entries)),
            key=lambda i: (
                caption_entries[i]["figure_id"].isdigit(),
                caption_entries[i]["figure_id"].zfill(10)
                if caption_entries[i]["figure_id"][:-1].isdigit() or caption_entries[i]["figure_id"].isdigit()
                else caption_entries[i]["figure_id"],
            ),
        )

    def _find_candidate_images(
        self,
        caption_bbox: tuple,
        image_bboxes: list[tuple],
        caption_position: str,
        column_bounds: tuple | None,
        top_limit: float | None,
    ) -> list[tuple]:
        """Find candidate image bboxes for a caption.

        Args:
            caption_bbox: Bounding box of the caption.
            image_bboxes: All image bounding boxes on the page.
            caption_position: Either "above" or "below".
            column_bounds: Optional column bounds (left, right).
            top_limit: Optional top limit.

        Returns:
            List of candidate image bounding boxes.
        """
        candidate_bboxes = image_bboxes

        if top_limit is not None:
            candidate_bboxes = [bbox for bbox in candidate_bboxes if bbox[3] >= top_limit + 2]

        if column_bounds:
            column_left, column_right = column_bounds
            candidate_bboxes = [
                bbox
                for bbox in candidate_bboxes
                if column_left <= self._bbox_center_x(bbox) <= column_right
                and self._horizontal_overlap(bbox, caption_bbox) >= 0.2
            ]

        # Filter by position relative to caption
        if caption_position == "above":
            side_images = [
                bbox
                for bbox in candidate_bboxes
                if bbox[3] <= caption_bbox[1] + 5 and self._horizontal_overlap(bbox, caption_bbox) >= 0.1
            ]
        else:
            side_images = [
                bbox
                for bbox in candidate_bboxes
                if bbox[1] >= caption_bbox[3] - 5 and self._horizontal_overlap(bbox, caption_bbox) >= 0.1
            ]

        return side_images

    def _compute_figure_region(
        self,
        caption_bbox: tuple,
        blocks: list[dict],
        page_rect: tuple,
        side_images: list[tuple],
        column_bounds: tuple | None,
        top_limit: float | None,
        bottom_limit: float | None,
    ) -> tuple[tuple, bool]:
        """Compute the figure region for a caption.

        Args:
            caption_bbox: Bounding box of the caption.
            blocks: All page blocks.
            page_rect: Page rectangle.
            side_images: Candidate image bounding boxes.
            column_bounds: Optional column bounds.
            top_limit: Optional top limit.
            bottom_limit: Optional bottom limit.

        Returns:
            Tuple of (figure_region, used_image_match) where used_image_match
            indicates whether an actual image bbox was matched.
        """
        closest_image = self._find_closest_image(caption_bbox, side_images)

        if closest_image is not None:
            image_region = self._expand_bbox_with_neighbors(closest_image, side_images)
            figure_region = self._clamp_bbox(image_region, page_rect)
            return figure_region, True

        # Fallback to rendered region
        render_region = self._find_figure_region(
            caption_bbox,
            blocks,
            page_rect,
            prefer_full_width=True,
            top_limit=top_limit,
            bottom_limit=bottom_limit,
        )
        figure_region = self._clamp_bbox(render_region, page_rect)

        # Apply column and limit constraints
        if column_bounds:
            column_left, column_right = column_bounds
            figure_region = (
                max(figure_region[0], column_left),
                figure_region[1],
                min(figure_region[2], column_right),
                figure_region[3],
            )

        if top_limit is not None:
            figure_region = (
                figure_region[0],
                max(figure_region[1], top_limit),
                figure_region[2],
                figure_region[3],
            )

        if bottom_limit is not None:
            figure_region = (
                figure_region[0],
                figure_region[1],
                figure_region[2],
                min(figure_region[3], bottom_limit),
            )

        return figure_region, False

    def _create_combined_region(
        self,
        figure_region: tuple,
        caption_bbox: tuple,
        page_rect: tuple,
        used_image_match: bool,
        column_bounds: tuple | None,
        top_limit: float | None,
    ) -> tuple | None:
        """Create a combined region including figure and caption.

        Args:
            figure_region: Bounding box of the figure region.
            caption_bbox: Bounding box of the caption.
            page_rect: Page rectangle.
            used_image_match: Whether an image bbox was matched.
            column_bounds: Optional column bounds.
            top_limit: Optional top limit.

        Returns:
            Combined bounding box or None if region is too small.
        """
        combined_bbox = self._merge_bboxes(figure_region, caption_bbox, padding=5)
        combined_bbox = self._clamp_bbox(combined_bbox, page_rect)

        if not used_image_match:
            if column_bounds:
                column_left, column_right = column_bounds
                combined_bbox = (
                    max(combined_bbox[0], column_left),
                    combined_bbox[1],
                    min(combined_bbox[2], column_right),
                    combined_bbox[3],
                )
            if top_limit is not None and top_limit < caption_bbox[1]:
                combined_bbox = (
                    combined_bbox[0],
                    max(combined_bbox[1], top_limit),
                    combined_bbox[2],
                    combined_bbox[3],
                )

        combined_width = combined_bbox[2] - combined_bbox[0]
        combined_height = combined_bbox[3] - combined_bbox[1]

        if combined_width < 50 or combined_height < 30:
            return None

        return combined_bbox

    def _save_figure(
        self,
        page,
        combined_bbox: tuple,
        figure_id: str,
        description: str,
    ) -> bool:
        """Render and save a figure from the page.

        Args:
            page: PyMuPDF page object.
            combined_bbox: Bounding box to render.
            figure_id: Figure identifier for filename.
            description: Figure description to save.

        Returns:
            True if save succeeded, False otherwise.
        """
        fitz = self._get_fitz()

        try:
            rect = fitz.Rect(*combined_bbox)
            pix = page.get_pixmap(dpi=200, clip=rect, alpha=False)
            img_bytes = pix.tobytes("ppm")
            image = Image.open(io.BytesIO(img_bytes))
            image = image.convert("RGB")

            image_name = f"figure_{figure_id}.jpg"
            image_path = os.path.join(self.output_folder, image_name)
            image.save(image_path, "JPEG", quality=100)

            desc_path = os.path.join(self.output_folder, f"figure_{figure_id}.txt")
            with open(desc_path, "w", encoding="utf-8") as desc_file:
                desc_file.write(description)

            return True

        except Exception as e:
            logger.warning(f"Failed to save figure {figure_id}: {e}")
            return False

    def _process_page(
        self,
        page,
        page_index: int,
        caption_position: str,
        extracted_figure_ids: set[str],
        current_count: int,
    ) -> int:
        """Process a single page and extract figures.

        Args:
            page: PyMuPDF page object.
            page_index: 1-based page index.
            caption_position: Either "above" or "below".
            extracted_figure_ids: Set of already extracted figure IDs (modified in place).
            current_count: Current extraction count.

        Returns:
            Number of figures extracted from this page.
        """
        blocks = page.get_text("dict")["blocks"]
        page_rect = (0, 0, page.rect.width, page.rect.height)
        image_bboxes = self._collect_image_bboxes(page, blocks)

        if not image_bboxes:
            logger.debug(f"No image bboxes found on page {page_index}")

        caption_entries = self._collect_captions(blocks)
        if not caption_entries:
            return 0

        caption_limits = self._compute_caption_limits(caption_entries, page_rect)
        caption_order = self._get_sorted_caption_order(caption_entries)

        extracted_this_page = 0

        for idx in caption_order:
            if current_count + extracted_this_page >= self.MAX_IMAGES:
                break

            entry = caption_entries[idx]
            caption_bbox = entry["bbox"]
            figure_id = entry["figure_id"]
            description = entry["description"]
            column_bounds = entry.get("column_bounds")
            top_limit, bottom_limit = caption_limits.get(idx, (None, None))

            if figure_id in extracted_figure_ids:
                logger.debug(
                    f"Skipping duplicate figure {figure_id} on page {page_index}",
                )
                continue

            # Debug logging
            if top_limit is not None:
                logger.debug(
                    f"Applying top limit {top_limit:.1f} for figure {figure_id} on page {page_index}",
                )
            if bottom_limit is not None:
                logger.debug(
                    f"Applying bottom limit {bottom_limit:.1f} for figure {figure_id} on page {page_index}",
                )
            if column_bounds:
                logger.debug(
                    f"Applying column bounds {column_bounds[0]:.1f}-{column_bounds[1]:.1f} "
                    f"for figure {figure_id} on page {page_index}",
                )

            side_images = self._find_candidate_images(
                caption_bbox,
                image_bboxes,
                caption_position,
                column_bounds,
                top_limit,
            )

            if not side_images:
                logger.debug(
                    f"No candidate images on '{caption_position}' side for figure {figure_id} on page {page_index}",
                )

            figure_region, used_image_match = self._compute_figure_region(
                caption_bbox,
                blocks,
                page_rect,
                side_images,
                column_bounds,
                top_limit,
                bottom_limit,
            )

            if used_image_match:
                logger.debug(
                    f"Matched image bbox for figure {figure_id} on page {page_index} (no crop)",
                )
            else:
                logger.debug(
                    f"Fallback region used for figure {figure_id} on page {page_index}",
                )

            # Validate figure region
            region_width = figure_region[2] - figure_region[0]
            region_height = figure_region[3] - figure_region[1]

            if region_width < 50 or region_height < 30:
                logger.debug(
                    f"Figure region too small for figure {figure_id} on page {page_index}: "
                    f"{region_width:.1f}x{region_height:.1f}",
                )
                continue

            combined_bbox = self._create_combined_region(
                figure_region,
                caption_bbox,
                page_rect,
                used_image_match,
                column_bounds,
                top_limit,
            )

            if combined_bbox is None:
                logger.debug(
                    f"Combined region too small for figure {figure_id} on page {page_index}",
                )
                continue

            if self._save_figure(page, combined_bbox, figure_id, description):
                extracted_figure_ids.add(figure_id)
                extracted_this_page += 1
                logger.debug(f"Extracted figure {figure_id} from page {page_index}")

        return extracted_this_page


# -----------------------------------------------------------------------------
# Module-level convenience function for backward compatibility
# -----------------------------------------------------------------------------


def extract_images(pdf_path: str, output_folder: str = "images") -> int:
    """Extract labeled figures from a PDF file into an output folder.

    This is a convenience function that wraps the FigureExtractor class.

    Args:
        pdf_path: Path to the input PDF file.
        output_folder: Folder to save extracted images.

    Returns:
        Number of figures extracted.
    """
    return FigureExtractor(pdf_path, output_folder).extract()


if __name__ == "__main__":
    extract_images("test_2.pdf", "test_data/")
