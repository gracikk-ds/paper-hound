"""Download a single PDF from a URL to the specified path."""

from __future__ import annotations

import os
import warnings
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from loguru import logger
from PIL import Image

from src.utils.images_utils import extract_images

if TYPE_CHECKING:
    import fitz as fitz_module

    from src.utils.schemas import Paper


# 50 MB limit (matching Google Cloud's limit for PDFs)
MAX_PDF_SIZE_BYTES: int = 50 * 1024 * 1024
# Threshold for skipping already-small JPEG images (100KB)
SMALL_JPEG_THRESHOLD: int = 100_000

# Progressive image compression levels: (max_dimension, jpeg_quality)
IMAGE_COMPRESSION_LEVELS = [(1200, 80), (1000, 70)]


def _get_fitz() -> fitz_module:  # type: ignore[valid-type]
    """Import PyMuPDF with warnings filtered."""
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

    return fitz


def _convert_to_rgb(pil_image: Image.Image) -> Image.Image:
    """Convert PIL image to RGB mode, handling transparency properly.

    Args:
        pil_image: The PIL image to convert.

    Returns:
        RGB mode PIL image.
    """
    if pil_image.mode in ("RGBA", "P", "LA"):
        # Create white background for transparency
        background = Image.new("RGB", pil_image.size, (255, 255, 255))
        if pil_image.mode == "P":
            pil_image = pil_image.convert("RGBA")
        if pil_image.mode in ("RGBA", "LA"):
            background.paste(pil_image, mask=pil_image.split()[-1])
        else:
            background.paste(pil_image)
        return background
    if pil_image.mode != "RGB":
        return pil_image.convert("RGB")
    return pil_image


def _compress_image_bytes(
    image_bytes: bytes,
    image_ext: str,
    max_image_dim: int,
    jpeg_quality: int,
) -> bytes | None:
    """Compress image bytes by downscaling and recompressing.

    Args:
        image_bytes: Original image bytes.
        image_ext: Original image extension/format.
        max_image_dim: Maximum dimension for the image.
        jpeg_quality: JPEG quality for recompression.

    Returns:
        Compressed image bytes, or None if compression not beneficial.
    """
    pil_image = Image.open(BytesIO(image_bytes))

    # Check if we should skip this image
    width, height = pil_image.size
    is_small_image = width <= max_image_dim and height <= max_image_dim
    is_small_jpeg = image_ext.lower() in ("jpeg", "jpg") and len(image_bytes) < SMALL_JPEG_THRESHOLD
    if is_small_image and is_small_jpeg:
        return None

    # Calculate new dimensions and resize if needed
    scale = min(max_image_dim / width, max_image_dim / height, 1.0)
    if scale < 1.0:
        new_width = int(width * scale)
        new_height = int(height * scale)
        pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Convert to RGB and compress to JPEG
    pil_image = _convert_to_rgb(pil_image)
    output_buffer = BytesIO()
    pil_image.save(output_buffer, format="JPEG", quality=jpeg_quality, optimize=True)
    compressed_bytes = output_buffer.getvalue()

    # Only return if we actually reduced size
    if len(compressed_bytes) < len(image_bytes):
        return compressed_bytes
    return None


def _compress_images_in_pdf(
    pdf_path: Path,
    output_path: Path,
    max_image_dim: int = 1200,
    jpeg_quality: int = 75,
) -> None:
    """Compress images in a PDF by downscaling and recompressing them.

    Uses page.replace_image() to properly replace images while preserving
    their position and the PDF structure.

    Args:
        pdf_path: Path to the source PDF.
        output_path: Path to save the compressed PDF.
        max_image_dim: Maximum dimension (width or height) for images.
        jpeg_quality: JPEG quality (0-100) for recompression.
    """
    fitz = _get_fitz()
    doc = fitz.open(pdf_path)

    # Track which xrefs we've already processed (images can appear on multiple pages)
    processed_xrefs: set[int] = set()

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]

            # Skip if already processed
            if xref in processed_xrefs:
                continue
            processed_xrefs.add(xref)

            try:
                base_image = doc.extract_image(xref)
                if base_image is None:
                    continue

                compressed_bytes = _compress_image_bytes(
                    base_image["image"],
                    base_image["ext"],
                    max_image_dim,
                    jpeg_quality,
                )

                if compressed_bytes is not None:
                    # Use replace_image to properly update the image with correct metadata
                    # This replaces the image across all pages where it appears
                    page.replace_image(xref, stream=compressed_bytes)
                    logger.debug(
                        f"Compressed image {img_index} on page {page_num}: "
                        f"{len(base_image['image'])} -> {len(compressed_bytes)} bytes",
                    )

            except Exception as e:  # noqa: BLE001
                logger.debug(f"Could not compress image {img_index} on page {page_num}: {e}")

    doc.save(output_path, garbage=4, deflate=True, clean=True)
    doc.close()


