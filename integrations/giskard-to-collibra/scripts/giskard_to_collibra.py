#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests
from giskard_hub import HubClient
from giskard_hub.types import Severity

MAX_MONITORS = 36  # Collibra's Quality-tab chart limit

TYPE_AI_AGENT = {"publicId": "AIAgent"}
TYPE_AI_AGENT_VERSION = {"publicId": "AIAgentVersion"}
TYPE_AI_ENDPOINT = {"publicId": "AIEndpoint"}
TYPE_AI_MONITOR = {"publicId": "AIMonitor"}

COMPLEX_REL_DEPLOYMENT_TYPE = "00000000-0000-0000-0000-000000007505"
LEG_VERSION_RELATION = "00000000-0000-0000-0000-000000007213"
LEG_ENDPOINT_RELATION = "00000000-0000-0000-0000-000000007214"
REL_AGENT_HAS_VERSION = "00000000-0000-0000-0000-000000007206:TARGET"
REL_DEPLOYMENT_HAS_MONITOR = "00000000-0000-0000-0000-000000007215:TARGET"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def require_env(*names: str) -> list[str]:
    values = [os.environ.get(n, "") for n in names]
    missing = [n for n, v in zip(names, values) if not v]
    if missing:
        sys.exit("Missing values in .env or environment: " + ", ".join(missing))
    return values


def deterministic_uuid(domain_id: str, asset_name: str, type_public_id: str) -> str:
    raw = f"{domain_id}>{asset_name}>{type_public_id}"
    return str(uuid.UUID(bytes=hashlib.md5(raw.encode("utf-8")).digest(), version=3))


def asset(
    name: str,
    asset_type: dict,
    domain_id: str,
    relations: dict | None = None,
    attributes: dict | None = None,
) -> dict:
    cmd = {
        "resourceType": "Asset",
        "identifier": {
            "id": deterministic_uuid(domain_id, name, asset_type["publicId"])
        },
        "type": asset_type,
        "name": name,
        "displayName": name,
        "domain": {"id": domain_id},
    }
    if relations:
        cmd["relations"] = relations
    if attributes:
        cmd["attributes"] = attributes
    return cmd


def resolve_scan(hub, args):
    if args.scan_id:
        return hub.scans.retrieve(args.scan_id)
    scans = [
        s for s in hub.scans.list(project_id=args.project_id) if s.state == "finished"
    ]
    if not scans:
        sys.exit(f"Project {args.project_id} has no finished scans.")
    return max(scans, key=lambda s: s.created_at)


def parse_args():
    p = argparse.ArgumentParser(
        description="Export a Giskard scan's results into Collibra AI Governance."
    )
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--scan-id", help="Giskard scan ID to export")
    target.add_argument(
        "--project-id", help="Giskard project ID; exports its latest finished scan"
    )
    target.add_argument(
        "--list-projects",
        action="store_true",
        help="List Giskard projects (id and name) and exit",
    )
    p.add_argument("--max-monitors", type=int, default=MAX_MONITORS)
    p.add_argument("--output", default="import_agents.json")
    return p.parse_args()


