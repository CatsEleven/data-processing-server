import boto3
import io
from datetime import datetime
from dotenv import load_dotenv
import os

# --- Cloudflare R2 Config ---
load_dotenv(".env")
R2_BUCKET_NAME = "rsnp2025"

s3 = boto3.client(
    service_name="s3",
    endpoint_url=os.getenv("R2_ENDPOINT"),
    aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("R2_ACCESS_KEY_SECRET"),
    region_name="apac",
)

def upload_mp4_bytes(mp4_bytes: bytes) -> str:
    """
    すでに RAM 上にある MP4 バイト列をそのままアップロードする。
    """
    buffer = io.BytesIO(mp4_bytes)
    buffer.seek(0)

    fileName = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".mp4"

    s3.upload_fileobj(
        buffer,
        R2_BUCKET_NAME,
        fileName,
        ExtraArgs={"ContentType": "video/mp4"}
    )

    return "https://r2.k-ota.com/" + fileName

