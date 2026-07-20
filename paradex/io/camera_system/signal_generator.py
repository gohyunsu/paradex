"""USBTMC control for the UTG900E hardware trigger generator."""

import os
import time


class UTGE900:
    """Configure and switch UTG900E channel outputs through SCPI.

    The previous implementation replayed front-panel key presses. Direct SCPI is
    deterministic and keeps the trigger output disabled until configuration is
    complete.
    """

    _WAVES = {"sine": "SINe", "square": "SQUare", "pulse": "PULSe", "ramp": "RAMP"}

    def __init__(self, addr):
        self.device = addr
        if not os.path.exists(addr):
            raise FileNotFoundError(f"Device {addr} not found")
        if not os.access(addr, os.R_OK | os.W_OK):
            raise PermissionError(f"No permission for {addr}. Run: sudo chmod 666 {addr}")
        self.ch = [False, False]

    def write(self, command):
        """Send one newline-terminated SCPI command."""
        with open(self.device, "wb") as device:
            device.write((command + "\n").encode("ascii"))
            device.flush()

    def query(self, command, strip=False):
        """Send a SCPI query and return its response."""
        with open(self.device, "w+b", buffering=0) as device:
            device.write((command + "\n").encode("ascii"))
            time.sleep(0.05)
            response = device.read(4096).decode("ascii").strip()
        return response.rstrip() if strip else response

    @staticmethod
    def _channel(ch):
        ch = int(ch)
        if ch not in (1, 2):
            raise ValueError(f"UTG900E channel must be 1 or 2, got {ch}")
        return ch

    def generate(self, ch=1, wave="square", freq=30, amp=5, offset=0):
        """Configure a continuous waveform while keeping its output disabled."""
        ch = self._channel(ch)
        try:
            wave = self._WAVES[wave.lower()]
        except KeyError as exc:
            raise ValueError(f"Unsupported UTG900E waveform: {wave}") from exc

        prefix = f":CHANnel{ch}"
        self.write(f"{prefix}:OUTPut OFF")
        self.write(f"{prefix}:MODe CONTinue")
        self.write(f"{prefix}:BASE:WAVe {wave}")
        self.write(f"{prefix}:BASE:FREQuency {freq}")
        self.write(f"{prefix}:AMPLitude:UNIT VPP")
        self.write(f"{prefix}:BASE:AMPLitude {amp}")
        self.write(f"{prefix}:BASE:OFFSet {offset}")
        if wave == "SQUare":
            self.write(f"{prefix}:BASE:DUTY 50")

    def start(self, fps, ch=1):
        """Configure a 0-5 V square trigger and enable its channel output."""
        ch = self._channel(ch)
        if self.ch[ch - 1]:
            return
        self.generate(ch, wave="square", freq=fps, amp=5, offset=2.5)
        self.write(f":CHANnel{ch}:OUTPut ON")
        self.ch[ch - 1] = True

    def stop(self, ch=1):
        """Disable a channel output without changing its waveform settings."""
        ch = self._channel(ch)
        if not self.ch[ch - 1]:
            return
        self.write(f":CHANnel{ch}:OUTPut OFF")
        self.ch[ch - 1] = False

    def end(self):
        """Leave all channels owned by this instance disabled."""
        for ch in (1, 2):
            self.stop(ch)

    def getName(self):
        return self.query("*IDN?")