def main():
    load_dotenv(Path(".env"))
    load_dotenv(Path(__file__).parent / ".env")
    args = parse_args()

    require_env("GISKARD_HUB_BASE_URL", "GISKARD_HUB_API_KEY")
    hub = HubClient()

    if args.list_projects:
        for p in hub.projects.list():
            print(f"{p.id}  {p.name}")
        return

    collibra_url, domain_id, user, password = require_env(
        "COLLIBRA_URL", "COLLIBRA_DOMAIN_ID", "COLLIBRA_USER", "COLLIBRA_PASSWORD"
    )
    collibra_url = collibra_url.rstrip("/")
    auth = (user, password)

    scan = resolve_scan(hub, args)
    agent = hub.agents.retrieve(scan.agent.id)
    probes = hub.scans.list_probes(scan.id)
    print(f"Scan {scan.id} (agent: {agent.name}, {len(probes)} probes)")

    if len(probes) > args.max_monitors:
        print(
            f"Note: pushing only the first {args.max_monitors} probes "
            f"(Collibra Quality-tab chart limit)."
        )
        probes = probes[: args.max_monitors]

    name_version = f"{agent.name} Version"
    name_endpoint = f"{agent.name} Endpoint"
    version_id = deterministic_uuid(domain_id, name_version, "AIAgentVersion")
    endpoint_id = deterministic_uuid(domain_id, name_endpoint, "AIEndpoint")

    agent_asset = asset(
        agent.name,
        TYPE_AI_AGENT,
        domain_id,
        relations={REL_AGENT_HAS_VERSION: [{"id": version_id}]},
    )
    version_asset = asset(name_version, TYPE_AI_AGENT_VERSION, domain_id)
    endpoint_asset = asset(
        name_endpoint,
        TYPE_AI_ENDPOINT,
        domain_id,
        attributes={
            "AccessMethod": [{"value": "MCP"}],
            "AccessInstructions": [{"value": agent.url or ""}],
        },
    )
    monitor_assets = [asset(p.name, TYPE_AI_MONITOR, domain_id) for p in probes]

    deployment_cr = {
        "resourceType": "Complex Relation",
        "identifier": {
            "externalSystemId": "giskard",
            "externalEntityId": f"{agent.id}:deployment",
        },
        "complexRelationType": {"id": COMPLEX_REL_DEPLOYMENT_TYPE},
        "relations": {
            f"{LEG_VERSION_RELATION}:TARGET": [{"id": version_id}],
            f"{LEG_ENDPOINT_RELATION}:TARGET": [{"id": endpoint_id}],
            REL_DEPLOYMENT_HAS_MONITOR: [
                {"id": m["identifier"]["id"]} for m in monitor_assets
            ],
        },
        "attributes": {"TrafficSplitPercentage": [{"value": 100}]},
    }

    commands = [
        agent_asset,
        version_asset,
        endpoint_asset,
        deployment_cr,
        *monitor_assets,
    ]
    with open(args.output, "w") as f:
        json.dump(commands, f, indent=2)
    print(f"Import file written -> {args.output} ({len(commands)} commands)")

    print(f"\nImporting into {collibra_url} ...")
    with open(args.output, "rb") as f:
        resp = requests.post(
            f"{collibra_url}/rest/2.0/import/json-job",
            auth=auth,
            files={"file": (os.path.basename(args.output), f, "application/json")},
            data={"fileName": os.path.basename(args.output), "continueOnError": "true"},
            timeout=30,
        )
    resp.raise_for_status()
    job_id = resp.json()["id"]

    result = None
    for _ in range(40):
        time.sleep(3)
        job = requests.get(
            f"{collibra_url}/rest/2.0/jobs/{job_id}", auth=auth, timeout=10
        ).json()
        print(f"  {job['state']}")
        if job["state"] in ("COMPLETED", "ERROR", "CANCELED"):
            result = job.get("result")
            print(f"Result: {result}\n{job.get('message', '')}")
            break

    if result != "SUCCESS":
        sys.exit(f"Import did not complete cleanly (result={result}).")

    # Metrics must target the AI Agent Version id, not the agent id.
    # giskard-hub 3.1.x does not declare start_datetime on Scan, so it comes back
    # as a raw ISO string or is absent. 3.2+ returns a datetime. str()[:10] gives
    # the YYYY-MM-DD date in every case.
    scan_date = str(getattr(scan, "start_datetime", None) or scan.created_at)[:10]
    metrics = [
        {
            "correlationId": scan.id,
            "assetId": version_id,
            "date": scan_date,
            "data": {
                "type": "PASS_FAIL_MONITOR",
                "monitorAssetId": monitor["identifier"]["id"],
                "passCount": sum(
                    m.count for m in probe.metrics or [] if m.severity == Severity.SAFE
                ),
                "failCount": sum(
                    m.count for m in probe.metrics or [] if m.severity != Severity.SAFE
                ),
                "errorCount": 0,
            },
        }
        for probe, monitor in zip(probes, monitor_assets)
    ]

    print(f"\nPushing {len(metrics)} monitor metrics for {scan_date} ...")
    resp = requests.post(
        f"{collibra_url}/rest/aiGovernance/v1/metrics/batch",
        auth=auth,
        json={"metrics": metrics},
        timeout=30,
    )
    if not resp.ok:
        sys.exit(f"HTTP {resp.status_code}: {resp.text}")

    print(
        f"Done. Agent in Collibra: {collibra_url}/asset/{agent_asset['identifier']['id']}"
    )


if __name__ == "__main__":
    main()
