"""
PC Guardian — monitors system health in the background and alerts
Jarvis when something needs attention. 100% local, zero API calls.

Monitors: CPU, RAM, disk, battery, temperature.
Identifies the top offending process when CPU/RAM spikes.
Cooldowns prevent alert spam.
"""

import threading
import time
import logging
from typing import Callable

logger = logging.getLogger(__name__)

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

# ── Thresholds ─────────────────────────────────────────────────────────────────
THRESHOLDS = {
    "cpu":         85,    # % sustained over 2 checks
    "ram":         88,    # %
    "disk":        10,    # % free remaining
    "battery":     20,    # % (when not charging)
    "temperature": 85,    # °C
}

# ── Cooldowns (seconds between same alert type) ────────────────────────────────
COOLDOWNS = {
    "cpu":         300,   # 5 min
    "ram":         600,   # 10 min
    "disk":        1800,  # 30 min
    "battery":     600,   # 10 min
    "temperature": 300,   # 5 min
}

CHECK_INTERVAL = 30       # seconds between each full check
CPU_CONFIRM_CHECKS = 2    # CPU must be high for this many checks in a row


def _top_process(by: str = "cpu") -> str:
    """Return name + value of the most resource-hungry process."""
    try:
        procs = []
        for p in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except Exception:
                pass
        if by == "cpu":
            top = max(procs, key=lambda x: x.get("cpu_percent") or 0)
            return f"{top['name']} ({top['cpu_percent']:.0f}% CPU)"
        else:
            top = max(procs, key=lambda x: x.get("memory_percent") or 0)
            return f"{top['name']} ({top['memory_percent']:.0f}% RAM)"
    except Exception:
        return "unknown process"


def _get_disk_free_pct(path: str = "C:\\") -> float:
    try:
        usage = psutil.disk_usage(path)
        return 100.0 - usage.percent
    except Exception:
        return 100.0


def _get_temperature() -> float | None:
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        for key in ("coretemp", "acpitz", "cpu_thermal", "k10temp"):
            if key in temps:
                readings = temps[key]
                if readings:
                    return max(r.current for r in readings)
        # fallback: any sensor
        for readings in temps.values():
            if readings:
                return max(r.current for r in readings)
    except Exception:
        return None


class PCGuardian:

    def __init__(self, speak: Callable[[str], None]):
        self.speak         = speak
        self._stop_event   = threading.Event()
        self._thread       = None
        self._last_alert   = {}          # alert_type → last alert timestamp
        self._cpu_streak   = 0           # consecutive high-CPU checks

        # Live snapshot (for dashboard polling)
        self.snapshot: dict = {}

    def start(self) -> None:
        if not _PSUTIL:
            print("[Guardian] psutil not available — install with: pip install psutil")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="PCGuardian"
        )
        self._thread.start()
        print("[Guardian] PC Guardian active.")

    def stop(self) -> None:
        self._stop_event.set()

    def _can_alert(self, alert_type: str) -> bool:
        last = self._last_alert.get(alert_type, 0)
        return (time.time() - last) >= COOLDOWNS[alert_type]

    def _record_alert(self, alert_type: str) -> None:
        self._last_alert[alert_type] = time.time()

    def _loop(self) -> None:
        # Give Jarvis time to fully start before first check
        time.sleep(15)

        while not self._stop_event.is_set():
            try:
                self._check()
            except Exception as e:
                logger.debug(f"[Guardian] Check error: {e}")
            self._stop_event.wait(CHECK_INTERVAL)

    def _check(self) -> None:
        snap: dict = {}

        # ── CPU ───────────────────────────────────────────────────────────────
        cpu = psutil.cpu_percent(interval=1)
        snap["cpu"] = cpu
        if cpu >= THRESHOLDS["cpu"]:
            self._cpu_streak += 1
        else:
            self._cpu_streak = 0

        if self._cpu_streak >= CPU_CONFIRM_CHECKS and self._can_alert("cpu"):
            top = _top_process("cpu")
            self.speak(
                f"Heads up, boss — CPU is running at {cpu:.0f} percent. "
                f"The main culprit is {top}. Want me to kill it?"
            )
            self._record_alert("cpu")
            self._cpu_streak = 0

        # ── RAM ───────────────────────────────────────────────────────────────
        ram = psutil.virtual_memory()
        snap["ram"] = ram.percent
        if ram.percent >= THRESHOLDS["ram"] and self._can_alert("ram"):
            top = _top_process("ram")
            used_gb = ram.used / (1024 ** 3)
            total_gb = ram.total / (1024 ** 3)
            self.speak(
                f"RAM is at {ram.percent:.0f} percent, boss — "
                f"{used_gb:.1f} of {total_gb:.0f} gigabytes used. "
                f"Biggest consumer is {top}. Want me to close something?"
            )
            self._record_alert("ram")

        # ── Disk ──────────────────────────────────────────────────────────────
        disk_free = _get_disk_free_pct()
        snap["disk_free"] = disk_free
        if disk_free <= THRESHOLDS["disk"] and self._can_alert("disk"):
            disk = psutil.disk_usage("C:\\")
            free_gb = disk.free / (1024 ** 3)
            self.speak(
                f"Warning, boss — your C drive is almost full. "
                f"Only {free_gb:.1f} gigabytes remaining. "
                f"Want me to find the largest files?"
            )
            self._record_alert("disk")

        # ── Battery ───────────────────────────────────────────────────────────
        battery = psutil.sensors_battery()
        if battery:
            snap["battery"] = battery.percent
            snap["plugged"]  = battery.power_plugged
            if (not battery.power_plugged
                    and battery.percent <= THRESHOLDS["battery"]
                    and self._can_alert("battery")):
                self.speak(
                    f"Battery at {battery.percent:.0f} percent and not charging, boss. "
                    f"You may want to plug in soon."
                )
                self._record_alert("battery")

        # ── Temperature ───────────────────────────────────────────────────────
        temp = _get_temperature()
        if temp is not None:
            snap["temp"] = temp
            if temp >= THRESHOLDS["temperature"] and self._can_alert("temperature"):
                self.speak(
                    f"CPU temperature is at {temp:.0f} degrees Celsius, boss — "
                    f"that's running hot. You might want to check your cooling."
                )
                self._record_alert("temperature")

        self.snapshot = snap
        logger.debug(f"[Guardian] {snap}")


# ── Singleton ──────────────────────────────────────────────────────────────────
_guardian: PCGuardian | None = None


def start_guardian(speak: Callable[[str], None]) -> PCGuardian:
    global _guardian
    _guardian = PCGuardian(speak)
    _guardian.start()
    return _guardian


def get_guardian() -> PCGuardian | None:
    return _guardian
