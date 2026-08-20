from __future__ import annotations

import asyncio
import os

from app.services.distribution_artifact_service import DistributionArtifactService


async def run() -> None:
    interval = max(300, int(os.getenv("DISTRIBUTION_SYNC_INTERVAL_SECONDS", "21600")))
    service = DistributionArtifactService()
    while True:
        try:
            result = await service.sync_latest_release()
            print(
                "Scheduler Pro artifact mirror ready: "
                f"release={result.get('release')} artifacts={result.get('artifacts')} "
                f"changed={result.get('changed')}"
            )
        except Exception as exc:
            # Existing mirrored artifacts remain available even if the upstream
            # repository is temporarily unavailable or has become private.
            print(f"Scheduler Pro artifact mirror warning: {exc}", flush=True)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(run())
