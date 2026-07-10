import argparse
import os
import sys
from multiprocessing import Manager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from paradex.video.raw_video_processor import undistort_raw_video


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Run the per-video raw upload worker on one .avi. "
            "The worker deletes the input file after a successful upload, "
            "so pass a copied validation clip unless deletion is intended."
        )
    )
    parser.add_argument("video_path", help="Path to one raw .avi file.")
    parser.add_argument("--video_id", default=None,
                        help="Progress key. Defaults to the video filename.")
    args = parser.parse_args()

    if not os.path.exists(args.video_path):
        raise FileNotFoundError(args.video_path)

    progress = Manager().dict()
    video_id = args.video_id or os.path.basename(args.video_path)
    result = undistort_raw_video(args.video_path, progress, video_id)
    print(result)
    print(dict(progress))
