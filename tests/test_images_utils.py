"""Tests for images_utils module."""
# ruff: noqa: S101

import tempfile
from pathlib import Path

from src.utils.images_utils import load_images_and_descriptions


class TestLoadImagesAndDescriptions:
    """Tests for load_images_and_descriptions function."""

    def test_natural_sorting_of_figure_numbers(self):
        """Test that figures are sorted numerically, not lexicographically.

        figure_4.jpg should come before figure_14.jpg.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files in a deliberately wrong lexicographic order
            test_files = [
                ("figure_1.jpg", "figure_1.txt", "Description 1"),
                ("figure_4.jpg", "figure_4.txt", "Description 4"),
                ("figure_14.jpg", "figure_14.txt", "Description 14"),
                ("figure_2.jpg", "figure_2.txt", "Description 2"),
                ("figure_20.jpg", "figure_20.txt", "Description 20"),
                ("figure_3.jpg", "figure_3.txt", "Description 3"),
            ]

            for img_name, txt_name, description in test_files:
                # Create empty image file
                Path(tmpdir, img_name).touch()
                # Create description file
                with open(Path(tmpdir, txt_name), "w", encoding="utf-8") as f:
                    f.write(description)

            # Load images
            result = load_images_and_descriptions(tmpdir)

            # Extract base names
            base_names = [base for base, _, _ in result]

            # Expected order (numerical, not lexicographic)
            expected_order = ["figure_1", "figure_2", "figure_3", "figure_4", "figure_14", "figure_20"]

            assert base_names == expected_order, (
                f"Expected {expected_order}, but got {base_names}. "
                "Images should be sorted numerically, not lexicographically."
            )

    def test_loads_images_with_descriptions(self):
        """Test that images and their descriptions are loaded correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            Path(tmpdir, "figure_1.jpg").touch()
            with open(Path(tmpdir, "figure_1.txt"), "w", encoding="utf-8") as f:
                f.write("Test description")

            result = load_images_and_descriptions(tmpdir)

            assert len(result) == 1
            base, img_path, desc = result[0]
            assert base == "figure_1"
            assert img_path.endswith("figure_1.jpg")
            assert desc == "Test description"

    def test_skips_images_without_descriptions(self):
        """Test that images without .txt files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "figure_1.jpg").touch()
            # No corresponding .txt file

            result = load_images_and_descriptions(tmpdir)

            assert len(result) == 0

    def test_empty_directory(self):
        """Test that empty directory returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_images_and_descriptions(tmpdir)
            assert result == []
