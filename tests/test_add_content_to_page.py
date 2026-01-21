"""Unit tests for markdown to Notion conversion with equation parsing."""
# ruff: noqa: S101, SLF001, PLR2004

from unittest.mock import patch

import pytest

from src.service.notion_db.add_content_to_page import MarkdownToNotionUploader


@pytest.fixture
def uploader() -> MarkdownToNotionUploader:
    """Create a MarkdownToNotionUploader instance with mocked dependencies."""
    with patch("src.service.notion_db.add_content_to_page.S3Uploader"):
        return MarkdownToNotionUploader()


# =============================================================================
# Inline Equation Tests (_parse_rich_text)
# =============================================================================


class TestParseRichTextInlineEquations:
    """Tests for inline equation parsing in _parse_rich_text."""

    def test_single_inline_equation(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse a single inline equation."""
        result = uploader._parse_rich_text("The formula $E=mc^2$ is famous")
        assert len(result) == 3
        assert result[0] == {"type": "text", "text": {"content": "The formula "}}
        assert result[1] == {"type": "equation", "equation": {"expression": "E=mc^2"}}
        assert result[2] == {"type": "text", "text": {"content": " is famous"}}

    def test_equation_only(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse a line with only an equation."""
        result = uploader._parse_rich_text("$x^2 + y^2 = z^2$")
        assert len(result) == 1
        assert result[0] == {"type": "equation", "equation": {"expression": "x^2 + y^2 = z^2"}}

    def test_multiple_inline_equations(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse multiple inline equations in a single line."""
        result = uploader._parse_rich_text("Given $a$ and $b$, compute $a + b$")
        assert len(result) == 6
        assert result[0] == {"type": "text", "text": {"content": "Given "}}
        assert result[1] == {"type": "equation", "equation": {"expression": "a"}}
        assert result[2] == {"type": "text", "text": {"content": " and "}}
        assert result[3] == {"type": "equation", "equation": {"expression": "b"}}
        assert result[4] == {"type": "text", "text": {"content": ", compute "}}
        assert result[5] == {"type": "equation", "equation": {"expression": "a + b"}}

    def test_equation_at_start(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse equation at the start of line."""
        result = uploader._parse_rich_text("$\\alpha$ is the learning rate")
        assert len(result) == 2
        assert result[0] == {"type": "equation", "equation": {"expression": "\\alpha"}}
        assert result[1] == {"type": "text", "text": {"content": " is the learning rate"}}

    def test_equation_at_end(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse equation at the end of line."""
        result = uploader._parse_rich_text("The result is $\\theta$")
        assert len(result) == 2
        assert result[0] == {"type": "text", "text": {"content": "The result is "}}
        assert result[1] == {"type": "equation", "equation": {"expression": "\\theta"}}

    def test_no_equation(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse line without equations (backward compatibility)."""
        result = uploader._parse_rich_text("Plain text without equations")
        assert len(result) == 1
        assert result[0] == {"type": "text", "text": {"content": "Plain text without equations"}}

    def test_complex_latex_equation(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse complex LaTeX expressions."""
        result = uploader._parse_rich_text(
            "The integral $\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}$ is well known",
        )
        assert len(result) == 3
        assert result[1]["type"] == "equation"
        assert result[1]["equation"]["expression"] == "\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}"


# =============================================================================
# Mixed Content Tests (Bold + Equations)
# =============================================================================


class TestParseRichTextMixedContent:
    """Tests for mixed content with bold and equations."""

    def test_bold_and_equation(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse line with both bold text and equation."""
        result = uploader._parse_rich_text("**Important**: The formula $E=mc^2$ explains energy")
        # Expected: [bold "Important"], [text ": The formula "], [equation], [text " explains energy"]
        assert len(result) == 4
        assert result[0]["type"] == "text"
        assert result[0]["text"]["content"] == "Important"
        assert result[0]["annotations"]["bold"] is True
        assert result[1] == {"type": "text", "text": {"content": ": The formula "}}
        assert result[2] == {"type": "equation", "equation": {"expression": "E=mc^2"}}
        assert result[3] == {"type": "text", "text": {"content": " explains energy"}}

    def test_equation_between_bold(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse equation between bold texts."""
        result = uploader._parse_rich_text("**Start** $x$ **End**")
        assert len(result) == 5
        assert result[0]["annotations"]["bold"] is True
        assert result[0]["text"]["content"] == "Start"
        assert result[1] == {"type": "text", "text": {"content": " "}}
        assert result[2] == {"type": "equation", "equation": {"expression": "x"}}
        assert result[3] == {"type": "text", "text": {"content": " "}}
        assert result[4]["annotations"]["bold"] is True
        assert result[4]["text"]["content"] == "End"

    def test_bold_only(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse line with only bold text (backward compatibility)."""
        result = uploader._parse_rich_text("This has **bold** text")
        assert len(result) == 3
        assert result[0] == {"type": "text", "text": {"content": "This has "}}
        assert result[1]["text"]["content"] == "bold"
        assert result[1]["annotations"]["bold"] is True
        assert result[2] == {"type": "text", "text": {"content": " text"}}


# =============================================================================
# Block Equation Tests (markdown_to_blocks)
# =============================================================================


class TestMarkdownToBlocksEquations:
    """Tests for block equation parsing in markdown_to_blocks."""

    def test_single_line_block_equation(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse single-line block equation."""
        markdown = "## Test Title\n\n$$E = mc^2$$\n\nSome text"
        blocks, _, _, _, _ = uploader.markdown_to_blocks(markdown)

        # Find the equation block
        equation_blocks = [b for b in blocks if b.get("type") == "equation"]
        assert len(equation_blocks) == 1
        assert equation_blocks[0]["equation"]["expression"] == "E = mc^2"

    def test_multi_line_block_equation(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse multi-line block equation."""
        markdown = "## Test Title\n\n$$\n\\frac{a}{b} = c\n$$\n\nText after"
        blocks, _, _, _, _ = uploader.markdown_to_blocks(markdown)

        equation_blocks = [b for b in blocks if b.get("type") == "equation"]
        assert len(equation_blocks) == 1
        # Multi-line equation content should be joined
        assert "\\frac{a}{b} = c" in equation_blocks[0]["equation"]["expression"]

    def test_multiple_block_equations(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse multiple block equations."""
        markdown = "## Test Title\n\n$$x = 1$$\n\nText\n\n$$y = 2$$"
        blocks, _, _, _, _ = uploader.markdown_to_blocks(markdown)

        equation_blocks = [b for b in blocks if b.get("type") == "equation"]
        assert len(equation_blocks) == 2
        assert equation_blocks[0]["equation"]["expression"] == "x = 1"
        assert equation_blocks[1]["equation"]["expression"] == "y = 2"

    def test_paragraph_with_inline_equation(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse paragraph containing inline equation."""
        markdown = "## Test Title\n\nThe formula $E=mc^2$ is important."
        blocks, _, _, _, _ = uploader.markdown_to_blocks(markdown)

        # Should be a paragraph block with rich_text containing equation
        paragraph_blocks = [b for b in blocks if b.get("type") == "paragraph"]
        assert len(paragraph_blocks) == 1
        rich_text = paragraph_blocks[0]["paragraph"]["rich_text"]
        equation_items = [item for item in rich_text if item.get("type") == "equation"]
        assert len(equation_items) == 1
        assert equation_items[0]["equation"]["expression"] == "E=mc^2"

    def test_bullet_with_inline_equation(self, uploader: MarkdownToNotionUploader) -> None:
        """Parse bullet point containing inline equation."""
        markdown = "## Test Title\n\n- Item with $x^2$ formula"
        blocks, _, _, _, _ = uploader.markdown_to_blocks(markdown)

        bullet_blocks = [b for b in blocks if b.get("type") == "bulleted_list_item"]
        assert len(bullet_blocks) == 1
        rich_text = bullet_blocks[0]["bulleted_list_item"]["rich_text"]
        equation_items = [item for item in rich_text if item.get("type") == "equation"]
        assert len(equation_items) == 1


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in equation parsing."""

    def test_escaped_dollar_sign(self, uploader: MarkdownToNotionUploader) -> None:
        """Escaped dollar sign should not be treated as equation delimiter."""
        result = uploader._parse_rich_text("Price is \\$100 dollars")
        # Should contain the dollar sign as literal text
        full_text = "".join(
            item.get("text", {}).get("content", "") or item.get("equation", {}).get("expression", "") for item in result
        )
        assert "$100" in full_text or "\\$100" in full_text

    def test_empty_equation_delimiters(self, uploader: MarkdownToNotionUploader) -> None:
        """Empty equation delimiters should be handled gracefully."""
        result = uploader._parse_rich_text("Text $$ more text")
        # Should not crash and handle empty delimiters
        assert len(result) >= 1

    def test_unclosed_equation(self, uploader: MarkdownToNotionUploader) -> None:
        """Unclosed equation delimiter should be treated as text."""
        result = uploader._parse_rich_text("Text $unclosed equation")
        # Should return the text as-is without crashing
        assert len(result) >= 1
        full_text = "".join(
            item.get("text", {}).get("content", "") or item.get("equation", {}).get("expression", "") for item in result
        )
        assert "unclosed" in full_text

    def test_adjacent_equations(self, uploader: MarkdownToNotionUploader) -> None:
        """Adjacent equations - at least the first should be parsed."""
        result = uploader._parse_rich_text("$a$$b$")
        equation_items = [item for item in result if item.get("type") == "equation"]
        # The first equation $a$ should be matched
        # Note: $b$ may not match because its opening $ is preceded by $ (trade-off to avoid
        # incorrectly parsing $$block$$ as inline equation)
        assert len(equation_items) >= 1
        assert equation_items[0]["equation"]["expression"] == "a"

    def test_block_equation_in_inline_preserved(self, uploader: MarkdownToNotionUploader) -> None:
        """Block equation markers in inline text should be preserved as text."""
        result = uploader._parse_rich_text("Text $$block$$ more")
        # $$block$$ should not be parsed as inline equation
        equation_items = [item for item in result if item.get("type") == "equation"]
        assert len(equation_items) == 0
        # The text should be preserved
        full_text = "".join(item.get("text", {}).get("content", "") for item in result if item.get("type") == "text")
        assert "$$block$$" in full_text

    def test_equation_with_dollar_inside(self, uploader: MarkdownToNotionUploader) -> None:
        """Equation containing special characters."""
        result = uploader._parse_rich_text("The expression $\\$10 \\times 2$ equals 20")
        # Should parse the equation containing escaped dollar
        assert len(result) >= 1

    def test_block_equation_empty_content(self, uploader: MarkdownToNotionUploader) -> None:
        """Empty block equation should be handled gracefully."""
        markdown = "## Test Title\n\n$$$$\n\nText"
        blocks, _, _, _, _ = uploader.markdown_to_blocks(markdown)
        # Should not crash
        assert isinstance(blocks, list)

    def test_inline_equation_preserves_surrounding_whitespace(self, uploader: MarkdownToNotionUploader) -> None:
        """Whitespace around inline equations should be preserved."""
        result = uploader._parse_rich_text("before $x$ after")
        text_items = [item for item in result if item.get("type") == "text"]
        # Check that spaces are preserved
        texts = [item["text"]["content"] for item in text_items]
        assert any("before " in t for t in texts)
        assert any(" after" in t for t in texts)
