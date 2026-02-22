"""AWS scan config and classification for resource discovery."""

from tools.aws.scope_shared.scan.config import (
    FRU_CATEGORIES,
    classify_project_category,
    is_aws_builtin,
    is_project_resource,
)

__all__ = [
    "FRU_CATEGORIES",
    "classify_project_category",
    "is_aws_builtin",
    "is_project_resource",
]
