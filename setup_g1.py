#!/usr/bin/env python3
"""Install missing runtime files only; never launch the motor controller."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
ARCHIVE = "g1_core_binary_stripped_20261021.tar.gz"
ARCHIVE_SHA = "0d6abe0b1abf44d82cdc433f6032341b695209e4ba29d6cd70cbf70e6a2be8b6"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def extract(archive, target):
    """Pinned archive, no absolute paths, link ancestors, hardlinks or devices."""
    if sha(archive) != ARCHIVE_SHA:
        raise RuntimeError("Archive SHA256 mismatch")
    target.mkdir()
    with tarfile.open(archive, "r:gz") as tf:
        members = tf.getmembers()
        links = set()
        names = set()
        for m in members:
            p = PurePosixPath(m.name)
            if p.is_absolute() or ".." in p.parts or m.name in names:
                raise RuntimeError("Unsafe/duplicate archive member: " + m.name)
            names.add(m.name)
            if not (m.isfile() or m.isdir() or m.issym()):
                raise RuntimeError("Unsupported archive type: " + m.name)
            if m.issym():
                links.add(p)
                link = PurePosixPath(m.linkname)
                resolved = os.path.normpath(str(p.parent / link))
                if link.is_absolute() or resolved == ".." or resolved.startswith("../"):
                    raise RuntimeError("Escaping archive link")
        for m in members:
            p = PurePosixPath(m.name)
            if any(parent in links for parent in p.parents):
                raise RuntimeError("Archive entry has symlink ancestor")
        # Ownership is intentionally not restored. Never preserve setuid/setgid.
        for m in members:
            dst = target / m.name
            if m.isdir():
                dst.mkdir(parents=True, exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if m.issym():
                    dst.symlink_to(m.linkname)
                else:
                    with tf.extractfile(m) as src, dst.open("xb") as out:
                        shutil.copyfileobj(src, out)
                    dst.chmod(m.mode & 0o777)


def allowed(rel):
    s = rel.as_posix()
    roots = (
        "home/unitree/sangmyeong_g1",
        "home/unitree/groot_onboard_runtime",
        "home/unitree/groot_command_observer_build_20261007_9dd21a6",
        "home/unitree/unitree_sdk2_python",
        "home/unitree/.local/lib/python3.8/site-packages",
    )
    if any(s == x or s.startswith(x + "/") or x.startswith(s + "/") for x in roots):
        return True
    libs = ["usr/local/lib/" + x for x in
            ("libddsc.so", "libddsc.so.0", "libddscxx.so", "libddscxx.so.0")]
    return any(s == x or x.startswith(s + "/") for x in libs)


def entries(payload):
    result = sorted(payload.rglob("*"), key=lambda x: (len(x.parts), str(x)))
    for src in result:
        if not allowed(src.relative_to(payload)):
            raise RuntimeError("Unexpected install path: " + str(src))
    return result


def parent_safe(dst, root):
    for p in [dst.parent] + list(dst.parent.parents):
        if p == root:
            break
        if p.is_symlink():
            raise RuntimeError("Symlink destination ancestor: " + str(p))


def same(src, dst):
    if src.is_symlink():
        return dst.is_symlink() and os.readlink(src) == os.readlink(dst)
    if dst.is_symlink():
        return False
    if src.is_dir():
        return dst.is_dir()
    return (dst.is_file() and sha(src) == sha(dst)
            and stat.S_IMODE(src.stat().st_mode) == stat.S_IMODE(dst.stat().st_mode))


def inspect(payload, root):
    conflicts, missing = [], []
    for src in entries(payload):
        dst = root / src.relative_to(payload)
        try:
            parent_safe(dst, root)
        except RuntimeError as error:
            conflicts.append(str(error))
            continue
        if os.path.lexists(dst):
            if not same(src, dst):
                conflicts.append(str(dst))
        else:
            missing.append(str(dst))
    return {"conflicts": conflicts, "missing": missing}


def install(payload, root, receipt, owner=None):
    check = inspect(payload, root)
    if check["conflicts"]:
        raise RuntimeError("Existing file conflict; no installation performed: "
                           + "; ".join(check["conflicts"][:15]))
    for src in entries(payload):
        rel = src.relative_to(payload)
        dst = root / rel
        parent_safe(dst, root)
        if os.path.lexists(dst):
            if not same(src, dst):
                raise RuntimeError("Destination changed during install: " + str(dst))
            continue
        # Exclusive creation refuses a newly appearing file. No overwrite/delete.
        if src.is_symlink():
            dst.symlink_to(os.readlink(src))
        elif src.is_dir():
            dst.mkdir()
        else:
            fd = os.open(str(dst), os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
            receipt["created"].append(str(dst))
            with os.fdopen(fd, "wb") as out, src.open("rb") as inp:
                shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
            dst.chmod(stat.S_IMODE(src.stat().st_mode) & 0o777)
        if str(dst) not in receipt["created"]:
            receipt["created"].append(str(dst))
        if owner is not None:
            uid, gid = owner if rel.parts[:2] == ("home", "unitree") else (0, 0)
            os.chown(dst, uid, gid, follow_symlinks=False)
    check = inspect(payload, root)
    if check["conflicts"] or check["missing"]:
        raise RuntimeError("Installed tree verification failed")


def environment(install_dependencies=False, report_dir=None):
    failures = []
    release = Path("/etc/os-release").read_text()
    l4t = Path("/etc/nv_tegra_release").read_text() if Path("/etc/nv_tegra_release").exists() else ""
    if platform.machine() != "aarch64" or 'VERSION_ID="20.04"' not in release:
        failures.append("Requires aarch64 Ubuntu 20.04")
    if "R35 (release), REVISION: 3.1" not in l4t:
        failures.append("Requires L4T R35.3.1")
    if sys.version_info[:2] != (3, 8):
        failures.append("Run with system python3 (3.8)")
    import pwd
    if pwd.getpwuid(os.getuid()).pw_name != "unitree":
        failures.append("Run as unitree, not root")
    if not Path("/sys/class/net/eth0").exists():
        failures.append("eth0 missing")
    # Base tooling and sudo cannot bootstrap themselves under this non-root entry.
    for command in ("sudo", "bash", "pgrep", "sha256sum", "apt-get", "dpkg-query"):
        if not shutil.which(command):
            failures.append("Missing tool: " + command)
    missing = {}
    for command, package in (("bwrap", "bubblewrap"), ("v4l2-ctl", "v4l-utils"),
                             ("ldd", "libc-bin")):
        if not shutil.which(command):
            missing[package] = None
    for package, prefix in (("libnvinfer8", "8.5.2"), ("cuda-cudart-11-4", "11.4")):
        proc = subprocess.run(["dpkg-query", "-W", "-f=${Status}\t${Version}", package],
                              capture_output=True, text=True)
        if proc.returncode or proc.stdout.split("\t", 1)[0] not in ("install ok installed", "hold ok installed"):
            missing[package] = prefix
        elif not proc.stdout.split("\t", 1)[1].startswith(prefix):
            failures.append("Existing incompatible package (will NOT change): " + package)
    try:
        __import__("numpy")
    except ImportError:
        missing["python3-numpy"] = None
    targets = ("groot_balance_actuator", "g1_omni_heading_controller.py",
               "g1_teleop_server.py", "g1_bimanual_runtime.py")
    for cmd in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            args = cmd.read_bytes().split(b"\0")
            if any(Path(x.decode(errors="replace")).name in targets for x in args if x):
                failures.append("Existing controller/service process: " + cmd.parent.name)
        except OSError:
            pass
    if failures:
        raise RuntimeError("\n".join(failures) + "\nNo automatic OS/package changes performed.")
    if missing:
        if not install_dependencies:
            raise RuntimeError("Missing packages (check-only does not install): " + ", ".join(missing))
        # Load without depending on embedded/modified Python search paths.
        import importlib.util
        spec = importlib.util.spec_from_file_location("system_dependencies", HERE / "system_dependencies.py")
        deps = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deps)
        deps.install_missing(missing, report_dir / "system-dependencies")
        importlib.invalidate_caches()
        return environment(install_dependencies=False, report_dir=report_dir)
    # Namespace probe before downloads, privilege request or installation.
    subprocess.run(["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
                    "--cap-drop", "ALL", "--ro-bind", "/", "/", "--proc", "/proc",
                    "--dev", "/dev", "--tmpfs", "/home", "--tmpfs", "/run",
                    "--tmpfs", "/tmp", "/bin/true"],
                   env={"PATH": "/usr/bin:/bin"}, check=True, timeout=10)


def worker(archive):
    import pwd
    if os.geteuid() != 0:
        raise RuntimeError("Install worker requires sudo")
    user = pwd.getpwnam("unitree")
    receipt = {"created": [], "motor_execution": False, "success": False}
    try:
        # Root uses its own fresh extraction and rechecks the pinned SHA.
        with tempfile.TemporaryDirectory(prefix="g1-install-") as tmp:
            root = Path(tmp) / "unpacked"
            extract(archive, root)
            install(root / "payload", Path("/"), receipt, (user.pw_uid, user.pw_gid))
            if any(x.startswith("/usr/local/lib/") for x in receipt["created"]):
                subprocess.run(["/sbin/ldconfig"], check=True)
            receipt["success"] = True
    except Exception as error:
        receipt["error"] = str(error)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["success"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true",
                        help="Environment, download, integrity and conflicts only; no installation")
    parser.add_argument("--archive-dir", type=Path, help="Use already downloaded release assets")
    parser.add_argument("--install-worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.install_worker:
        return worker(args.install_worker.resolve())
    work = Path(tempfile.mkdtemp(prefix="g1-setup-", dir=str(Path.home())))
    print("Setup records:", work, flush=True)
    environment(install_dependencies=not args.check_only, report_dir=work)
    records = json.loads((HERE / "artifacts.json").read_text())["artifacts"][:3]
    for record in records:
        dst = work / record["name"]
        if args.archive_dir:
            source = args.archive_dir / record["name"]
            if sha(source) != record["sha256"]:
                raise RuntimeError("Local asset mismatch: " + str(source))
            shutil.copyfile(source, dst)
        else:
            print("Downloading:", record["name"], flush=True)
            with urllib.request.urlopen(record["url"], timeout=60) as inp, dst.open("xb") as out:
                shutil.copyfileobj(inp, out)
        if sha(dst) != record["sha256"]:
            raise RuntimeError("Download SHA mismatch: " + dst.name)
    archive = work / ARCHIVE
    package = work / "unpacked"
    extract(archive, package)
    check = inspect(package / "payload", Path("/"))
    (work / "preflight.json").write_text(json.dumps(check, indent=2))
    if check["conflicts"]:
        raise RuntimeError("STOP: existing file conflicts; see " + str(work / "preflight.json"))
    if args.check_only:
        print("CHECK PASS. No installation or application execution.", flush=True)
        return 0
    print("Installing missing files only. sudo may request your Linux password.", flush=True)
    proc = subprocess.run(["sudo", "--", sys.executable, str(Path(__file__).resolve()),
                           "--install-worker", str(archive)], stdout=subprocess.PIPE, text=True)
    (work / "install-receipt.json").write_text(proc.stdout)
    if proc.returncode:
        raise RuntimeError("Install stopped; inspect receipt. Existing files were not overwritten.")
    if inspect(package / "payload", Path("/")) != {"conflicts": [], "missing": []}:
        raise RuntimeError("Post-install mismatch")
    executable = "/home/unitree/groot_command_observer_build_20261007_9dd21a6/build/groot_balance_actuator"
    links = subprocess.run(["ldd", executable], capture_output=True, text=True)
    (work / "binary-links.txt").write_text(links.stdout + links.stderr)
    if links.returncode or "not found" in links.stdout:
        raise RuntimeError("Native libraries missing; see binary-links.txt. Controller NOT executed.")
    # Use the reviewed motor-excluded namespace validation, not start_all.sh.
    trial = work / "isolated"
    subprocess.run([sys.executable, str(HERE / "validation/prepare.py"),
                    "--package", str(package), "--destination", str(trial)], check=True)
    subprocess.run([sys.executable, str(HERE / "validation/run_isolated.py"),
                    "--root", str(trial), "--seconds", "30", "--idle-valleg-fixture"], check=True)
    result_file = next(trial.glob("run_*/result.json"))
    result = json.loads(result_file.read_text())
    console = result_file.with_name("console.log").read_text(errors="replace")
    if (result["forced_cleanup"] or not result["original_launcher_completion_marker"]
            or "ACK arm=[FRESH_LIVE ready]" not in console):
        raise RuntimeError("Lifecycle/readiness evidence incomplete; inspect isolated logs.")
    if inspect(package / "payload", Path("/")) != {"conflicts": [], "missing": []}:
        raise RuntimeError("Installed files changed during isolated validation")
    print("INSTALL + ISOLATED LIFECYCLE COMPLETE. Motor controller NOT executed.", flush=True)
    print("Valleg was an idle fixture; real Quest/camera/LowState/motor integration NOT validated.")
    print("Records:", work)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("SETUP STOPPED:", error, file=sys.stderr)
        sys.exit(1)
