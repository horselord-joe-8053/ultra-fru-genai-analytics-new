
variable "name" { type = string }
variable "versioning" {
  type    = bool
  default = true
}
variable "tags" {
  type    = map(string)
  default = {}
}