def _try_truncate_pdf(
    pdf_path: Path,
    compressed_path: Path,
    max_size: int,
) -> bool:
    """Try to truncate pages from the end of a PDF to meet size limit.

    Args:
        pdf_path: Path to the source PDF.
        compressed_path: Path to save the compressed PDF.
        max_size: Maximum allowed file size in bytes.

    Returns:
        True if truncation succeeded, False otherwise.
    """
    fitz = _get_fitz()
    doc = fitz.open(pdf_path)
    original_page_count = len(doc)
    doc.close()

    # Minimum pages to keep (at least first 8 pages or half, whichever is smaller)
    min_pages = min(8, max(1, original_page_count // 2))

    # Binary search for optimal page count
    low, high = min_pages, original_page_count
    best_page_count = None

    while low <= high:
        mid = (low + high) // 2
        doc_copy = fitz.open(pdf_path)

        if mid < original_page_count:
            doc_copy.delete_pages(from_page=mid, to_page=original_page_count - 1)

        doc_copy.save(compressed_path, garbage=4, deflate=True, clean=True)
        doc_copy.close()

        # Also apply image compression to truncated PDF
        try:
            temp_path = pdf_path.with_suffix(".temp.pdf")
            _compress_images_in_pdf(compressed_path, temp_path, 600, 50)
            temp_path.replace(compressed_path)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Image compression during truncation failed: {e}")

        test_size = compressed_path.stat().st_size
        if test_size <= max_size:
            best_page_count = mid
            low = mid + 1
        else:
            high = mid - 1

        compressed_path.unlink(missing_ok=True)

    if best_page_count is None:
        logger.warning(
            f"Could not reduce PDF below {max_size / 1024 / 1024:.1f} MB even with {min_pages} pages",
        )
        return False

    # Create final truncated PDF
    doc = fitz.open(pdf_path)
    if best_page_count < original_page_count:
        doc.delete_pages(from_page=best_page_count, to_page=original_page_count - 1)
    doc.save(compressed_path, garbage=4, deflate=True, clean=True)
    doc.close()

    # Apply image compression to final result
    try:
        temp_path = pdf_path.with_suffix(".temp.pdf")
        _compress_images_in_pdf(compressed_path, temp_path, 600, 50)
        temp_path.replace(compressed_path)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Final image compression failed: {e}")

    compressed_path.replace(pdf_path)
    final_size = pdf_path.stat().st_size
    logger.info(
        f"Truncated PDF from {original_page_count} to {best_page_count} pages ({final_size / 1024 / 1024:.1f} MB)",
    )
    return True


def compress_pdf(pdf_path: Path, max_size: int = MAX_PDF_SIZE_BYTES) -> bool:
    """Compress a PDF file to reduce its size below the maximum limit.

    Uses multiple strategies in order:
    1. Basic PDF structure compression
    2. Image downscaling and recompression (multiple quality levels)
    3. Page truncation (last resort)

    Args:
        pdf_path: Path to the PDF file to compress.
        max_size: Maximum allowed file size in bytes.

    Returns:
        True if compression succeeded and file is under limit, False otherwise.
    """
    current_size = pdf_path.stat().st_size
    if current_size <= max_size:
        return True

    logger.info(
        f"PDF size ({current_size / 1024 / 1024:.1f} MB) exceeds limit "
        f"({max_size / 1024 / 1024:.1f} MB), attempting compression...",
    )

    fitz = _get_fitz()
    compressed_path = pdf_path.with_suffix(".compressed.pdf")

    try:
        # Strategy 1: Basic structure compression
        doc = fitz.open(pdf_path)
        doc.save(compressed_path, garbage=4, deflate=True, clean=True)
        doc.close()

        compressed_size = compressed_path.stat().st_size
        logger.info(
            f"Basic compression: {current_size / 1024 / 1024:.1f} MB -> {compressed_size / 1024 / 1024:.1f} MB",
        )

        if compressed_size <= max_size:
            compressed_path.replace(pdf_path)
            return True

        compressed_path.unlink(missing_ok=True)

        # Strategy 2: Image compression with progressively aggressive settings
        for max_dim, quality in IMAGE_COMPRESSION_LEVELS:
            logger.info(f"Trying image compression: max_dim={max_dim}, quality={quality}")
            try:
                _compress_images_in_pdf(pdf_path, compressed_path, max_dim, quality)
                compressed_size = compressed_path.stat().st_size
                logger.info(f"Image compression result: {compressed_size / 1024 / 1024:.1f} MB")

                if compressed_size <= max_size:
                    compressed_path.replace(pdf_path)
                    logger.info(
                        f"Successfully compressed PDF to {compressed_size / 1024 / 1024:.1f} MB "
                        f"using max_dim={max_dim}, quality={quality}",
                    )
                    return True

                compressed_path.unlink(missing_ok=True)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Image compression failed at level ({max_dim}, {quality}): {e}")
                compressed_path.unlink(missing_ok=True)

        # Strategy 3: Page truncation as last resort
        logger.info("Image compression insufficient, truncating pages from the end...")
        return _try_truncate_pdf(pdf_path, compressed_path, max_size)

    except Exception:  # noqa: BLE001
        logger.exception("Error compressing PDF")
        return False
    finally:
        compressed_path.unlink(missing_ok=True)
        pdf_path.with_suffix(".temp.pdf").unlink(missing_ok=True)


def download_pdf(pdf_url: str, pdf_path: Path, max_size: int = MAX_PDF_SIZE_BYTES) -> None:
    """Download a single PDF from a URL to the specified path.

    Args:
        pdf_url: The URL of the PDF to download.
        pdf_path: The local file path to save the downloaded PDF.
        max_size: Maximum allowed file size in bytes. If exceeded, compression is attempted.

    Raises:
        ValueError: If the PDF is too large and cannot be compressed below the limit.
    """
    file_dir = pdf_path.parent
    os.makedirs(file_dir, exist_ok=True)

    response = requests.get(pdf_url, stream=True, timeout=60)
    response.raise_for_status()
    with open(pdf_path, "wb") as pdf_file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                pdf_file.write(chunk)

    # Check size after download and compress if needed
    if pdf_path.stat().st_size > max_size and not compress_pdf(pdf_path, max_size):
        pdf_path.unlink(missing_ok=True)
        msg = f"PDF could not be compressed below the {max_size / 1024 / 1024:.1f} MB limit"
        raise ValueError(msg)


def load_pdf_and_images(paper: Paper) -> tuple[Path | None, Path | None]:
    """Load the PDF and images for the paper.

    Args:
        paper (Paper): the paper to load.

    Returns:
        tuple[Path, Path]: the path to the PDF and the path to the images.
    """
    file_name = f"{paper.title.replace(' ', '_').lower()}.pdf"
    tmp_pdf_path = Path("tmp_storage/tmp_pdfs") / file_name
    tmp_images_path = Path("tmp_storage/tmp_images") / file_name
    try:
        download_pdf(paper.pdf_url, tmp_pdf_path)
        extract_images(str(tmp_pdf_path), str(tmp_images_path))
    except Exception as exp:  # noqa: BLE001
        logger.error(f"Error loading PDF and images for paper: {paper.title}: {exp}")
        return None, None
    return tmp_pdf_path, tmp_images_path
