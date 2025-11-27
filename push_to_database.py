import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import Client, create_client

# --- DATABASE Settings ---
load_dotenv('.env')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')


def push_to_database(latitude, longitude, speed, image_url):
    """指定された測定値を Supabase (PostGIS) に登録する."""

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    created_at = datetime.now(timezone.utc).isoformat()

    point_wkt = f"POINT({float(longitude)} {float(latitude)})"

    supabase.table("near-miss-log").insert(
        {
            "latitude": latitude,
            "longitude": longitude,
            "speed": speed,
            "imageUrl": image_url,
            "created_at": created_at,
            "postgis": point_wkt,
        }
    ).execute()
