import json
from pathlib import Path

from openai import OpenAI


def load_env(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def main() -> None:
    env = load_env(Path("local_gateway/.env"))
    api_key = env.get("VOLC_API_KEY", "")
    base_url = env.get("VOLC_OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3")

    if not api_key:
        print("VOLC_API_KEY is empty")
        return

    client = OpenAI(api_key=api_key, base_url=base_url)
    models = client.models.list()

    names = []
    for m in models.data:
        mid = getattr(m, "id", "")
        if mid:
            names.append(mid)

    keys = ("tts", "speech", "audio", "doubao", "seed")
    filtered = [n for n in names if any(k in n.lower() for k in keys)]

    print(json.dumps({
        "total_models": len(names),
        "tts_related_models": sorted(filtered)[:200],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
