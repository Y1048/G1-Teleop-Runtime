"""Linux-only validation runner. No fallback to unisolated execution."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import signal
import subprocess
import time


def command(root, bwrap):
    home = root / "home/unitree"
    # Read-only host OS for the original JetPack libraries. ALL original /home
    # paths are hidden; only copied package files are writable. No NIC or devices.
    return [
        bwrap, "--unshare-all", "--die-with-parent", "--new-session",
        "--cap-drop", "ALL", "--ro-bind", "/", "/", "--proc", "/proc",
        "--dev", "/dev", "--tmpfs", "/tmp", "--tmpfs", "/run",
        "--tmpfs", "/home", "--bind", str(home), "/home/unitree",
        "--setenv", "HOME", "/home/unitree",
        "--setenv", "USER", "unitree", "--setenv", "PATH", "/usr/bin:/bin",
        "--setenv", "LANG", "C.UTF-8",
        "--chdir", "/home/unitree/sangmyeong_g1",
        "/bin/bash", "./start_no_motors.sh",
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, required=True)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--idle-valleg-fixture", action="store_true",
                        help="Lifecycle only: replace physical Valleg with a no-input idle process")
    args = parser.parse_args()
    if os.name != "posix" or os.geteuid() == 0:
        raise SystemExit("Requires Linux, non-root user, working unprivileged bubblewrap")
    if not 5 <= args.seconds <= 120:
        raise SystemExit("Duration must be 5..120 seconds")
    root = args.root.resolve()
    metadata = json.loads((root / "preparation.json").read_text())
    app = root / "home/unitree/sangmyeong_g1"
    if hashlib.sha256((app / "start_no_motors.sh").read_bytes()).hexdigest() != metadata["derived_start_sha256"]:
        raise SystemExit("Derived launcher changed")
    excluded = root / "home/unitree/groot_command_observer_build_20261007_9dd21a6/build/groot_balance_actuator"
    if excluded.exists() or excluded.is_symlink():
        raise SystemExit("Actuator binary must be absent from sandbox")
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise SystemExit("bubblewrap absent. STOP: no automatic install or unsafe fallback")
    # Probe the exact isolation flags first, without importing project code.
    argv = command(root, bwrap)
    if args.idle_valleg_fixture:
        fixture = pathlib.Path(__file__).resolve().with_name("idle_valleg_fixture.py")
        if not fixture.is_file():
            raise SystemExit("Missing idle fixture")
        index = argv.index("--chdir")
        argv[index:index] = ["--ro-bind", str(fixture),
                            "/home/unitree/sangmyeong_g1/tools/g1_valleg_gateway.py"]
    # Ubuntu 20.04 bubblewrap predates --clearenv. Pass a clean environment
    # to BOTH invocations instead; do not inherit PYTHONPATH/LD_PRELOAD/etc.
    clean_env = {"PATH": "/usr/bin:/bin"}
    subprocess.run(argv[:-2] + ["/bin/true"], check=True, timeout=10, env=clean_env)
    report = root / ("run_" + time.strftime("%Y%m%d_%H%M%S"))
    report.mkdir()
    forced = False
    with (report / "console.log").open("wb") as log:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True, env=clean_env)
        started = time.monotonic()
        try:
            while proc.poll() is None and time.monotonic() - started < args.seconds:
                time.sleep(.1)
            if proc.poll() is None:
                proc.stdin.write(b"\n")
                proc.stdin.flush()
            proc.wait(timeout=40)
        except (KeyboardInterrupt, subprocess.TimeoutExpired):
            forced = True
            if proc.poll() is None:
                # Only this owned namespace/supervisor, never process-name kills.
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=5)
        finally:
            proc.stdin.close()
    text = (report / "console.log").read_text(errors="replace")
    (report / "result.json").write_text(json.dumps({
        "returncode": proc.returncode, "forced_cleanup": forced,
        "original_launcher_completion_marker": "all stopped. logs:" in text,
        "elapsed_s": time.monotonic() - started,
        "hardware_validation": False, "motor_process_excluded": True,
        "network_and_devices_isolated": True,
        "integration_pass": None,
        "idle_valleg_fixture": args.idle_valleg_fixture,
        "note": "Inspect ALL component logs for readiness; exit zero alone is not integration PASS."
    }, indent=2))
    print(report)
    raise SystemExit(1 if forced or proc.returncode else 0)


if __name__ == "__main__":
    main()
