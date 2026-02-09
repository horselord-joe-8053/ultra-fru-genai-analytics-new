
variable "name" { type = string }
variable "subnet_ids" { type = list(string) }
variable "instance_types" {
  type    = list(string)
  default = ["t3.small"]
}
variable "desired_size" {
  type    = number
  default = 1
}
variable "tags" {
  type    = map(string)
  default = {}
}
