"""Lifecycle fixture only: no HID, sockets, base commands, or simulated samples."""
import signal
import time

running = True


def stop(signum, frame):
    global running
    running = False


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
print("[FIXTURE] Idle Valleg placeholder; NO INPUT DATA PUBLISHED", flush=True)
while running:
    time.sleep(.1)
print("[FIXTURE] stopped", flush=True)
