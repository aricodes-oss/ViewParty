import asyncio
import argparse
import os
import random
import subprocess
import tempfile
import datetime
from time import sleep

from twitchio import Client
from yt_dlp import YoutubeDL

STREAM_KEY = os.environ.get("STREAM_KEY")
TWITCH_TOKEN = os.environ.get("TWITCH_TOKEN")

# Corresponds to --get-url - https://github.com/yt-dlp/yt-dlp/blob/master/devscripts/cli_to_api.py
YDL_ARGS = {
    "extract_flat": "discard_in_playlist",
    "forceurl": True,
    "fragment_retries": 10,
    "ignoreerrors": "only_download",
    "noprogress": True,
    "postprocessors": [{"key": "FFmpegConcat", "only_multi_video": True, "when": "playlist"}],
    "quiet": True,
    "retries": 10,
    "simulate": True,
}


async def _main(args):
    assert all([val is not None for val in [STREAM_KEY, TWITCH_TOKEN]])

    client = Client(TWITCH_TOKEN)
    user_id = (await client.fetch_users(names=[args.username]))[0].id

    videos = list(
        filter(
            lambda vid: "speedrun" in vid.title.lower()
            and vid.published_at > datetime.datetime(2020, 1, 1).astimezone(),
            await client.fetch_videos(user_id=user_id, type="highlight"),
        )
    )
    # Take a sampling of these videos and create a playlist file out of them
    videos = random.choices(videos, k=10)
    with YoutubeDL(YDL_ARGS) as ydl:
        # Map all the videos to their URLs
        videos = [ydl.extract_info(video.url)["url"] for video in videos]

    playlist_file = tempfile.NamedTemporaryFile("w", delete=False)
    playlist_file.write("\n".join([f"file '{url}'" for url in videos]))
    playlist_file.close()

    stream = subprocess.Popen(
        [
            "ffmpeg",
            "-re",  # Playback in real time (useful for livestreaming, prevents skips)
            "-safe",
            "0",  # Accept HTTP streams
            "-protocol_whitelist",
            "file,http,https,tcp,tls",  # Expand protocol whitelist to accept web streams
            "-i",
            playlist_file.name,
            "-codec",
            "copy",  # Copy the audio and video unmodified
            "-f",
            "flv",  # Output to FLV (required for RTMP)
            "-b:v",
            "6M",  # Sets the video bitrate (max twitch supports)
            "-b:a",
            "48k",  # AssertionErrorets audio bitrate (max twitch supports)
            "-reconnect_streamed",  # Reconnect on stream error
            "1",
            "-reconnect_on_network_error",  # Reconnect on network error
            "1",
            "-drop_pkts_on_overflow",
            "1",
            "-attempt_recovery",
            "1",
            "-recover_any_error",
            "1",
            f"{args.rtmp_server}/{STREAM_KEY}",  # Actual RTMP target
        ]
    )
    return_code = stream.wait()
    os.remove(playlist_file.name)

    # Reboot immediately with no delay on failure
    if return_code != 0:
        return
    # Otherwise give the RTMP feed time to go down on Twitch's side before rebooting
    sleep(120)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rtmp-server",
        "-O",
        type=str,
        default="rtmp://ingest.global-contribute.live-video.net/app",
        help="RTMP server to output to (defaults to Twitch)",
    )
    parser.add_argument(
        "--memory-length",
        "-m",
        type=int,
        default=20,
        help="Number of recently watched videos to keep track of",
    )
    parser.add_argument("username", type=str, help="Username to pull highlights from")
    args = parser.parse_args()

    asyncio.run(_main(args))
