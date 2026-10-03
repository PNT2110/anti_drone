"""Publish the static Hugging Face Space that fronts the SkyWatch server.

Free Hugging Face accounts can only host static Spaces, so the Space shows
the console served by our own GPU server. Re-run this whenever the server's
public URL changes (a trycloudflare.com URL changes on every tunnel restart).

Usage:
    python scripts/publish_hf_static.py https://<public-url-of-the-server>
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

TEMPLATE = Path(__file__).resolve().parents[1] / "deploy" / "hf-static"
PLACEHOLDER = "__BACKEND_URL__"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backend_url", help="Public https URL of the running web server")
    parser.add_argument("--space", default=None, help="<user>/<space>; default <logged-in user>/skywatch-anti-drone")
    args = parser.parse_args()

    backend_url = args.backend_url.rstrip("/")
    if not backend_url.startswith("https://"):
        raise SystemExit("backend_url must start with https:// (the Space is served over HTTPS)")

    api = HfApi()
    space = args.space or f"{api.whoami()['name']}/skywatch-anti-drone"
    with tempfile.TemporaryDirectory() as folder:
        index = (TEMPLATE / "index.html").read_text(encoding="utf-8")
        if PLACEHOLDER not in index:
            raise SystemExit(f"{PLACEHOLDER} missing from index.html template")
        (Path(folder) / "index.html").write_text(index.replace(PLACEHOLDER, backend_url), encoding="utf-8")
        (Path(folder) / "README.md").write_text(
            (TEMPLATE / "README.md").read_text(encoding="utf-8"), encoding="utf-8"
        )
        api.create_repo(space, repo_type="space", space_sdk="static", private=False, exist_ok=True)
        api.upload_folder(
            repo_id=space, repo_type="space", folder_path=folder,
            commit_message=f"Point console at {backend_url}",
        )
    print(f"Published https://huggingface.co/spaces/{space} -> {backend_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
