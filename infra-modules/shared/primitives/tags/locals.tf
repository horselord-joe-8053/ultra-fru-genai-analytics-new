
locals {
  common_tags = merge(
    {
      owner       = "fru"
      managed_by  = "tofu"
    },
    var.extra_tags
  )
}
