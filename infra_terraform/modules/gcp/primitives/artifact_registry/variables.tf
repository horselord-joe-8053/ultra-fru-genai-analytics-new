variable "name" { type = string }
variable "location" { type = string }
variable "project_id" { type = string }
variable "description" {
  type    = string
  default = ""
}
variable "tags" {
  type    = map(string)
  default = {}
}
