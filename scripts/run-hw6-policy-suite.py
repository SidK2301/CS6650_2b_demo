#!/usr/bin/env python3
"""Sequential exploratory policy trials; each restores baseline settings before the next."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root / "evidence/hw6/policy-suite"
    folder.mkdir(parents=True, exist_ok=True)
    trials = [("target_value", 50, 240), ("target_value", 90, 120),
              ("min_capacity", 4, 90), ("max_capacity", 2, 90),
              ("scale_out_cooldown", 30, 60), ("scale_in_cooldown", 30, 60)]
    manifest = {"start_utc": datetime.now(timezone.utc).isoformat(),
                "scope": "Exploration, not a controlled steady-state benchmark; task state can carry between trials. Short windows may not outlast alarm evaluation and metric publication.",
                "trials": []}

    def save():
        (folder / "suite.json").write_text(json.dumps(manifest, indent=2) + "\n")

    save()
    for index, (field, value, duration) in enumerate(trials, 1):
        name = f"{index}-{field}-{value}"
        print("Starting", name, "for", duration, "seconds", flush=True)
        trial = {"name": name, "field": field, "value": value, "duration_seconds": duration,
                 "start_utc": datetime.now(timezone.utc).isoformat()}
        manifest["trials"].append(trial)
        save()
        subprocess.run([sys.executable, str(root / "scripts/hw6-policy-experiment.py"),
                        "--field", field, "--value", str(value), "--seconds", str(duration),
                        "--output", str(folder / f"{name}.json")], check=True)
        trial["end_utc"] = datetime.now(timezone.utc).isoformat()
        save()
    manifest["end_utc"] = datetime.now(timezone.utc).isoformat()
    save()
    print("All trials completed and baseline settings restored.", flush=True)


if __name__ == "__main__":
    main()
