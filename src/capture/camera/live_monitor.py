#!/usr/bin/env python3
"""Browser monitor for the distributed Paradex camera preview stream.

Run this on the main PC. The browser Start button launches the existing
capture-PC stream clients, arms camera acquisition through
``remote_camera_controller``, and displays per-camera JPEG preview tiles.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import ModuleType
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CLIENT_COMMAND = "python src/capture/camera/stream_client.py"


def load_cv_stack() -> tuple[ModuleType, ModuleType]:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV and NumPy are required. Activate the Paradex/FLIR conda "
            "environment before running live_monitor.py."
        ) from exc
    return cv2, np


def load_runtime_stack() -> tuple[Any, Any, Any, Any]:
    from paradex.io.camera_system.remote_camera_controller import remote_camera_controller
    from paradex.io.capture_pc.command_sender import CommandSender
    from paradex.io.capture_pc.data_sender import DataCollector
    from paradex.io.capture_pc.ssh import run_script

    return remote_camera_controller, CommandSender, DataCollector, run_script


HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Paradex Camera Monitor</title>
  <style>
    :root {
      --ink: #202225;
      --muted: #66717a;
      --paper: #ffffff;
      --soft: #f4f7f8;
      --line: #d9e2e7;
      --teal: #007c89;
      --teal-dark: #07545e;
      --green: #2f7d4f;
      --red: #b84d3b;
      --amber: #9d6508;
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--soft);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }
    button, input { font: inherit; }
    .app {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.9rem 1rem;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.94);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 2;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.7rem;
      min-width: 0;
      font-weight: 780;
    }
    .mark {
      display: grid;
      place-items: center;
      width: 2rem;
      height: 2rem;
      border-radius: 50%;
      color: #fff;
      background: var(--teal);
      flex: 0 0 auto;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.55rem;
      justify-content: flex-end;
    }
    .btn {
      min-height: 2.4rem;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--paper);
      color: var(--ink);
      padding: 0.45rem 0.8rem;
      font-weight: 720;
      cursor: pointer;
    }
    .btn.primary {
      color: #fff;
      background: var(--teal);
      border-color: var(--teal);
    }
    .btn.danger {
      color: #fff;
      background: var(--red);
      border-color: var(--red);
    }
    .btn:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    main {
      min-height: 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 0.9rem;
      padding: clamp(0.75rem, 1.6vw, 1.1rem);
    }
    .viewer {
      min-width: 0;
      min-height: 320px;
      height: clamp(320px, 68dvh, 760px);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #101820;
      overflow: hidden;
      display: grid;
      place-items: center;
      padding: 0.65rem;
      box-shadow: 0 14px 38px rgba(16, 24, 32, 0.16);
    }
    .camera-grid {
      width: 100%;
      height: 100%;
      min-width: 0;
      min-height: 0;
      display: grid;
      gap: 0.45rem;
    }
    .camera-tile {
      position: relative;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 6px;
      background: #0b1116;
    }
    .camera-tile img {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #0b1116;
    }
    .camera-label {
      position: absolute;
      top: 0.35rem;
      left: 0.35rem;
      max-width: calc(100% - 0.7rem);
      border-radius: 5px;
      padding: 0.16rem 0.35rem;
      color: #f8fbfc;
      background: rgba(10, 16, 20, 0.72);
      font-size: clamp(0.62rem, 0.8vw, 0.82rem);
      line-height: 1.2;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }
    aside {
      min-width: 0;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      align-content: start;
      gap: 0.85rem;
    }
    .panel {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--paper);
      padding: 0.9rem;
      box-shadow: 0 8px 24px rgba(31, 42, 55, 0.06);
    }
    .panel h2 {
      margin: 0 0 0.65rem;
      font-size: 1rem;
      letter-spacing: 0;
    }
    .panel-status {
      grid-column: span 2;
    }
    .panel-frames {
      grid-column: 1 / -1;
    }
    .status-line {
      display: grid;
      grid-template-columns: 6.4rem minmax(0, 1fr);
      gap: 0.5rem;
      padding: 0.36rem 0;
      border-top: 1px solid var(--line);
      font-size: 0.92rem;
    }
    .status-line:first-of-type { border-top: 0; }
    .label {
      color: var(--muted);
      font-weight: 720;
    }
    .value {
      min-width: 0;
      overflow-wrap: anywhere;
      font-variant-numeric: tabular-nums;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      min-height: 1.75rem;
      border-radius: 999px;
      padding: 0.16rem 0.55rem;
      color: var(--teal-dark);
      background: #e8f4f5;
      font-size: 0.84rem;
      font-weight: 780;
    }
    .chip.running {
      color: #fff;
      background: var(--green);
    }
    .chip.error {
      color: #fff;
      background: var(--red);
    }
    .chip.starting {
      color: #fff;
      background: var(--amber);
    }
    .list {
      display: grid;
      gap: 0.55rem;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .panel-frames .list {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      max-height: 250px;
      overflow: auto;
      padding-right: 0.2rem;
    }
    .panel-pcs .list {
      max-height: 250px;
      overflow: auto;
      padding-right: 0.2rem;
    }
    .item {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 0.55rem 0.6rem;
      background: #fbfcfd;
    }
    .item.warn {
      border-color: #e5be63;
      background: #fff8ea;
    }
    .item strong,
    .item span {
      display: block;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .item span {
      color: var(--muted);
      font-size: 0.86rem;
      margin-top: 0.12rem;
    }
    .error-text {
      color: var(--red);
      font-weight: 680;
    }
    code {
      background: #eef3f5;
      border-radius: 5px;
      padding: 0.08rem 0.3rem;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 0.9em;
    }
    @media (max-width: 980px) {
      aside {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .panel-status,
      .panel-frames {
        grid-column: 1 / -1;
      }
      .panel-frames .list {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 620px) {
      header {
        align-items: flex-start;
        flex-direction: column;
      }
      .actions,
      .btn {
        width: 100%;
      }
      .status-line {
        grid-template-columns: 1fr;
      }
      aside,
      .panel-status,
      .panel-frames {
        grid-template-columns: 1fr;
        grid-column: auto;
      }
      .viewer {
        height: clamp(240px, 54dvh, 480px);
        min-height: 240px;
        padding: 0.45rem;
      }
      .panel-frames .list {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand"><span class="mark">P</span><span>Paradex Camera Monitor</span></div>
      <div class="actions">
        <button id="start" class="btn primary" type="button">Start stream</button>
        <button id="stop" class="btn danger" type="button">Stop</button>
        <button id="refresh" class="btn" type="button">Refresh</button>
      </div>
    </header>

    <main>
      <section class="viewer" aria-label="Live camera preview grid">
        <div id="camera-grid" class="camera-grid"></div>
      </section>

      <aside>
        <section class="panel panel-status" aria-labelledby="status-title">
          <h2 id="status-title">Status</h2>
          <div class="status-line">
            <span class="label">State</span>
            <span class="value"><span id="state" class="chip">Idle</span></span>
          </div>
          <div class="status-line">
            <span class="label">Cameras</span>
            <span id="camera-count" class="value">0</span>
          </div>
          <div class="status-line">
            <span class="label">Last frame</span>
            <span id="last-frame" class="value">none</span>
          </div>
          <div class="status-line">
            <span class="label">FPS</span>
            <span id="fps" class="value">-</span>
          </div>
          <div class="status-line">
            <span class="label">Error</span>
            <span id="error" class="value">none</span>
          </div>
        </section>

        <section class="panel panel-pcs" aria-labelledby="pcs-title">
          <h2 id="pcs-title">Capture PCs</h2>
          <ul id="pcs" class="list"></ul>
        </section>

        <section class="panel panel-frames" aria-labelledby="frames-title">
          <h2 id="frames-title">Frames</h2>
          <ul id="frames" class="list"></ul>
        </section>

        <section class="panel panel-run" aria-labelledby="run-title">
          <h2 id="run-title">Run</h2>
          <div class="status-line">
            <span class="label">Daemons</span>
            <span class="value"><code>src/camera/server_daemon.py</code></span>
          </div>
          <div class="status-line">
            <span class="label">Client</span>
            <span class="value"><code>src/capture/camera/stream_client.py</code></span>
          </div>
          <div class="status-line">
            <span class="label">Preview</span>
            <span class="value">per-camera 1/8 JPEG</span>
          </div>
        </section>
      </aside>
    </main>
  </div>

  <script>
    const els = {
      start: document.getElementById("start"),
      stop: document.getElementById("stop"),
      refresh: document.getElementById("refresh"),
      state: document.getElementById("state"),
      cameraCount: document.getElementById("camera-count"),
      lastFrame: document.getElementById("last-frame"),
      fps: document.getElementById("fps"),
      error: document.getElementById("error"),
      pcs: document.getElementById("pcs"),
      frames: document.getElementById("frames"),
      cameraGrid: document.getElementById("camera-grid")
    };

    let busy = false;
    const cameraTiles = new Map();

    function ageText(seconds) {
      if (seconds === null || seconds === undefined) return "none";
      if (seconds < 1) return `${Math.round(seconds * 1000)} ms ago`;
      return `${seconds.toFixed(1)} s ago`;
    }

    function item(title, detail, tone = "") {
      const li = document.createElement("li");
      li.className = tone ? `item ${tone}` : "item";
      const strong = document.createElement("strong");
      const span = document.createElement("span");
      strong.textContent = title;
      span.textContent = detail;
      li.append(strong, span);
      return li;
    }

    function setList(node, rows, emptyText) {
      node.replaceChildren();
      if (!rows.length) {
        node.append(item(emptyText, ""));
        return;
      }
      rows.forEach(row => node.append(row));
    }

    function sortedFrameEntries(frames) {
      return Object.entries(frames || {}).sort(([a], [b]) => a.localeCompare(b, undefined, {numeric: true}));
    }

    function layoutCameraGrid(count) {
      if (!count) {
        els.cameraGrid.style.gridTemplateColumns = "1fr";
        els.cameraGrid.style.gridTemplateRows = "1fr";
        return;
      }
      const rect = els.cameraGrid.getBoundingClientRect();
      const gridAspect = Math.max(0.3, rect.width / Math.max(1, rect.height));
      const tileAspect = 4 / 3;
      let cols = Math.ceil(Math.sqrt(count * gridAspect / tileAspect));
      cols = Math.max(1, Math.min(count, cols));
      const rows = Math.ceil(count / cols);
      els.cameraGrid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
      els.cameraGrid.style.gridTemplateRows = `repeat(${rows}, minmax(0, 1fr))`;
    }

    function makeCameraTile(name) {
      const tile = document.createElement("div");
      tile.className = "camera-tile";
      tile.dataset.name = name;
      const img = document.createElement("img");
      img.alt = `${name} live preview`;
      img.src = `/camera.mjpg?name=${encodeURIComponent(name)}&t=${Date.now()}`;
      const label = document.createElement("div");
      label.className = "camera-label";
      label.textContent = name;
      tile.append(img, label);
      return {tile, img, label};
    }

    function syncCameraTiles(frames) {
      const entries = sortedFrameEntries(frames);
      const names = new Set(entries.map(([name]) => name));
      for (const [name, parts] of cameraTiles.entries()) {
        if (!names.has(name)) {
          parts.tile.remove();
          cameraTiles.delete(name);
        }
      }
      layoutCameraGrid(entries.length);
      for (const [name, frame] of entries) {
        let parts = cameraTiles.get(name);
        if (!parts) {
          parts = makeCameraTile(name);
          cameraTiles.set(name, parts);
        }
        els.cameraGrid.append(parts.tile);
        const age = frame.receive_age_ms === null ? "-" : `${Math.round(frame.receive_age_ms)} ms`;
        parts.label.textContent = `${name} · ${frame.pc || "pc?"} · ${age}`;
      }
      if (!entries.length) {
        els.cameraGrid.replaceChildren();
        cameraTiles.clear();
      }
    }

    function renderStatus(data) {
      const hasError = Boolean(data.error || data.rcc?.error);
      els.state.className = "chip";
      if (hasError) {
        els.state.classList.add("error");
        els.state.textContent = "Error";
      } else if (data.starting) {
        els.state.classList.add("starting");
        els.state.textContent = "Starting";
      } else if (data.running) {
        els.state.classList.add("running");
        els.state.textContent = "Streaming";
      } else {
        els.state.textContent = "Idle";
      }

      els.cameraCount.textContent = String(data.camera_count || 0);
      els.lastFrame.textContent = ageText(data.last_frame_age_sec);
      els.fps.textContent = data.config ? `${data.config.camera_fps} camera / ${data.config.ui_fps} UI` : "-";
      const errorText = data.error || (data.rcc?.error ? (data.rcc?.interrupt_msg || "camera status error") : "none");
      els.error.textContent = errorText;
      els.error.className = errorText === "none" ? "value" : "value error-text";

      const pcRows = Object.entries(data.rcc?.pc || {}).map(([pc, status]) => {
        const state = status.status || "unknown";
        const msg = status.msg || `detected ${status.detected_camera_count ?? "-"} / expected ${status.expected_camera_count ?? "-"}`;
        return item(pc, `${state}: ${msg}`, state === "ok" ? "" : "warn");
      });
      setList(els.pcs, pcRows, "No daemon status");

      syncCameraTiles(data.frames || {});

      const frameRows = sortedFrameEntries(data.frames || {}).map(([name, frame]) => {
        const age = frame.receive_age_ms === null ? "-" : `${Math.round(frame.receive_age_ms)} ms`;
        const tone = Number(frame.receive_age_ms || 0) > 1000 ? "warn" : "";
        return item(name, `fid ${frame.frame_id} · ${frame.pc || "pc?"} · seq ${frame.seq ?? "-"} · shown age ${age}`, tone);
      });
      setList(els.frames, frameRows, "No frames yet");

      els.start.disabled = busy || data.running || data.starting;
      els.stop.disabled = busy || (!data.running && !data.starting);
    }

    async function refresh() {
      try {
        const res = await fetch("/api/status", {cache: "no-store"});
        renderStatus(await res.json());
      } catch (err) {
        renderStatus({error: String(err), running: false, starting: false});
      }
    }

    async function post(path) {
      busy = true;
      await refresh();
      try {
        const res = await fetch(path, {method: "POST"});
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || res.statusText);
        renderStatus(data);
      } catch (err) {
        renderStatus({error: String(err), running: false, starting: false});
      } finally {
        busy = false;
        await refresh();
      }
    }

    els.start.addEventListener("click", () => post("/api/start"));
    els.stop.addEventListener("click", () => post("/api/stop"));
    els.refresh.addEventListener("click", refresh);
    window.addEventListener("resize", () => layoutCameraGrid(cameraTiles.size));
    refresh();
    setInterval(refresh, 500);
  </script>
</body>
</html>
"""


