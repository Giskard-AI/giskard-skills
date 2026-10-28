#!/usr/bin/env python3
"""One-shot Vertex GLM smoke test (x-goog-api-key auth)."""

from __future__ import annotations

import asyncio
import os
import sys

from giskard.llm import acompletion, configure


async def _main() -> int:
    if not os.environ.get("GLM_API_KEY"):
        print("smoke: FAIL — GLM_API_KEY unset")
        return 1
    base = os.environ.get(
        "GLM_BASE_URL",
        "https://aiplatform.googleapis.com/v1/projects/gsk-dev-497008/locations/global/endpoints/openapi",
    )
    model_id = os.environ.get("GLM_MODEL_ID", "zai-org/glm-5.2-maas")
    configure(
        "openai",
        provider="openai",
        api_key="unused",
        base_url=base,
        default_headers={"x-goog-api-key": os.environ["GLM_API_KEY"]},
    )
    try:
        resp = await acompletion(
            model=f"openai/{model_id}",
            messages=[{"role": "user", "content": "Reply with exactly the word smoke-ok and nothing else."}],
            max_tokens=256,
        )
        text = (resp.choices[0].message.content or "").strip()
        ok = "smoke-ok" in text
        print(f"smoke: {'ok' if ok else 'fail'} — model={model_id} content={text[:80]!r}")
        return 0 if ok else 2
    except Exception as exc:
        print(f"smoke: fail — {type(exc).__name__}: {str(exc)[:200]}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
