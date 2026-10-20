"""Install missing apt packages without upgrading/reinstalling existing ones."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ENV = dict(os.environ, LC_ALL="C", LANG="C")


def installed():
    p = subprocess.run(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${Status}\n"],
                       check=True, capture_output=True, text=True, env=ENV)
    rows = {}
    for line in p.stdout.splitlines():
        name, version, status = line.split("\t", 2)
        if status in ("install ok installed", "hold ok installed"):
            rows[name] = version
        elif status not in ("deinstall ok config-files", "unknown ok not-installed"):
            raise RuntimeError("Unfinished/held package state: " + name + " " + status)
    return rows


def base_name(name):
    return name.split(":", 1)[0]


def validate_plan(text, before):
    old = {base_name(name) for name in before}
    new = {}
    for line in text.splitlines():
        if line.startswith(("Remv ", "Purg ")):
            raise RuntimeError("Dependency plan would remove an existing package: " + line)
        if line.startswith("Inst "):
            match = re.match(r"Inst (\S+) \((\S+) ", line)
            if not match or base_name(line.split()[1]) in old:
                raise RuntimeError("Dependency plan would change an existing package: " + line)
            new[match.group(1)] = match.group(2)
        if line.startswith("Conf ") and base_name(line.split()[1]) in old:
            raise RuntimeError("Dependency plan would reconfigure an existing package: " + line)
    return new


def pins(before):
    # Version-specific first, all other versions of installed packages forbidden.
    return "".join("Package: %s\nPin: version %s\nPin-Priority: 1001\n\n"
                   "Package: %s\nPin: version *\nPin-Priority: -1\n\n" %
                   (name, version, name) for name, version in sorted(before.items()))


def choose_version(name, prefix):
    p = subprocess.run(["apt-cache", "madison", name], check=True,
                       capture_output=True, text=True, env=ENV)
    versions = [line.split("|")[1].strip() for line in p.stdout.splitlines() if "|" in line]
    matches = [v for v in versions if prefix is None or v.startswith(prefix)]
    if not matches:
        raise RuntimeError("No compatible repository version: " + name +
                           ". No repository or existing NVIDIA version will be changed.")
    return matches[0]


def install_missing(requirements, report_dir):
    """requirements: missing package -> required version prefix or None."""
    before = installed()
    old = {base_name(n) for n in before}
    if any(name in old for name in requirements):
        raise RuntimeError("Existing/broken dependency will not be reinstalled")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "packages-before.json").write_text(json.dumps(before, indent=2))
    # Index refresh only; no upgrade, distribution change or repository addition.
    subprocess.run(["sudo", "--", "env", "LC_ALL=C", "apt-get", "update"], check=True)
    with tempfile.TemporaryDirectory(prefix="g1-apt-plan-") as folder:
        pref = Path(folder) / "preserve-installed"
        pref.write_text(pins(before))
        requests = [name + "=" + choose_version(name, prefix)
                    for name, prefix in requirements.items()]
        options = ["-o", "Dir::Etc::preferences=" + str(pref),
                   "--no-install-recommends", "--no-upgrade", "--no-remove"]
        plan = subprocess.run(["apt-get", "-s"] + options + ["install"] + requests,
                              capture_output=True, text=True, env=ENV)
        (report_dir / "apt-plan.txt").write_text(plan.stdout + plan.stderr)
        plan.check_returncode()
        new = validate_plan(plan.stdout, before)
        if not set(requirements).issubset({base_name(n) for n in new}):
            raise RuntimeError("Missing package absent from install plan")
        # Freeze transitive additions to the versions reviewed in simulation too.
        exact = [name + "=" + version for name, version in new.items()]
        final_plan = subprocess.run(["apt-get", "-s"] + options + ["install"] + exact,
                                    capture_output=True, text=True, env=ENV)
        (report_dir / "apt-final-plan.txt").write_text(final_plan.stdout + final_plan.stderr)
        final_plan.check_returncode()
        if validate_plan(final_plan.stdout, before) != new:
            raise RuntimeError("Exact-version dependency plan changed; no installation performed")
        if installed() != before:
            raise RuntimeError("Package state changed during planning; retry when apt is idle")
        proc = subprocess.run(["sudo", "--", "env", "LC_ALL=C", "apt-get", "-y"]
                              + options + ["install"] + exact)
        after = installed()
        (report_dir / "packages-after.json").write_text(json.dumps(after, indent=2))
        changed = {n: [v, after.get(n)] for n, v in before.items() if after.get(n) != v}
        (report_dir / "existing-version-check.json").write_text(json.dumps({
            "changed_existing": changed,
            "new_packages": {n: v for n, v in after.items() if n not in before},
            "apt_returncode": proc.returncode,
        }, indent=2))
        if changed:
            raise RuntimeError("Existing package version changed unexpectedly; STOP, inspect receipt")
        proc.check_returncode()
