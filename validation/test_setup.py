import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("setup_g1", Path(__file__).resolve().parents[1] / "setup_g1.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.payload = self.base / "payload"
        self.source = self.payload / "home/unitree/sangmyeong_g1/example.txt"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"fixture")
        self.root = self.base / "target"
        self.root.mkdir()
        self.dest = self.root / self.source.relative_to(self.payload)

    def tearDown(self):
        self.temp.cleanup()

    def test_fresh_install_and_idempotent(self):
        receipt = {"created": []}
        setup.install(self.payload, self.root, receipt)
        self.assertEqual(self.dest.read_bytes(), b"fixture")
        before = self.dest.stat().st_mtime_ns
        again = {"created": []}
        setup.install(self.payload, self.root, again)
        self.assertEqual(again["created"], [])
        self.assertEqual(self.dest.stat().st_mtime_ns, before)

    def test_conflict_aborts_before_any_writes(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.write_bytes(b"user data")
        (self.source.parent / "new.txt").write_bytes(b"new")
        with self.assertRaises(RuntimeError):
            setup.install(self.payload, self.root, {"created": []})
        self.assertEqual(self.dest.read_bytes(), b"user data")
        self.assertFalse((self.dest.parent / "new.txt").exists())

    def test_unknown_install_path_rejected(self):
        x = self.payload / "etc/unsafe"
        x.parent.mkdir()
        x.write_text("fixture")
        with self.assertRaises(RuntimeError):
            setup.inspect(self.payload, self.root)

    @unittest.skipIf(os.name == "nt", "POSIX link test runs on G1")
    def test_symlink_parent_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.root / "home").symlink_to(outside)
        with self.assertRaises(RuntimeError):
            setup.install(self.payload, self.root, {"created": []})
        self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "POSIX mode test runs on G1")
    def test_existing_mode_difference_is_conflict(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.write_bytes(self.source.read_bytes())
        self.dest.chmod(0o700)
        self.source.chmod(0o644)
        self.assertTrue(setup.inspect(self.payload, self.root)["conflicts"])

    def archive(self, name, kind=None, link=None):
        a = self.base / "test.tar.gz"
        with tarfile.open(a, "w:gz") as t:
            m = tarfile.TarInfo(name)
            if kind:
                m.type = kind
                m.linkname = link or ""
                t.addfile(m)
            else:
                m.size = 3
                t.addfile(m, io.BytesIO(b"abc"))
        return a

    def test_hash_mismatch_before_extraction(self):
        a = self.archive("file")
        with self.assertRaises(RuntimeError):
            setup.extract(a, self.base / "unpacked")
        self.assertFalse((self.base / "unpacked").exists())

    def test_traversal_rejected(self):
        a = self.archive("../outside.txt")
        with patch.object(setup, "ARCHIVE_SHA", setup.sha(a)):
            with self.assertRaises(RuntimeError):
                setup.extract(a, self.base / "unpacked")
        self.assertFalse((self.base / "outside.txt").exists())

    def test_hardlink_rejected(self):
        a = self.archive("link", tarfile.LNKTYPE, "/etc/passwd")
        with patch.object(setup, "ARCHIVE_SHA", setup.sha(a)):
            with self.assertRaises(RuntimeError):
                setup.extract(a, self.base / "unpacked")

    def test_absolute_symlink_rejected(self):
        a = self.archive("link", tarfile.SYMTYPE, "/home/unitree")
        with patch.object(setup, "ARCHIVE_SHA", setup.sha(a)):
            with self.assertRaises(RuntimeError):
                setup.extract(a, self.base / "unpacked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
