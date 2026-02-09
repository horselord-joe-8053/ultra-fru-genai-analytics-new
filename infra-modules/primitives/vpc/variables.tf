
variable "name" { type = string }
variable "cidr" { type = string }
variable "azs" { type = list(string) }
variable "public_subnet_cidrs" { type = list(string) }
variable "private_subnet_cidrs" { type = list(string) }
variable "enable_nat" { type = bool default = true }
variable "tags" { type = map(string) default = {} }

# If true, creates resources WITHOUT prevent_destroy so the durable stack can be explicitly destroyed.
# If false (default), creates resources WITH prevent_destroy.
variable "allow_destroy" {
  type    = bool
  default = false
}
