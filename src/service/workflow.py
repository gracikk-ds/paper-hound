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
        notion_settings_db_ids: dict[str, str],
        threshold: float = 0.65,
    ) -> None:
        """Initialize the WorkflowService.

        Args:
            processor (PapersProcessor): Service for processing papers.
            classifier (Classifier): Service for classifying papers.
            summarizer (Summarizer): Service for summarizing papers.
            arxiv_fetcher (ArxivFetcher): Service for fetching papers from ArXiv.
            notion_uploader (MarkdownToNotionUploader): Service for uploading to Notion.
            notion_settings_db_ids (dict[str, str]): The IDs of the Notion settings databases.
            notion_settings_extractor (NotionPageExtractor): Service for extracting settings from Notion pages.
            threshold (float): The threshold for the similarity score.
        """
        self.threshold = threshold
        self.processor = processor
        self.classifier = classifier
        self.summarizer = summarizer
        self.arxiv_fetcher = arxiv_fetcher
        self.notion_uploader = notion_uploader
        self.notion_settings_extractor = notion_settings_extractor
        self.notion_settings_db_ids = notion_settings_db_ids

    def process_paper_summary_and_upload(
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

    def daily_ingestion(
        self,
        date: datetime.date | None = None,
        num_days_to_look_back: int = 4,
    ) -> tuple[str, str, float]:
        """Ingest papers for a given date range.

        We look back num_days_to_look_back days to ensure no papers are missed due to arxiv api delay.
        If the papers were already ingested for previous days, we won't ingest them again, just skip them.

        Args:
            date (datetime.date | None): The date to ingest papers for. Defaults to yesterday.
            num_days_to_look_back (int): The number of days to look back. Defaults to 4.

        Returns:
            tuple[str, str, float]: The start date string, end date string and the costs of the embedding service.
        """
        current_date = date or datetime.date.today()  # noqa: DTZ011
        current_date_str = current_date.strftime("%Y-%m-%d")
        start_date = current_date - datetime.timedelta(days=num_days_to_look_back)

        logger.info(f"Starting ingestion for {current_date_str}, but looking back {num_days_to_look_back} days.")

        # 1. Ingest papers
        try:
            updated_start_date_str, costs = self.processor.insert_papers(start_date, current_date)
        except Exception as exp:  # noqa: BLE001
            logger.error(f"Error inserting papers for {current_date_str}: {exp}")
        return updated_start_date_str, current_date_str, costs

    def process_daily_cycle(self, date: datetime.date | None = None, top_k: int = 10) -> None:
        """Run the daily paper processing cycle.

        Args:
            date (datetime.date | None): The date to process. Defaults to yesterday.
            top_k (int): The number of papers to return. Defaults to 10.
        """
        # 1. Ingest papers
        date_start_str, date_end_str, embedder_costs = self.daily_ingestion(date)
        for category, page_id in self.notion_settings_db_ids.items():
            settings = self.notion_settings_extractor.extract_settings_from_page(page_id)
            if settings is None:
                logger.error(f"Invalid set of settings for {category}.")
                continue

            # 2. Search for relevant papers
            query = settings["Query Prompt"]
            try:
                # Note: search_papers expects string dates
                candidates = self.processor.search_papers(
                    query=query,
                    k=top_k,
                    threshold=self.threshold,
                    start_date_str=date_start_str,
                    end_date_str=date_end_str,
                )
            except Exception as exp:  # noqa: BLE001
                logger.error(f"Error searching papers: {exp}")
                return
            logger.info(f"Found {len(candidates)} candidates for '{query}' on {date_end_str}")

            # 3. Filter and Process
            processed_count = 0
            cls_costs = 0.0
            sum_costs = 0.0
            for paper in candidates:
                try:
                    is_relevant = self.classifier.classify(
                        title=paper.title,
                        summary=paper.summary,
                        system_prompt=settings["Classifier Prompt"],
                    )
                    cls_costs += self.classifier.inference_price

                    if is_relevant:
                        logger.info(f"Paper '{paper.title}' classified as relevant. Processing...")
                        url = self.process_paper_summary_and_upload(
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

        logger.info(f"Daily cycle costs: {cls_costs + sum_costs + embedder_costs}")
        logger.info("Daily cycle completed.")

    async def run_scheduled_job(self) -> None:
        """Wrapper for the scheduled job."""
        logger.info("Running scheduled daily paper workflow.")
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.process_daily_cycle)
        except Exception as exp:  # noqa: BLE001
            logger.error(f"Scheduled job failed: {exp}")
