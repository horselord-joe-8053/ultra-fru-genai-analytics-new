variable "cluster_name" { type = string }
variable "location" { type = string }
variable "initial_node_count" {
  type    = number
  default = 1
}
