"""Workflow service for managing paper processing tasks."""

import asyncio
import datetime
import shutil
from pathlib import Path

from loguru import logger

from src.service.ai_researcher.classifier import Classifier
from src.service.ai_researcher.summarizer import Summarizer
from src.service.arxiv.arxiv_fetcher import ArxivFetcher
from src.service.notion_db.add_content_to_page import MarkdownToNotionUploader
from src.service.notion_db.extract_page_content import NotionPageExtractor
from src.service.processor import PapersProcessor
from src.utils.images_utils import add_images_to_md
from src.utils.load_utils import load_pdf_and_images


class WorkflowService:
    """Service for managing paper processing workflows."""

    def __init__(  # noqa: PLR0913
        self,
        processor: PapersProcessor,
        classifier: Classifier,
        summarizer: Summarizer,
        arxiv_fetcher: ArxivFetcher,
        notion_uploader: MarkdownToNotionUploader,
        notion_settings_extractor: NotionPageExtractor,
        notion_command_database_id: str,
        threshold: float = 0.65,
    ) -> None:
        """Initialize the WorkflowService.

        Args:
            processor (PapersProcessor): Service for processing papers.
            classifier (Classifier): Service for classifying papers.
            summarizer (Summarizer): Service for summarizing papers.
            arxiv_fetcher (ArxivFetcher): Service for fetching papers from ArXiv.
            notion_uploader (MarkdownToNotionUploader): Service for uploading to Notion.
            notion_settings_extractor (NotionPageExtractor): Service for extracting settings from Notion pages.
            notion_command_database_id (str): The ID of the Notion command database.
            threshold (float): The threshold for the similarity score.
        """
        self.threshold = threshold
        self.processor = processor
        self.classifier = classifier
        self.summarizer = summarizer
        self.arxiv_fetcher = arxiv_fetcher
        self.notion_uploader = notion_uploader
        self.notion_settings_extractor = notion_settings_extractor
        self.notion_command_database_id = notion_command_database_id

    def _ingest_papers(self, start_date: datetime.date, end_date: datetime.date) -> tuple[str, str, float]:
        """Ingest papers for a given date range.

        Args:
            start_date (datetime.date): The start date.
            end_date (datetime.date): The end date.

        Returns:
            tuple[str, str, float]: The start date string, end date string and the costs of the embedding service.
        """
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        logger.info(f"Starting ingestion from {start_date_str} to {end_date_str}.")
        try:
            updated_start_date_str, costs = self.processor.insert_papers(start_date, end_date)
        except Exception as exp:  # noqa: BLE001
            logger.error(f"Error inserting papers from {start_date_str} to {end_date_str}: {exp}")
            return start_date_str, end_date_str, 0.0
        else:
            return updated_start_date_str, end_date_str, costs

    def prepare_paper_summary_and_upload(  # noqa: PLR0912,PLR0911
        self,
        paper_id: str,
        summarizer_prompt: str | None = None,
        category: str = "AdHoc Research",
    ) -> str | None:
        """Process a single paper: fetch, download, summarize, and upload to Notion.

        Args:
            paper_id (str): The ID of the paper to process.
            summarizer_prompt (str | None): Custom prompt for summarization.
            category (str): Category for Notion upload.

        Returns:
            str | None: The URL of the created Notion page, or None if failed.
        """
        # Extract paper information
        paper = self.processor.get_paper_by_id(paper_id)
        if paper is None:
            try:
                paper = self.arxiv_fetcher.extract_paper_by_name_or_id(paper_id)
            except Exception as exp:  # noqa: BLE001
                logger.error(f"Failed to fetch paper {paper_id}: {exp}")
                return None

        if paper is None:
            logger.error(f"Paper {paper_id} not found.")
            return None

        # Check if paper already exists in Notion
        url = self.notion_uploader.check_paper_exists(paper.paper_id)
        if url:
            logger.info(f"Paper {paper.title} already exists in Notion: {url}. Skipping.")
            return url

        tmp_pdf_path, tmp_images_path = load_pdf_and_images(paper)
        if tmp_pdf_path is None or tmp_images_path is None:
            logger.error(f"Failed to load PDF or images for paper {paper.title}")
            return None

        # Summarize paper
        try:
            _, md_path_str = self.summarizer.summarize(paper, tmp_pdf_path, summarizer_prompt)
            if md_path_str is None:
                logger.error(f"Error summarizing paper: {paper.title}")
                return None

            md_path = Path(md_path_str)
            add_images_to_md(md_path_str, str(tmp_images_path), paper.model_dump())

            # Upload summary to notion
            return self.notion_uploader.upload_markdown_file(md_path_str, category=category)
        except Exception as exp:  # noqa: BLE001
            logger.error(f"Error processing paper {paper.title}: {exp}")
            return None
        finally:
            # Clean up
            if tmp_pdf_path.exists():
                tmp_pdf_path.unlink()
            if tmp_images_path.exists():
                if tmp_images_path.is_dir():
                    shutil.rmtree(tmp_images_path)
                else:
                    tmp_images_path.unlink()
            if "md_path" in locals() and md_path.exists():
                md_path.unlink()

    def _process_category(  # noqa: PLR0913
        self,
        category: str,
        settings: dict,
        date_start_str: str,
        date_end_str: str,
        top_k: int = 10,
        *,
        use_classifier: bool = True,
    ) -> tuple[float, float, int]:
        """Process a specific category.

        Args:
            category (str): The category name.
            settings (dict): The settings for the category.
            date_start_str (str): Start date string.
            date_end_str (str): End date string.
            top_k (int): Number of candidates.
            use_classifier (bool): Whether to use classifier.

        Returns:
            tuple[float, float, int]: Classifier costs, summarizer costs, processed count.
        """
        query = settings["Query Prompt"]
        try:
            candidates = self.processor.search_papers(
                query=query,
                k=top_k,
                threshold=self.threshold,
                start_date_str=date_start_str,
                end_date_str=date_end_str,
            )
        except Exception as exp:  # noqa: BLE001
            logger.error(f"Error searching papers for category {category}: {exp}")
            return 0.0, 0.0, 0

        logger.info(f"Found {len(candidates)} candidates for '{query}' in {category}")
        processed_count = 0
        cls_costs = 0.0
        sum_costs = 0.0

        for paper in candidates:
            try:
                is_relevant = True
                if use_classifier:
                    is_relevant = self.classifier.classify(
                        title=paper.title,
                        summary=paper.summary,
                        system_prompt=settings["Classifier Prompt"],
                    )
                    cls_costs += self.classifier.inference_price

                if is_relevant:
                    if use_classifier:
                        logger.info(f"Paper '{paper.title}' classified as relevant. Processing...")
                    else:
                        logger.info(f"Processing '{paper.title}' (classifier skipped)...")

                    url = self.prepare_paper_summary_and_upload(
                        paper_id=paper.paper_id,
                        summarizer_prompt=settings["Summarizer Prompt"],
                        category=category,
                    )
                    sum_costs += self.summarizer.inference_price
                    if url:
                        logger.info(f"Successfully processed '{paper.title}': {url}")
                        processed_count += 1
                else:
                    logger.info(f"Paper '{paper.title}' classified as NOT relevant.")
            except Exception as exp:  # noqa: BLE001
                logger.error(f"Error processing candidate '{paper.title}': {exp}")

        return cls_costs, sum_costs, processed_count

    def run_workflow(  # noqa: PLR0913
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        *,
        skip_ingestion: bool = False,
        use_classifier: bool = True,
        top_k: int = 10,
        category: str | None = None,
    ) -> None:
        """Run the workflow for a date range.

        Args:
            start_date (datetime.date): Start date.
            end_date (datetime.date): End date.
            skip_ingestion (bool): Whether to skip paper ingestion.
            use_classifier (bool): Whether to use the classifier.
            top_k (int): Number of papers to retrieve per category.
            category (str | None): Category to process.
        """
        embedder_costs = 0.0
        date_start_str = start_date.strftime("%Y-%m-%d")
        date_end_str = end_date.strftime("%Y-%m-%d")

        if not skip_ingestion:
            date_start_str, date_end_str, embedder_costs = self._ingest_papers(start_date, end_date)

        total_cls_costs = 0.0
        total_sum_costs = 0.0
        total_processed = 0

        for page_id in self.notion_settings_extractor.query_database(self.notion_command_page_id):
            page_settings = self.notion_settings_extractor.extract_settings_from_page(page_id)
            if page_settings is None:
                logger.error(f"Invalid set of settings for {page_id}.")
                continue
            page_category = page_settings.get("Page Name", None)
            if category is not None and page_category is not None and page_category != category:
                continue

            cls_costs, sum_costs, count = self._process_category(
                category=page_category,
                settings=page_settings,
                date_start_str=date_start_str,
                date_end_str=date_end_str,
                top_k=top_k,
                use_classifier=use_classifier,
            )
            total_cls_costs += cls_costs
            total_sum_costs += sum_costs
            total_processed += count

        logger.info(f"Workflow costs: {total_cls_costs + total_sum_costs + embedder_costs}")
        logger.info(f"Workflow completed. Processed {total_processed} papers.")

    async def run_scheduled_job(self) -> None:
        """Wrapper for the scheduled job."""
        logger.info("Running scheduled daily paper workflow.")
        try:
            # Default behavior: run for today, looking back 4 days
            today = datetime.date.today()  # noqa: DTZ011
            start_date = today - datetime.timedelta(days=4)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: self.run_workflow(start_date=start_date, end_date=today))
        except Exception as exp:  # noqa: BLE001
            logger.error(f"Scheduled job failed: {exp}")
