import argparse
import time
import cv2
from threading import Event

from paradex.io.camera_system.camera_reader import MultiCameraReader
from paradex.io.capture_pc.data_sender import DataPublisher
from paradex.io.capture_pc.command_sender import CommandReceiver


def parse_args():
    parser = argparse.ArgumentParser(description="Publish low-latency multi-camera preview JPEGs.")
    parser.add_argument("--scale-divisor", type=int, default=8, help="Downscale divisor before JPEG encoding.")
    parser.add_argument("--jpeg-quality", type=int, default=65, help="Preview JPEG quality, 1-100.")
    parser.add_argument("--poll-sleep", type=float, default=0.003, help="Loop sleep in seconds.")
    return parser.parse_args()


args = parse_args()
scale_divisor = max(1, int(args.scale_divisor))
jpeg_quality = max(1, min(100, int(args.jpeg_quality)))
poll_sleep = max(0.0, float(args.poll_sleep))

# Initialize components
dp = DataPublisher(port=1234, name="camera_stream")
exit_event = Event()
cr = CommandReceiver(event_dict={"exit": exit_event}, port=6890)

# Initialize multi-camera reader
reader = MultiCameraReader()

last_frame_ids = {name: 0 for name in reader.camera_names}

while not exit_event.is_set():
    # Match calibration preview clients: read the latest shared-memory buffer
    # directly and only allocate the downscaled JPEG preview.
    images_data = reader.get_images(copy=False)

    for camera_name, (image, frame_id) in images_data.items():
        # Only send if we have a new frame
        if frame_id > last_frame_ids[camera_name] and frame_id > 0:
            if scale_divisor > 1:
                image = cv2.resize(
                    image,
                    (
                        max(1, image.shape[1] // scale_divisor),
                        max(1, image.shape[0] // scale_divisor),
                    ),
                    interpolation=cv2.INTER_AREA,
                )
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
            success, encoded_image = cv2.imencode(".jpg", image, encode_param)
            
            if success:
                dp.send_data(
                    {
                        "type": "image",
                        "name": camera_name,
                        "frame_id": int(frame_id),
                        "shape": tuple(int(x) for x in image.shape),
                    },
                    [encoded_image],
                )
                last_frame_ids[camera_name] = frame_id

    if poll_sleep:
        time.sleep(poll_sleep)

# Cleanup
reader.close()
dp.close()
cr.end()
print("Camera streaming client stopped.")
