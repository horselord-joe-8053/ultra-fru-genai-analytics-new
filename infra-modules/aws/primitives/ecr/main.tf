terraform { required_version = ">= 1.6.0" }

resource "aws_ecr_repository" "this" {
  name                 = var.name
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
  force_delete         = true
  tags                 = var.tags
}