class CameraMonitor:
    def __init__(
        self,
        *,
        pc_list: list[str] | None,
        camera_fps: int,
        ui_fps: int,
        jpeg_quality: int,
        launch_clients: bool,
        client_command: str,
        remote_log: bool,
        command_timeout_ms: int,
        command_retries: int,
    ) -> None:
        self.pc_list = pc_list
        self.camera_fps = camera_fps
        self.ui_fps = max(1, ui_fps)
        self.jpeg_quality = max(1, min(100, int(jpeg_quality)))
        self.launch_clients = launch_clients
        self.client_command = client_command
        self.remote_log = remote_log
        self.command_timeout_ms = command_timeout_ms
        self.command_retries = command_retries
        self.cv2, self.np = load_cv_stack()

        self.lifecycle_lock = threading.RLock()
        self.frame_cond = threading.Condition()
        self.collect_stop = threading.Event()

        self.rcc: Any | None = None
        self.dc: Any | None = None
        self.cs: Any | None = None
        self.collect_thread: threading.Thread | None = None

        self.running = False
        self.starting = False
        self.error: str | None = None
        self.camera_jpegs: dict[str, bytes] = {}
        self.camera_versions: dict[str, int] = {}
        self.global_version = 0
        self.last_frame_time: float | None = None
        self.frames: dict[str, dict[str, Any]] = {}
        self.frame_seen_at: dict[str, float] = {}
        self.frame_versions: dict[str, tuple[int | None, int | None]] = {}
        self.placeholder_jpeg = self._make_placeholder("Click Start stream")

    def start(self) -> dict[str, Any]:
        with self.lifecycle_lock:
            if self.running or self.starting:
                return self.status()
            self.starting = True
            self.error = None

        try:
            remote_camera_controller, CommandSender, DataCollector, run_script = load_runtime_stack()
            if self.launch_clients:
                run_script(self.client_command, pc_list=self.pc_list, log=self.remote_log)

            rcc = remote_camera_controller("camera_live_monitor", pc_list=self.pc_list)
            dc = DataCollector(pc_list=self.pc_list)
            dc.start()
            cs = CommandSender(
                pc_list=self.pc_list,
                timeout=self.command_timeout_ms,
                retries=self.command_retries,
            )

            rcc.arm(syncMode=False, fps=self.camera_fps)
            rcc.set_stream(True)

            with self.lifecycle_lock:
                self.rcc = rcc
                self.dc = dc
                self.cs = cs
                self.collect_stop.clear()
                self.running = True
                self.starting = False
                self.camera_jpegs = {}
                self.camera_versions = {}
                self.global_version = 0
                self.last_frame_time = None
                self.frames = {}
                self.frame_seen_at = {}
                self.frame_versions = {}
                self.collect_thread = threading.Thread(
                    target=self._collect_loop,
                    name="camera-live-monitor-collector",
                    daemon=True,
                )
                self.collect_thread.start()
            return self.status()
        except Exception as exc:
            with self.lifecycle_lock:
                self.error = str(exc)
                self.starting = False
            self._cleanup_handles(locals().get("rcc"), locals().get("dc"), locals().get("cs"))
            return self.status()

    def stop(self) -> dict[str, Any]:
        with self.lifecycle_lock:
            rcc, dc, cs = self.rcc, self.dc, self.cs
            thread = self.collect_thread
            self.running = False
            self.starting = False
            self.rcc = None
            self.dc = None
            self.cs = None
            self.collect_thread = None
            self.collect_stop.set()

        if thread is not None:
            thread.join(timeout=2)
        self._cleanup_handles(rcc, dc, cs)
        with self.frame_cond:
            self.camera_jpegs = {}
            self.camera_versions = {}
            self.global_version = 0
            self.last_frame_time = None
            self.frames = {}
            self.frame_seen_at = {}
            self.frame_versions = {}
            self.frame_cond.notify_all()
        return self.status()

    def shutdown(self) -> None:
        self.stop()

    def wait_for_camera_jpeg(
        self,
        name: str,
        after_version: int = 0,
        timeout: float = 1.0,
    ) -> tuple[bytes, int]:
        with self.frame_cond:
            self.frame_cond.wait_for(
                lambda: self.camera_versions.get(name, 0) > after_version,
                timeout=timeout,
            )
            version = self.camera_versions.get(name, 0)
            return self.camera_jpegs.get(name, self.placeholder_jpeg), version

    def status(self) -> dict[str, Any]:
        with self.lifecycle_lock:
            rcc = self.rcc
            dc = self.dc
            running = self.running
            starting = self.starting
            error = self.error
        rcc_status: dict[str, Any] = {}
        collector_stats: dict[str, Any] = {}
        if rcc is not None:
            try:
                rcc_status = rcc.get_status()
            except Exception as exc:
                rcc_status = {"error": True, "pc": {}, "interrupt_msg": str(exc)}
        if dc is not None:
            try:
                collector_stats = dc.get_stats()
            except Exception:
                collector_stats = {}

        now = time.time()
        with self.frame_cond:
            frames = {}
            for name, meta in self.frames.items():
                item = dict(meta)
                seen_at = self.frame_seen_at.get(name)
                item["receive_age_ms"] = None if seen_at is None else max(0.0, (now - seen_at) * 1000.0)
                frames[name] = item
            last_frame_age = (
                None if self.last_frame_time is None else max(0.0, now - self.last_frame_time)
            )

        return {
            "running": running,
            "starting": starting,
            "error": error,
            "camera_count": len(frames),
            "last_frame_age_sec": last_frame_age,
            "frames": frames,
            "rcc": rcc_status,
            "collector_stats": collector_stats,
            "config": {
                "camera_fps": self.camera_fps,
                "ui_fps": self.ui_fps,
                "jpeg_quality": self.jpeg_quality,
                "launch_clients": self.launch_clients,
            },
        }

    def _collect_loop(self) -> None:
        assert self.dc is not None
        poll_hz = max(self.ui_fps, self.camera_fps * 2, 20)
        period = 1.0 / poll_hz
        while not self.collect_stop.is_set():
            started = time.monotonic()
            try:
                all_data = self.dc.get_data()
                now = time.time()
                with self.frame_cond:
                    frames = dict(self.frames)
                    frame_seen_at = dict(self.frame_seen_at)
                    frame_versions = dict(self.frame_versions)
                    camera_jpegs = dict(self.camera_jpegs)
                    camera_versions = dict(self.camera_versions)
                    global_version = self.global_version

                for item_name, item_data in sorted(all_data.items()):
                    if item_data.get("type") != "image":
                        continue
                    image_bytes = item_data.get("data")
                    if not image_bytes:
                        continue

                    name = str(item_name)
                    frame_id = self._as_int(item_data.get("frame_id"), 0)
                    seq = self._as_int(item_data.get("seq"), None)
                    version = (frame_id, seq)
                    if frame_versions.get(name) != version:
                        frame_versions[name] = version
                        frame_seen_at[name] = now
                        camera_jpegs[name] = image_bytes
                        camera_versions[name] = camera_versions.get(name, 0) + 1
                        global_version += 1

                    frames[name] = {
                        "frame_id": frame_id,
                        "pc": str(item_data.get("pc", "")),
                        "src": str(item_data.get("src", "")),
                        "seq": seq,
                    }

                if frames:
                    with self.frame_cond:
                        self.camera_jpegs = {name: jpeg for name, jpeg in camera_jpegs.items() if name in frames}
                        self.camera_versions = {
                            name: version for name, version in camera_versions.items() if name in frames
                        }
                        self.global_version = global_version
                        self.last_frame_time = now
                        self.frames = frames
                        self.frame_seen_at = {
                            name: seen_at for name, seen_at in frame_seen_at.items() if name in frames
                        }
                        self.frame_versions = {
                            name: version for name, version in frame_versions.items() if name in frames
                        }
                        self.frame_cond.notify_all()
            except Exception as exc:
                with self.lifecycle_lock:
                    self.error = str(exc)
            elapsed = time.monotonic() - started
            self.collect_stop.wait(max(0.0, period - elapsed))

    def _cleanup_handles(
        self,
        rcc: Any | None,
        dc: Any | None,
        cs: Any | None,
    ) -> None:
        for label, func in (
            ("rcc.stop", lambda: rcc.stop() if rcc is not None else None),
            ("rcc.end", lambda: rcc.end() if rcc is not None else None),
            ("dc.end", lambda: dc.end() if dc is not None else None),
            ("cs.end", lambda: cs.end() if cs is not None else None),
        ):
            try:
                func()
            except Exception as exc:
                print(f"[camera-live-monitor] {label} failed: {exc}", file=sys.stderr)

    @staticmethod
    def _as_int(value: Any, default: int | None) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _make_placeholder(self, message: str) -> bytes:
        image = self.np.full((720, 1280, 3), (247, 250, 251), dtype=self.np.uint8)
        self.cv2.rectangle(image, (40, 40), (1240, 680), (219, 226, 231), 2)
        self.cv2.putText(
            image,
            "Paradex Camera Monitor",
            (72, 330),
            self.cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (32, 34, 37),
            3,
            self.cv2.LINE_AA,
        )
        self.cv2.putText(
            image,
            message,
            (76, 385),
            self.cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (95, 105, 114),
            2,
            self.cv2.LINE_AA,
        )
        ok, encoded = self.cv2.imencode(".jpg", image, [int(self.cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            return b""
        return encoded.tobytes()


class CameraMonitorServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], monitor: CameraMonitor):
        super().__init__(server_address, CameraMonitorHandler)
        self.monitor = monitor


class CameraMonitorHandler(BaseHTTPRequestHandler):
    server: CameraMonitorServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            self._send_html(HTML)
        elif path == "/api/status":
            self._send_json(self.server.monitor.status())
        elif path == "/camera.mjpg":
            params = parse_qs(parsed.query)
            name = (params.get("name") or [""])[0]
            self._send_camera_mjpeg(name)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/start":
            status = self.server.monitor.start()
            code = HTTPStatus.INTERNAL_SERVER_ERROR if status.get("error") else HTTPStatus.OK
            self._send_json(status, code)
        elif path == "/api/stop":
            self._send_json(self.server.monitor.stop())
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[camera-live-monitor] {self.address_string()} - {fmt % args}")

    def _send_html(self, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, body: dict[str, Any], code: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_camera_mjpeg(self, name: str) -> None:
        if not name:
            self.send_error(HTTPStatus.BAD_REQUEST, "missing camera name")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        last_version = 0
        while True:
            try:
                jpeg, last_version = self.server.monitor.wait_for_camera_jpeg(
                    name,
                    after_version=last_version,
                    timeout=2.0,
                )
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii"))
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve a browser UI for the distributed Paradex multi-camera preview.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP bind host.")
    parser.add_argument("--port", type=int, default=8792, help="HTTP bind port.")
    parser.add_argument("--pc", action="append", dest="pcs", help="Capture PC name. Repeat to override system/current.")
    parser.add_argument("--camera-fps", type=int, default=15, help="Camera acquisition FPS for preview.")
    parser.add_argument("--ui-fps", type=int, default=30, help="Status/collector refresh rate.")
    parser.add_argument("--jpeg-quality", type=int, default=65, help="Default stream_client JPEG quality, 1-100.")
    parser.add_argument("--auto-start", action="store_true", help="Start streaming when the server boots.")
    parser.add_argument("--no-launch-clients", action="store_true", help="Assume stream_client.py is already running.")
    parser.add_argument("--remote-log", action="store_true", help="Write remote stream_client output to test.log.")
    parser.add_argument(
        "--client-command",
        default=DEFAULT_CLIENT_COMMAND,
        help="Command SSH-launched on capture PCs.",
    )
    parser.add_argument("--command-timeout-ms", type=int, default=2000, help="Stop-command timeout per capture PC.")
    parser.add_argument("--command-retries", type=int, default=1, help="Stop-command retries per capture PC.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client_command = args.client_command
    if client_command == DEFAULT_CLIENT_COMMAND:
        client_command = f"{DEFAULT_CLIENT_COMMAND} --jpeg-quality {args.jpeg_quality}"
    monitor = CameraMonitor(
        pc_list=args.pcs,
        camera_fps=args.camera_fps,
        ui_fps=args.ui_fps,
        jpeg_quality=args.jpeg_quality,
        launch_clients=not args.no_launch_clients,
        client_command=client_command,
        remote_log=args.remote_log,
        command_timeout_ms=args.command_timeout_ms,
        command_retries=args.command_retries,
    )
    server = CameraMonitorServer((args.host, args.port), monitor)
    print(f"[camera-live-monitor] open http://{args.host}:{args.port}")
    if args.auto_start:
        threading.Thread(target=monitor.start, name="camera-live-monitor-autostart", daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\n[camera-live-monitor] stopping")
    finally:
        server.server_close()
        monitor.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
