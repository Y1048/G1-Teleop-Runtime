#!/usr/bin/env python3
"""Passively discover Quest APK input on UDP 5020. Never starts any controller."""
import argparse
import ipaddress
import json
import math
import socket
import time

SCHEMA = "g1.bimanual.unity.sim.v5"


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def vector(value, length):
    return isinstance(value, list) and len(value) == length and all(finite(v) for v in value)


def validate(raw, peer):
    ip = ipaddress.IPv4Address(peer[0])
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or int(ip) == 0xFFFFFFFF:
        raise ValueError("Not a remote unicast sender")
    if len(raw) > 16384:
        raise ValueError("Oversized packet")
    def no_constant(value):
        raise ValueError("Nonfinite JSON")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result
    p = json.loads(raw.decode("utf-8"), parse_constant=no_constant, object_pairs_hook=unique)
    if not isinstance(p, dict) or p.get("schema") != SCHEMA:
        raise ValueError("Not the deployed APK input schema")
    if p.get("simulation_only") is not True or p.get("input_frame") != "unity_display_world_v1":
        raise ValueError("Wrong input contract")
    session = p.get("session")
    if not isinstance(session, str) or not 1 <= len(session) <= 128:
        raise ValueError("Missing session")
    if type(p.get("sequence")) is not int or p["sequence"] < 0:
        raise ValueError("Invalid sequence")
    if not finite(p.get("sender_time_s")) or p["sender_time_s"] < 0:
        raise ValueError("Invalid sender clock")
    for side in ("left", "right"):
        hand = p.get(side)
        if not isinstance(hand, dict) or type(hand.get("tracked")) is not bool:
            raise ValueError("Invalid hand")
        if not vector(hand.get("position_m"), 3) or not vector(hand.get("quaternion_wxyz"), 4):
            raise ValueError("Invalid hand pose")
        norm2 = sum(v * v for v in hand["quaternion_wxyz"])
        if not .5 <= norm2 <= 1.5:
            raise ValueError("Invalid orientation")
    return (str(ip), session), p["sequence"], p["sender_time_s"]


class Candidates:
    def __init__(self):
        self.items = {}

    def accept(self, raw, peer, now):
        key, seq, source_time = validate(raw, peer)
        previous = self.items.get(key)
        if previous is None and len(self.items) >= 256:
            raise RuntimeError("Too many sender sessions; stop discovery and check the network")
        if previous and (seq <= previous["sequence"] or source_time <= previous["source_time"]):
            raise ValueError("Repeated/backwards sample")
        count = previous["count"] + 1 if previous and now - previous["last"] <= 1 else 1
        self.items[key] = dict(sequence=seq, source_time=source_time, last=now, count=count)

    def select(self, now):
        fresh = {k: v for k, v in self.items.items() if now - v["last"] <= 2}
        if len(fresh) > 1:
            raise RuntimeError("Multiple APK senders/sessions detected. Close extra APK/Editor instances and retry.")
        if len(fresh) == 1:
            key, sample = next(iter(fresh.items()))
            if sample["count"] >= 3:
                return key[0]
        return None


def discover(timeout=60):
    candidates = Candidates()
    start = time.monotonic()
    settle_until = None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(("0.0.0.0", 5020))
        except OSError as error:
            raise RuntimeError("UDP 5020 is occupied/unavailable. Stop the existing teleop receiver first; nothing was killed.") from error
        sock.settimeout(.2)
        print("Waiting for Quest APK input on UDP 5020. Set APK server address to THIS G1.", flush=True)
        print("Discovery only. No motor, camera, DDS, forwarding or controller startup.", flush=True)
        while time.monotonic() - start < timeout:
            try:
                raw, peer = sock.recvfrom(16385)
                candidates.accept(raw, peer, time.monotonic())
            except socket.timeout:
                pass
            except (ValueError, UnicodeError, RecursionError, OverflowError):
                continue
            now = time.monotonic()
            selected = candidates.select(now)
            if selected is None:
                settle_until = None
            elif settle_until is None:
                settle_until = now + 3
            elif now >= settle_until:
                return selected
    raise RuntimeError("No sustained valid APK input. Check APK server address, LAN/firewall and that the APK is running.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or not 5 <= args.timeout <= 300:
        parser.error("timeout must be 5..300 seconds")
    ip = discover(args.timeout)
    # This is output, not an executed shell command. Socket closes before return.
    print("\nQuest-format input received from: " + ip)
    print("UDP 5020 released. No motor has been started.")
    print("This confirms incoming packets, not authenticated identity or full bidirectional connectivity.")
    print("\nOptional NO-MOTOR communication test (camera PTZ may move):")
    print("cd /home/unitree/sangmyeong_g1")
    print("NO_MOTORS=1 ./start_all.sh " + ip)
    print("\nOnly when YOU are ready for real actuation (5-second countdown):")
    print("NO_MOTORS=0 ./start_all.sh " + ip)
    print("If the Quest IP/network changes, run discovery again. Normal stop: Enter, wait for all stopped.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as error:
        raise SystemExit("DISCOVERY STOPPED: " + str(error))
    except KeyboardInterrupt:
        raise SystemExit("Discovery cancelled. No controller was started.")
