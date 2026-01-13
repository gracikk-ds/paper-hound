"""Extract images from a PDF file into an output folder."""

import io
import os
import re

import fitz
from loguru import logger
from PIL import Image

MIN_IMAGE_SIZE: int = 10


def filter_images_by_size(blk: dict, img_index: int, page_index: int) -> bool:
    """Filter images by size.

    Args:
        blk (dict): Block object
        img_index (int): Index of the image
        page_index (int): Index of the page

    Returns:
        bool: True if image is large enough, False otherwise
    """
    blk_width = blk["bbox"][2] - blk["bbox"][0]
    blk_height = blk["bbox"][3] - blk["bbox"][1]
    if blk_width <= MIN_IMAGE_SIZE and blk_height <= MIN_IMAGE_SIZE:
        logger.info(f"Skipping image {img_index} on page {page_index} because it's too small.")
        return True
    return False


def get_block_description(block: dict) -> str:
    """Given a page block, return the text appearing in the block.

    Args:
        block (dict): Page block

    Returns:
        str: The text appearing in the block
    """
    description = " ".join(span["text"] for line in block["lines"] for span in line["spans"]).strip()
    if "Figure" not in description and "Fig." not in description:
        return ""
    description = re.sub(r"\s+", " ", description)
    description = re.sub(r"\n", " ", description)
    return re.sub(r"- ", "", description)


def extract_figure_number(description: str) -> str:
    """Extract the figure number from the description.

    Args:
        description (str): The description of the figure

    Returns:
        str: The figure number
    """
    match = re.search(r"Figure (\d+)", description)
    if match:
        return match.group(1)
    match = re.search(r"Fig\. (\d+)", description)
    if match:
        return match.group(1)
    return ""


def extract_images(pdf_path: str, output_folder: str = "images") -> None:
    """Extract images from a PDF file into an output folder.

    Args:
        pdf_path: Path to the input PDF file
        output_folder: Folder to save extracted images
    """
    doc = fitz.open(pdf_path)  # type: ignore
    os.makedirs(output_folder, exist_ok=True)

    # Iterate through each page
    max_pages: int = 10
    max_images: int = 10
    img_num = 0
    for page_index, page in enumerate(doc, start=1):
        if page_index > max_pages:
            break
        # Reading-order blocks of this page
        blocks = page.get_text("dict")["blocks"]
        is_inside_picture = False
        coords = None
        for blk_idx, blk in enumerate(blocks, start=1):
            if blk["type"] != 1 and not is_inside_picture:
                continue

            if blk["type"] == 1:
                if filter_images_by_size(blk, blk_idx, page_index):
                    continue
                is_inside_picture = True

            if coords is None:
                coords = blk["bbox"]
            else:
                coords = (
                    min(coords[0], blk["bbox"][0]),
                    min(coords[1], blk["bbox"][1]),
                    max(coords[2], blk["bbox"][2]),
                    max(coords[3], blk["bbox"][3]),
                )

            if blk["type"] != 1:
                description = get_block_description(blk)
                figure_number = extract_figure_number(description)
                if figure_number == "":
                    continue
            else:
                continue
            image_name = f"figure_{figure_number}.jpg"
            image_path = os.path.join(output_folder, image_name)
            rect = fitz.Rect(coords[0] - 10, coords[1] - 10, coords[2] + 10, coords[3] + 10)  # type: ignore
            pix = page.get_pixmap(dpi=300, clip=rect, alpha=False)
            img_bytes = pix.tobytes("ppm")  # Get image as PPM bytes
            image = Image.open(io.BytesIO(img_bytes))
            image = image.convert("RGB")
            image.save(image_path, "JPEG", quality=70)
            with open(os.path.join(output_folder, f"figure_{figure_number}.txt"), "w") as description_file:
                description_file.write(f"{description}")
            is_inside_picture = False
            coords = None
            img_num += 1
        if img_num >= max_images:
            break
    logger.info(f"\nCompleted extraction of images from '{pdf_path}'")


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
        return

    # Separate Figure 1 and the rest
    fig1 = next(
        ((base, img_path, desc) for (base, img_path, desc) in figures if base == "figure_1"),
        None,
    )
    other_figs = [(base, img_path, desc) for (base, img_path, desc) in figures if base != "figure_1"]

    if fig1 is None:
        fig1 = other_figs[0]
        other_figs = other_figs[1:]

    # Read the original markdown
    with open(md_path, encoding="utf-8") as md_file:
        md_content = md_file.read()

    # Insert Figure 1 at the top
    if fig1:
        _, img_path, desc = fig1
        new_md += img_block(img_path, desc) + "\n"

    new_md += md_content.rstrip()

    if not other_figs:
        # Continue writing even when no additional figures are present
        logger.warning(f"No other figures found in {images_dir}")
    else:
        new_md = new_md + "\n\n"
        new_md = new_md + "## 6. Paper Figures\n"

        # Append other figures
        for _, img_path, desc in other_figs:
            new_md += img_block(img_path, desc) + "\n"

    # Write back to the markdown file
    with open(md_path, "w", encoding="utf-8") as md_file:
        md_file.write(new_md)
