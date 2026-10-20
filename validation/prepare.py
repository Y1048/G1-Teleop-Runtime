"""Prepare a disposable copy. Never starts the package or connects to a robot."""
import argparse
import hashlib
import json
import pathlib
import shutil

START_SHA = "829428c5a379836b74972c3a2a00f30039d860a54aa71109922df7c5668fa8d8"
BEGIN = 'say "[4/5] GROOT binary check"'
END = "echo\nsay \"GROOT running."


def derive_start(text):
    if hashlib.sha256(text.encode()).hexdigest() != START_SHA:
        raise ValueError("Unknown startup revision: inspect it before preparing validation")
    start, end = text.index(BEGIN), text.index(END)
    # Preserve original server, IK, Valleg and cleanup code. Replace BOTH the
    # actuator launch and the original heading cwd with sandbox-local heading.
    replacement = '''say "[4/5] ISOLATED NO-MOTOR VALIDATION: actuator excluded"
say "[5/5] heading only, inside private network/device namespace"
( cd "$RUNTIME" && G1_GROOT_OWNER=$OWNER exec python3 "$HERE/ptyrun.py" "$LOG/heading.log" \\
  python3 -u tools/g1_omni_heading_controller.py --yaw-sign -1 ) </dev/null >/dev/null 2>&1 &
PIDS+=($!)
sleep 1
'''
    result = text[:start] + replacement + text[end:]
    result = result.replace('GROOT running. STOP', 'ISOLATED VALIDATION running. STOP')
    if "--enable-actuation" in result or '"$OBSERVER_BIN" --' in result:
        raise ValueError("Actuator launch survived transformation")
    return result


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def prepare(package, destination):
    package, destination = package.resolve(), destination.absolute()
    if destination.exists() or package in destination.parents:
        raise ValueError("Use a NEW directory outside the source package")
    records = json.loads((package / "manifest.json").read_text())
    for entry in records:
        path = (package / entry["path"]).resolve()
        if package not in path.parents or sha(path) != entry["sha256"]:
            raise ValueError("Manifest mismatch: " + entry["path"])
    source = package / "payload/home/unitree"
    text = (source / "sangmyeong_g1/start_all.sh").read_bytes().decode()
    derived = derive_start(text)
    # No tar extraction, no overwrites, no edits to the package.
    destination.mkdir(parents=True)
    home = destination / "home/unitree"
    shutil.copytree(source, home, symlinks=True)
    app = home / "sangmyeong_g1"
    (app / "start_no_motors.sh").write_bytes(derived.encode())
    # Remove command-capable entrypoints only from this disposable COPY.
    (app / "start_all.sh").unlink()
    (app / "stop_motors.sh").unlink(missing_ok=True)
    observer = home / "groot_command_observer_build_20261007_9dd21a6/build/groot_balance_actuator"
    observer.unlink()
    (destination / "preparation.json").write_text(json.dumps({
        "source_package": str(package), "source_start_sha256": START_SHA,
        "derived_start_sha256": sha(app / "start_no_motors.sh"),
        "source_records_verified": len(records), "motor_binary_removed_from_copy": True,
        "hardware_validation": False, "full_lifecycle_validation": False,
        "missing_devices_expected": ["camera", "Valleg", "LowState", "Quest"],
    }, indent=2))
    for entry in records:
        if sha(package / entry["path"]) != entry["sha256"]:
            raise ValueError("Source changed during preparation")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=pathlib.Path, required=True)
    parser.add_argument("--destination", type=pathlib.Path, required=True)
    args = parser.parse_args()
    print(prepare(args.package, args.destination))
