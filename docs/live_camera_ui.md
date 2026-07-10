# Live Camera UI

Run this on the main PC when you want to verify the multi-view camera rig before
recording or robot motion.

```bash
# Capture-PC camera daemons must already be up.
python src/camera/reset_cameras.py

# Start the browser monitor on the main PC.
python src/capture/camera/live_monitor.py --host 0.0.0.0 --port 8792
```

Open `http://<main-pc>:8792`.

## What Start Does

The **Start stream** button:

1. SSH-launches `python src/capture/camera/stream_client.py` on capture PCs.
2. Creates `remote_camera_controller("camera_live_monitor")`.
3. Runs `rcc.arm(syncMode=False, fps=10)`.
4. Turns on the stream sink with `rcc.set_stream(True)`.
5. Collects JPEG previews through `DataCollector` on port `1234`.

The preview is intentionally low resolution: `stream_client.py` downsamples each
camera image by 8x and publishes JPEG frames. Use it for framing, liveness, frame
ID progress, and daemon health. Use capture scripts for saved datasets.

## What Stop Does

The **Stop** button:

1. Stops the `remote_camera_controller` acquisition.
2. Closes the data collector.
3. Sends `exit` to the capture-PC stream clients through `CommandSender`.

Do this before closing the terminal so preview clients do not stay running on
capture PCs.

## Troubleshooting

If the UI starts but shows no frames:

- Check that `src/camera/server_daemon.py` is running on every capture PC.
- Run `python src/validate/data_sender/main.py` to verify the data return path.
- Run `python src/validate/camera_system/remote_camera_controller.py` to check
  daemon health and expected/detected camera counts.
- Use `--remote-log` to write remote stream-client logs to `test.log` on capture
  PCs.

Useful options:

```bash
python src/capture/camera/live_monitor.py \
  --host 0.0.0.0 \
  --port 8792 \
  --camera-fps 10 \
  --ui-fps 10 \
  --remote-log
```

Use `--pc capture1 --pc capture2` to restrict the monitor to specific capture PCs.
Use `--no-launch-clients` only if `stream_client.py` is already running.
