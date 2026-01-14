"""Provide a class for uploading images to S3."""

import mimetypes
import urllib.parse

import boto3
from botocore.config import Config

from src.settings import settings


class S3Uploader:
    """Handle uploading files to an S3-compatible storage.

    Attributes:
        s3_client (boto3.client): The boto3 S3 client instance.
    """

    def __init__(self, folder: str = "reports") -> None:
        """Initialize the S3Uploader with credentials from environment variables.

        Args:
            folder (str): Folder to upload the files to.
        """
        aws_access_key_id = settings.aws_access_key_id
        aws_secret_access_key = settings.aws_secret_access_key
        endpoint_url = settings.endpoint_url
        self.bucket = settings.s3_bucket
        self.folder = folder

        session = boto3.session.Session()  # type: ignore
        config = Config(request_checksum_calculation="when_required")
        self.s3_client = session.client(
            service_name="s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            endpoint_url=endpoint_url,
            config=config,
        )

    def get_public_url(self, s3_key: str) -> str:
        """Generate the public URL for a file in the S3 bucket.

        Args:
            s3_key (str): S3 key (path) of the file in the bucket.

        Example of the public URL:
        https://rndml-team-layer.obs.ru-moscow-1.hc.sbercloud.ru:443/reports/figure_2.jpg

        Returns:
            str: Public URL of the file.
        """
        endpoint_url = settings.endpoint_url.removeprefix("https://")
        encoded_key = urllib.parse.quote(s3_key, safe="/")
        return f"https://{self.bucket}.{endpoint_url}:443/{encoded_key}"

    def upload_file(self, local_path: str, s3_key: str) -> str:
        """Upload a single file to the specified S3 bucket and make it public.

        Args:
            local_path (str): Path to the local file.
            s3_key (str): S3 key (path) where the file will be uploaded.

        Returns:
            str: Public URL of the uploaded file.
        """
        s3_key = f"{self.folder}/{s3_key}"
        extra_args = {"ACL": "public-read"}
        content_type, _ = mimetypes.guess_type(local_path)
        if not content_type:
            # Fallback for common images if mimetypes fails
            if local_path.lower().endswith((".jpg", ".jpeg")):
                content_type = "image/jpeg"
            elif local_path.lower().endswith(".png"):
                content_type = "image/png"
        if content_type:
            extra_args["ContentType"] = content_type

        self.s3_client.upload_file(local_path, self.bucket, s3_key, ExtraArgs=extra_args)
        return self.get_public_url(s3_key)
