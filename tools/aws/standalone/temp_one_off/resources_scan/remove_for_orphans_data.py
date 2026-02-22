#!/usr/bin/env python3
"""
Remove orphan AWS resources listed in an orphans_<YYMMDD-hhmmss>.json file.

Usage:
  # Use latest orphans data file (default)
  python tools/aws/standalone/temp_one_off/resources_scan/remove_for_orphans_data.py --dry-run
  python tools/aws/standalone/temp_one_off/resources_scan/remove_for_orphans_data.py

  # Use specific data file
  python tools/aws/standalone/temp_one_off/resources_scan/remove_for_orphans_data.py --data-file orphan_data/orphans_250210-143022.json --dry-run

The JSON file is produced by scan_aws_remaining.py and contains structured records
for removal and recovery (audit trail if a removed resource turns out to be needed).
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

from tools.aws.scope_shared.scan.orphan_deps import compute_deletion_order
from tools.aws.scope_shared.scan.orphan_rules import LB_TYPE_CLASSIC
from tools.cloud_shared.logging import logger
from tools.cloud_shared.retry import run_with_heartbeat, update_heartbeat

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ORPHAN_DATA_DIR = os.path.join(_SCRIPT_DIR, "orphan_data")

# Wait for SG to become deletable after LB delete (AWS releases ENIs async)
WAIT_TIMEOUT_SEC = int(os.environ.get("ORPHAN_REMOVAL_WAIT_TIMEOUT_SEC", "1800"))
POLL_INTERVAL_SEC = int(os.environ.get("ORPHAN_REMOVAL_POLL_INTERVAL_SEC", "30"))


def _find_latest_orphans_file() -> str | None:
    """Return path to the most recent orphans_<ts>.json file, or None."""
    if not os.path.isdir(ORPHAN_DATA_DIR):
        return None
    candidates = [
        f for f in os.listdir(ORPHAN_DATA_DIR)
        if f.startswith("orphans_") and f.endswith(".json")
    ]
    if not candidates:
        return None
    # Sort by timestamp (filename) descending
    candidates.sort(reverse=True)
    return os.path.join(ORPHAN_DATA_DIR, candidates[0])


def _load_orphans_data(path: str) -> dict:
    """Load and validate orphans JSON."""
    with open(path) as f:
        data = json.load(f)
    if "orphans_definitely" not in data:
        raise ValueError(f"Invalid orphans file: missing 'orphans_definitely'")
    return data


_HEARTBEAT_INTERVAL_SEC = 15


def _aws(cmd: list[str], region: str | None = None, description: str | None = None) -> tuple[int, str]:
    """Run AWS CLI with heartbeat for long-running ops. Returns (returncode, stdout)."""
    full = ["aws"] + cmd
    if region:
        full += ["--region", region]
    svc = cmd[0] if cmd else "aws"
    desc = description or f"AWS {svc}"
    result = run_with_heartbeat(
        full,
        cwd=os.getcwd(),
        env=os.environ.copy(),
        description=desc,
        interval_sec=_HEARTBEAT_INTERVAL_SEC,
    )
    return result.returncode, result.stdout or result.stderr or ""


def _delete_cloudfront_oac(rec: dict, dry_run: bool) -> tuple[bool, str]:
    """Delete CloudFront OAC. Needs oac_id from extra or lookup by name."""
    oac_id = (rec.get("extra") or {}).get("oac_id")
    if not oac_id:
        # Lookup by name
        code, out = _aws(["cloudfront", "list-origin-access-controls"])
        if code != 0:
            return False, f"list-oac failed: {out}"
        data = json.loads(out) if out else {}
        for item in data.get("OriginAccessControlList", {}).get("Items") or []:
            if item.get("Name") == rec["name"]:
                oac_id = item.get("Id")
                break
        if not oac_id:
            return False, f"OAC '{rec['name']}' not found"
    if dry_run:
        return True, f"[dry-run] would delete cloudfront OAC id={oac_id} name={rec['name']}"
    # Get ETag first (required for delete)
    code, out = _aws(["cloudfront", "get-origin-access-control", "--id", oac_id])
    if code != 0:
        return False, f"get-oac failed: {out}"
    etag = json.loads(out).get("ETag", "").strip('"')
    code, out = _aws(
        ["cloudfront", "delete-origin-access-control", "--id", oac_id, "--if-match", etag],
        description=f"Deleting CloudFront OAC {rec['name']}",
    )
    return code == 0, out if code != 0 else "deleted"


def _delete_iam_role(rec: dict, dry_run: bool) -> tuple[bool, str]:
    """Delete IAM role. Must detach policies first."""
    name = rec["name"]
    if dry_run:
        return True, f"[dry-run] would delete IAM role {name}"
    # Detach managed policies
    code, out = _aws(["iam", "list-attached-role-policies", "--role-name", name])
    if code == 0 and out:
        data = json.loads(out)
        for p in data.get("AttachedPolicies", []):
            _aws(["iam", "detach-role-policy", "--role-name", name, "--policy-arn", p["PolicyArn"]])
    # Delete inline policies
    code, out = _aws(["iam", "list-role-policies", "--role-name", name])
    if code == 0 and out:
        data = json.loads(out)
        for p in data.get("PolicyNames", []):
            _aws(["iam", "delete-role-policy", "--role-name", name, "--policy-name", p])
    code, out = _aws(
        ["iam", "delete-role", "--role-name", name],
        description=f"Deleting IAM role {name}",
    )
    return code == 0, out if code != 0 else "deleted"


def _delete_load_balancer(rec: dict, dry_run: bool) -> tuple[bool, str]:
    """Delete Classic ELB (we only remove classic type)."""
    region = rec.get("region")
    if not region:
        return False, "load_balancer requires region"
    lb_type = (rec.get("extra") or {}).get("lb_type", "")
    if lb_type != LB_TYPE_CLASSIC:
        return False, f"skip non-classic lb {rec['name']}"
    name = rec["name"]
    if dry_run:
        return True, f"[dry-run] would delete Classic ELB {name} in {region}"
    code, out = _aws(
        ["elb", "delete-load-balancer", "--load-balancer-name", name],
        region=region,
        description=f"Deleting Classic ELB {name}",
    )
    return code == 0, out if code != 0 else "deleted"


def _delete_security_group(rec: dict, dry_run: bool) -> tuple[bool, str]:
    """Delete security group. Prefer group_id from extra."""
    region = rec.get("region")
    if not region:
        return False, "security_group requires region"
    group_id = (rec.get("extra") or {}).get("group_id")
    if not group_id:
        # Lookup by name
        code, out = _aws([
            "ec2", "describe-security-groups",
            "--filters", f"Name=group-name,Values={rec['name']}",
        ], region=region)
        if code != 0:
            return False, f"describe-sg failed: {out}"
        data = json.loads(out) if out else {}
        sgs = data.get("SecurityGroups", [])
        if not sgs:
            return False, f"SG '{rec['name']}' not found"
        group_id = sgs[0].get("GroupId")
    if dry_run:
        return True, f"[dry-run] would delete SG {group_id} ({rec['name']}) in {region}"
    code, out = _aws(
        ["ec2", "delete-security-group", "--group-id", group_id],
        region=region,
        description=f"Deleting security group {rec['name']}",
    )
    return code == 0, out if code != 0 else "deleted"


def _is_dependency_violation(out: str) -> bool:
    """Check if AWS error indicates SG has dependent objects (ENIs from deleted ELB)."""
    return "DependencyViolation" in out or "dependent object" in out.lower()


def _delete_security_group_with_wait(rec: dict, dry_run: bool) -> tuple[bool, str]:
    """
    Delete SG with retry on DependencyViolation. After LB delete, ENIs release async;
    poll until SG is deletable or timeout.
    """
    if dry_run:
        return _delete_security_group(rec, dry_run=True)
    deadline = time.monotonic() + WAIT_TIMEOUT_SEC
    start = time.monotonic()
    last_heartbeat = 0
    last_msg = ""
    while time.monotonic() < deadline:
        success, msg = _delete_security_group(rec, dry_run=False)
        last_msg = msg
        if success:
            return True, msg
        if not _is_dependency_violation(msg):
            return False, msg
        elapsed = int(time.monotonic() - start)
        last_heartbeat = update_heartbeat(
            elapsed,
            last_heartbeat,
            POLL_INTERVAL_SEC,
            f"Waiting for SG {rec['name']} to become deletable (ENI release after LB delete, can take 10–30 min) ... ({elapsed}s elapsed)",
        )
        time.sleep(POLL_INTERVAL_SEC)
    return False, f"timeout after {WAIT_TIMEOUT_SEC}s: {last_msg}"


def _delete_target_group(rec: dict, dry_run: bool) -> tuple[bool, str]:
    """Delete target group. Prefer target_group_arn from extra."""
    region = rec.get("region")
    if not region:
        return False, "target_group requires region"
    arn = (rec.get("extra") or {}).get("target_group_arn")
    if not arn:
        code, out = _aws([
            "elbv2", "describe-target-groups",
            "--names", rec["name"],
        ], region=region)
        if code != 0:
            return False, f"describe-tg failed: {out}"
        data = json.loads(out) if out else {}
        tgs = data.get("TargetGroups", [])
        if not tgs:
            return False, f"Target group '{rec['name']}' not found"
        arn = tgs[0].get("TargetGroupArn")
    if dry_run:
        return True, f"[dry-run] would delete target group {rec['name']} in {region}"
    code, out = _aws(
        ["elbv2", "delete-target-group", "--target-group-arn", arn],
        region=region,
        description=f"Deleting target group {rec['name']}",
    )
    return code == 0, out if code != 0 else "deleted"


_DELETERS = {
    "cloudfront_oac": _delete_cloudfront_oac,
    "iam_role": _delete_iam_role,
    "load_balancer": _delete_load_balancer,
    "security_group": _delete_security_group,
    "target_group": _delete_target_group,
}


def main():
    ap = argparse.ArgumentParser(description="Remove orphan AWS resources from orphans JSON")
    ap.add_argument(
        "--data-file",
        default=None,
        help="Relative path to orphans_<ts>.json (default: latest in orphan_data/)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print what would be done, do not delete")
    ap.add_argument(
        "--definitely-only",
        action="store_true",
        help="Only remove 'definitely' orphans; skip 'likely'",
    )
    args = ap.parse_args()

    if args.data_file:
        path = os.path.join(_SCRIPT_DIR, args.data_file) if not os.path.isabs(args.data_file) else args.data_file
        if not os.path.isfile(path):
            # Try relative to orphan_data
            path = os.path.join(ORPHAN_DATA_DIR, os.path.basename(args.data_file))
        if not os.path.isfile(path):
            logger.error(f"Data file not found: {args.data_file}")
            sys.exit(1)
    else:
        path = _find_latest_orphans_file()
        if not path:
            logger.error("No orphans data file found. Run scan_aws_remaining.py first.")
            sys.exit(1)
        logger.info(f"Using latest: {os.path.basename(path)}")

    data = _load_orphans_data(path)
    ts = data.get("scan_timestamp", "unknown")
    prefix = data.get("prefix", "")
    env = data.get("env", "")

    to_remove: list[dict] = list(data.get("orphans_definitely", []))
    if not args.definitely_only:
        to_remove.extend(data.get("orphans_likely", []))

    if not to_remove:
        logger.info("No orphans to remove.")
        return

    phase1, phase2 = compute_deletion_order(to_remove)
    total = len(phase1) + len(phase2)
    if phase2:
        logger.info(f"Deletion order: phase 1 (roots)={len(phase1)}, phase 2 (after wait for ENI release)={len(phase2)}")

    mode = "[DRY-RUN] " if args.dry_run else ""
    logger.step(f"{mode}Removing {total} orphan(s) from scan {ts} (prefix={prefix}, env={env})")
    logger.info(f"Loaded from {path}")

    ok = 0
    fail = 0
    removed_records: list[dict] = []
    start_time = time.monotonic()
    idx = 0

    def _do_delete(rec: dict, deleter, phase2_sg: bool) -> tuple[bool, str]:
        if phase2_sg and rec.get("resource_type") == "security_group":
            return _delete_security_group_with_wait(rec, args.dry_run)
        return deleter(rec, args.dry_run)

    for phase_name, phase_list in [("Phase 1 (roots)", phase1), ("Phase 2 (after wait)", phase2)]:
        if not phase_list:
            continue
        if len(phase1) + len(phase2) > 1:
            logger.info(f"--- {phase_name}: {len(phase_list)} item(s) ---")
        phase2_sg = phase_name.startswith("Phase 2")
        for rec in phase_list:
            idx += 1
            rt = rec.get("resource_type", "")
            display = rec.get("display", rec["name"])
            deleter = _DELETERS.get(rt)
            if not deleter:
                logger.warning(f"[{idx}/{total}] SKIP {display} (unsupported type {rt})")
                continue
            logger.info(f"[{idx}/{total}] Deleting {rt} {rec['name']}...")
            success, msg = _do_delete(rec, deleter, phase2_sg)
            if success:
                ok += 1
                logger.info(f"  -> OK: {msg}")
                if not args.dry_run:
                    removed_records.append({**rec, "removed_at": datetime.utcnow().isoformat() + "Z"})
            else:
                fail += 1
                logger.error(f"  -> FAIL: {msg}")

    # Write removed_<ts>.json as recovery/audit record
    if removed_records and not args.dry_run:
        os.makedirs(ORPHAN_DATA_DIR, exist_ok=True)
        rm_ts = datetime.utcnow().strftime("%y%m%d-%H%M%S")
        rm_path = os.path.join(ORPHAN_DATA_DIR, f"removed_{rm_ts}.json")
        with open(rm_path, "w") as f:
            json.dump({
                "removed_at": datetime.utcnow().isoformat() + "Z",
                "source_scan": ts,
                "prefix": prefix,
                "env": env,
                "removed": removed_records,
                "recovery_hints": data.get("recovery_hints", {}),
            }, f, indent=2)
        logger.success(f"Removal record written to: {rm_path}")

    elapsed = int(time.monotonic() - start_time)
    logger.step(f"{mode}Done: {ok} ok, {fail} failed (took {elapsed}s)")
    if fail and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()
