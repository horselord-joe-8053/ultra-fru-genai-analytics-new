"""
Render Kubernetes manifests from Jinja2 templates.

Used by tools/aws/kube/kube_apply.py and tools/gcp/kube/kube_apply.py.
Rendering runs locally (or in CI); cloud receives only the final YAML via kubectl.
"""
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

K8S_DIR = Path(__file__).resolve().parent.parent.parent / "infra_terraform" / "modules" / "cloud_shared" / "k8s"


def render(template_name: str, context: dict) -> str:
    """
    Render a .j2 template with the given context.
    template_name: e.g. "api-deployment", "api-service", "bootstrap-job", "spark-cronjob"
    """
    env = Environment(loader=FileSystemLoader(str(K8S_DIR)), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(f"{template_name}.yaml.j2")
    return template.render(**context)
