import json
import re
import sys
from pathlib import Path
from importlib import metadata

from packaging.markers import default_environment
from packaging.requirements import Requirement


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    req_name = (
        "requirements_forwindows.txt"
        if sys.platform == "win32"
        else "requirements_forubuntu.txt"
    )
    req_file = root / req_name
    result_file = root / "scripts" / "compare_requirements_result.json"
    raw_lines = req_file.read_text(encoding="utf-8").splitlines()

    env = default_environment()
    reqs = []
    for line in raw_lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            req = Requirement(s)
        except Exception:
            continue
        if req.marker is not None and not req.marker.evaluate(env):
            continue
        reqs.append(req)

    installed = {}
    for dist in metadata.distributions():
        name = dist.metadata.get("Name")
        if not name:
            continue
        installed[norm(name)] = dist.version

    missing = []
    version_mismatch = []
    matched = []

    for req in reqs:
        key = norm(req.name)
        spec = str(req.specifier) if req.specifier else ""
        installed_version = installed.get(key)

        if installed_version is None:
            missing.append({"name": req.name, "required": spec})
            continue

        ok = True
        if req.specifier:
            ok = req.specifier.contains(installed_version, prereleases=True)

        if ok:
            matched.append(
                {
                    "name": req.name,
                    "required": spec or "*",
                    "installed": installed_version,
                }
            )
        else:
            version_mismatch.append(
                {
                    "name": req.name,
                    "required": spec,
                    "installed": installed_version,
                }
            )

    required_keys = {norm(req.name) for req in reqs}
    extras = [
        {"name": name, "installed": version}
        for name, version in installed.items()
        if name not in required_keys
    ]

    result = {
        "requirements_considered": len(reqs),
        "matched_count": len(matched),
        "missing": missing,
        "version_mismatch": version_mismatch,
        "extras_count": len(extras),
        "extras_sample": extras[:80],
    }
    result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出简要摘要，完整结果请查看 result_file
    print(json.dumps({
        "requirements_considered": result["requirements_considered"],
        "matched_count": result["matched_count"],
        "missing_count": len(result["missing"]),
        "version_mismatch_count": len(result["version_mismatch"]),
        "extras_count": result["extras_count"],
        "result_file": str(result_file),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
