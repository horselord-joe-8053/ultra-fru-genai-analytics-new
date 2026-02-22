"""
Orphan dependency and deletion ordering.

Infers dependencies from orphan set (e.g. security_group k8s-elb-{X} depends on load_balancer {X}).
Returns phased deletion order: phase 1 (roots) first, then wait, then phase 2 (dependents).
"""

# k8s-elb-{lb_name} = SG created for Classic ELB {lb_name}. SG cannot be deleted until LB ENIs released.
K8S_ELB_SG_PREFIX = "k8s-elb-"


def _sg_depends_on_lb(sg_rec: dict, all_orphans: list[dict]) -> list[tuple[str, str]]:
    """
    If SG name is k8s-elb-{X}, check for load_balancer with name {X}.
    Returns [(lb_name, lb_region)] for LBs this SG depends on.
    """
    name = sg_rec.get("name", "")
    if not name.startswith(K8S_ELB_SG_PREFIX):
        return []
    lb_name = name[len(K8S_ELB_SG_PREFIX) :]
    deps = []
    for o in all_orphans:
        if o.get("resource_type") == "load_balancer" and o.get("name") == lb_name:
            deps.append((lb_name, o.get("region") or ""))
            break
    return deps


def compute_deletion_order(orphans: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Split orphans into phase 1 (roots) and phase 2 (dependents that need wait after phase 1).

    Phase 1: target_group, load_balancer, cloudfront_oac, iam_role, and security_groups with no LB dependency.
    Phase 2: security_groups that depend on load_balancers (must wait for ENI release after LB delete).

    Within phase 1: load_balancer first (to start async ENI release), then others.
    """
    phase1: list[dict] = []
    phase2: list[dict] = []
    sg_with_deps: list[dict] = []
    sg_no_deps: list[dict] = []

    for o in orphans:
        rt = o.get("resource_type", "")
        if rt == "security_group":
            deps = _sg_depends_on_lb(o, orphans)
            if deps:
                sg_with_deps.append(o)
            else:
                sg_no_deps.append(o)
        elif rt in ("target_group", "load_balancer", "cloudfront_oac", "iam_role"):
            phase1.append(o)
        else:
            # Unknown type: treat as root
            phase1.append(o)

    # Phase 1 order: load_balancer first, then the rest
    phase1_lbs = [o for o in phase1 if o.get("resource_type") == "load_balancer"]
    phase1_rest = [o for o in phase1 if o.get("resource_type") != "load_balancer"]
    phase1_ordered = phase1_lbs + phase1_rest

    # Add SGs with no deps to phase 1
    phase1_ordered.extend(sg_no_deps)

    # Phase 2: SGs that depend on LBs (need wait after phase 1)
    phase2 = sg_with_deps

    return phase1_ordered, phase2
