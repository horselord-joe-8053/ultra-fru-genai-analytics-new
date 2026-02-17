
variable "name" { type = string }
variable "force_destroy" {
  type    = bool
  default = true # Empty bucket before delete; required for delta/artifacts buckets that receive data
}
variable "versioning" {
  type    = bool
  default = true
}
variable "tags" {
  type    = map(string)
  default = {}
}
