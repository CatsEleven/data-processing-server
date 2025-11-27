from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from yolo_sam_segmentation import process_images_to_masked_video
from upload_storage import upload_mp4_bytes
from push_to_database import push_to_database

load_dotenv(".env")

# ---------- Config ----------
BROKER_ADDRESS = os.getenv("MQTT_BROKER", "broker.hivemq.com")
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC_BINARY = os.getenv("MQTT_TOPIC_BINARY", "binaryChunks")
TOPIC_TELEMETRY = os.getenv("MQTT_TOPIC_TELEMETRY", "telemetry/data")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "received_images"))
ARCHIVE_DIR = Path(os.getenv("ARCHIVE_DIR", "processed_images"))
INACTIVITY_SECONDS = int(os.getenv("INACTIVITY_SECONDS", "5"))

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("pipeline")

# ---------- State ----------
chunk_buffer: Dict[str, Dict] = {}
latest_telemetry: Optional[Dict] = None
last_chunk_at: Optional[float] = None
processing_lock = threading.Lock()
processing_in_progress = False
running = True

# ---------- Helpers ----------
def ensure_dirs():
    OUTPUT_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True)
    # movies dir is created inside step04 if needed


# ---------- MQTT Handlers ----------
def handle_binary_chunk(payload: bytes):
    global last_chunk_at

    header_raw, chunk_bytes = payload.split(b"\n", 1)
    header = json.loads(header_raw.decode("utf-8"))

    message_id = header["message_id"]
    filename = header["filename"]
    idx = header["chunk_index"]
    total = header["total_chunks"]

    if message_id not in chunk_buffer:
        chunk_buffer[message_id] = {"filename": filename, "total": total, "chunks": {}}

    chunk_buffer[message_id]["chunks"][idx] = chunk_bytes
    logger.info("Chunk %s/%s received for %s", idx + 1, total, filename)

    if len(chunk_buffer[message_id]["chunks"]) == total:
        save_path = OUTPUT_DIR / filename
        with open(save_path, "wb") as f:
            for i in range(total):
                f.write(chunk_buffer[message_id]["chunks"][i])
        logger.info("Reassembled %s", save_path)
        del chunk_buffer[message_id]

    last_chunk_at = time.time()


def handle_telemetry(payload: bytes):
    global latest_telemetry
    latest_telemetry = json.loads(payload.decode("utf-8"))
    logger.info("Telemetry updated: %s", latest_telemetry)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker")
        client.subscribe(TOPIC_BINARY)
        client.subscribe(TOPIC_TELEMETRY)
    else:
        logger.error("Failed to connect: rc=%s", rc)


def on_message(client, userdata, msg):
    if msg.topic == TOPIC_BINARY:
        handle_binary_chunk(msg.payload)
    elif msg.topic == TOPIC_TELEMETRY:
        handle_telemetry(msg.payload)


def archive_images(image_paths: List[Path]):
    if not image_paths:
        return
    ts_dir = ARCHIVE_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_dir.mkdir(parents=True, exist_ok=True)
    for p in image_paths:
        shutil.move(str(p), ts_dir / p.name)
    logger.info("Archived %s images to %s", len(image_paths), ts_dir)


# ---------- Orchestration ----------
def collect_images() -> List[Path]:
    return sorted(OUTPUT_DIR.glob("*.png"), key=lambda p: p.stem)


def process_batch():
    global processing_in_progress, last_chunk_at
    with processing_lock:
        if processing_in_progress:
            return
        processing_in_progress = True

    try:
        image_paths = collect_images()
        if not image_paths:
            return

        telemetry_snapshot = latest_telemetry.copy() if latest_telemetry else None

        # Build video using the existing segmentation script
        video_path = Path(process_images_to_masked_video())

        # Upload using existing R2 helper (expects bytes)
        with open(video_path, "rb") as f:
            video_bytes = f.read()
        video_url = upload_mp4_bytes(video_bytes)

        # Insert into Supabase using existing helper
        if telemetry_snapshot:
            push_to_database(
                telemetry_snapshot.get("latitude"),
                telemetry_snapshot.get("longitude"),
                telemetry_snapshot.get("speed"),
                video_url,
            )
        else:
            # If no telemetry, still insert minimal record
            push_to_database(None, None, None, video_url)

        archive_images(image_paths)

        last_chunk_at = None
    finally:
        processing_in_progress = False


def inactivity_watcher():
    while running:
        time.sleep(1)
        if last_chunk_at and (time.time() - last_chunk_at) >= INACTIVITY_SECONDS:
            logger.info("No new chunks for %ss -> processing batch.", INACTIVITY_SECONDS)
            process_batch()


def main():
    ensure_dirs()

    client = mqtt.Client(
        client_id="python_end_to_end",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
    )
    client.on_connect = on_connect
    client.on_message = on_message

    watcher = threading.Thread(target=inactivity_watcher, daemon=True)
    watcher.start()

    logger.info("Connecting to MQTT %s:%s", BROKER_ADDRESS, BROKER_PORT)
    client.connect(BROKER_ADDRESS, BROKER_PORT, 60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        global running
        running = False
        client.disconnect()
        process_batch()  # final flush


if __name__ == "__main__":
    main()
