"""Utilities for working with extracted images and markdown generation."""

import os

from loguru import logger


def load_images_and_descriptions(images_dir: str) -> list[tuple[str, str, str]]:
    """Load images and descriptions from the images directory.

    Args:
        images_dir (str): Path to the directory containing images and .txt descriptions.

    Returns:
        list[tuple[str, str, str]]: List of tuples containing the base name, image path, and description.
    """
    figures: list[tuple[str, str, str]] = []
    for fname in sorted(os.listdir(images_dir)):  # noqa: PTH208
        if fname.endswith(".jpg"):
            base = fname[:-4]
            txt_path = os.path.join(images_dir, base + ".txt")
            img_path = os.path.join(images_dir, fname)
            if os.path.exists(txt_path):
                with open(txt_path, encoding="utf-8") as description_file:
                    desc = description_file.read().strip()
                figures.append((base, img_path, desc))
    return figures


def img_block(img_path: str, desc: str) -> str:
    """Prepare markdown blocks.

    Args:
        img_path (str): Path to the image.
        desc (str): Description of the image.

    Returns:
        str: Markdown block.
    """
    rel_path = os.path.relpath(img_path).replace("site", "")
    rel_path = f"'{rel_path}' | relative_url"
    rel_path = "{{ " + rel_path + " }}"
    return f"![{desc}]({rel_path})"


def add_images_to_md(md_path: str, images_dir: str, paper_info: dict) -> None:
    """Add images and their descriptions from images_dir to a markdown file at md_path.

    Figure 1 is inserted at the top, others are appended at the end.

    Args:
        md_path (str): Path to the markdown file.
        images_dir (str): Path to the directory containing images and .txt descriptions.
        paper_info (dict): The information about the paper.
    """
    paper_name = md_path.split("/")[-1].split(".")[0]
    new_md = f"---\ntitle: {paper_name}\nlayout: default\ndate: {paper_info['published_date']}\n---\n"
    new_md += f"## {paper_info['title']}\n"
    new_md += f"**Authors:**{paper_info['authors']}\n\n"
    new_md += f"**ArXiv URL:** https://www.alphaxiv.org/abs/{paper_info['paper_id']}\n\n"
    new_md += f"**Published Date:** {paper_info['published_date']}\n\n"

    figures = load_images_and_descriptions(images_dir)
    if not figures:
        logger.warning(f"No figures found in {images_dir}")

    # Read the original markdown content - always do this
    with open(md_path, encoding="utf-8") as md_file:
        md_content = md_file.read()

    # Process and add figures only if they exist
    fig1 = None
    other_figs = []

    if figures:
        # Separate Figure 1 and the rest
        fig1 = next(
            ((base, img_path, desc) for (base, img_path, desc) in figures if base == "figure_1"),
            None,
        )
        other_figs = [(base, img_path, desc) for (base, img_path, desc) in figures if base != "figure_1"]

        if fig1 is None:
            fig1 = other_figs[0]
            other_figs = other_figs[1:]

        # Insert Figure 1 at the top
        if fig1:
            _, img_path, desc = fig1
            new_md += img_block(img_path, desc) + "\n"

    # Append original content - always do this
    new_md += md_content.rstrip()

    # Add other figures section only if they exist
    if figures and other_figs:
        new_md = new_md + "\n\n"
        new_md = new_md + "## 6. Paper Figures\n"

        # Append other figures
        for _, img_path, desc in other_figs:
            new_md += img_block(img_path, desc) + "\n"
    elif figures and not other_figs:
        # Continue writing even when no additional figures are present
        logger.warning(f"No other figures found in {images_dir}")

    # Write back to the markdown file - always do this
    with open(md_path, "w", encoding="utf-8") as md_file:
        md_file.write(new_md)
