import importlib.util
import json
import itertools
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "discovery", Path(__file__).resolve().parents[1] / "discover_quest.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def packet(seq=1, session="fixture", **changes):
    hand = dict(tracked=False, position_m=[0, 0, 0], quaternion_wxyz=[1, 0, 0, 0])
    p = dict(schema=d.SCHEMA, simulation_only=True, input_frame="unity_display_world_v1",
             session=session, sequence=seq, sender_time_s=seq / 60, left=hand, right=hand)
    p.update(changes)
    return json.dumps(p).encode()


class DiscoveryTests(unittest.TestCase):
    def test_three_increasing_samples(self):
        c = d.Candidates()
        for i in range(3):
            c.accept(packet(i), ("192.168.1.50", 40123), i / 60)
        self.assertEqual(c.select(.1), "192.168.1.50")

    def test_single_sample_insufficient(self):
        c = d.Candidates()
        c.accept(packet(), ("192.168.1.50", 1), 0)
        self.assertIsNone(c.select(.1))

    def test_stale_rejected(self):
        c = d.Candidates()
        for i in range(3):
            c.accept(packet(i), ("192.168.1.50", 1), i / 60)
        self.assertIsNone(c.select(3))

    def test_replay_rejected(self):
        c = d.Candidates()
        c.accept(packet(), ("192.168.1.50", 1), 0)
        with self.assertRaises(ValueError):
            c.accept(packet(), ("192.168.1.50", 1), .1)

    def test_two_devices_rejected(self):
        c = d.Candidates()
        for ip in ("192.168.1.50", "192.168.1.51"):
            c.accept(packet(), (ip, 1), 0)
        with self.assertRaises(RuntimeError):
            c.select(.1)

    def test_two_sessions_same_ip_rejected(self):
        c = d.Candidates()
        for session in ("one", "two"):
            c.accept(packet(session=session), ("192.168.1.50", 1), 0)
        with self.assertRaises(RuntimeError):
            c.select(.1)

    def test_invalid_packets(self):
        for raw in (b"{}", packet(schema="other"), packet(sequence=True),
                    packet(sender_time_s=float("nan")), packet(left={}), b"\xff",
                    b'{"schema":"one","schema":"two"}', b"x" * 16385):
            with self.subTest(raw=raw[:60]):
                with self.assertRaises((ValueError, UnicodeError)):
                    d.validate(raw, ("192.168.1.50", 1))

    def test_loopback_rejected(self):
        with self.assertRaises(ValueError):
            d.validate(packet(), ("127.0.0.1", 1))

    def test_busy_port_no_takeover(self):
        with patch.object(d.socket, "socket") as factory:
            factory.return_value.__enter__.return_value.bind.side_effect = OSError("busy")
            with self.assertRaisesRegex(RuntimeError, "occupied"):
                d.discover(5)

    def test_main_only_prints_commands(self):
        with patch.object(d, "discover", return_value="192.168.1.50"), \
                patch("sys.argv", ["discover_quest.py"]), patch("builtins.print") as output:
            d.main()
        lines = "\n".join(str(call.args[0]) for call in output.call_args_list)
        self.assertIn("NO_MOTORS=0 ./start_all.sh 192.168.1.50", lines)
        self.assertIn("No motor has been started", lines)

    def test_receive_loop_releases_socket(self):
        ticks = itertools.count()
        sequences = itertools.count()
        with patch.object(d.socket, "socket") as factory, \
                patch.object(d.time, "monotonic", side_effect=lambda: next(ticks) * .1), \
                patch("builtins.print"):
            sock = factory.return_value.__enter__.return_value
            sock.recvfrom.side_effect = lambda size: (packet(next(sequences)), ("192.168.1.50", 1234))
            self.assertEqual(d.discover(60), "192.168.1.50")
            factory.return_value.__exit__.assert_called_once()

    def test_timeout_releases_socket(self):
        ticks = itertools.count()
        with patch.object(d.socket, "socket") as factory, \
                patch.object(d.time, "monotonic", side_effect=lambda: next(ticks)), \
                patch("builtins.print"):
            factory.return_value.__enter__.return_value.recvfrom.side_effect = d.socket.timeout()
            with self.assertRaisesRegex(RuntimeError, "No sustained"):
                d.discover(5)
            factory.return_value.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
