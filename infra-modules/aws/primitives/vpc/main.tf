
terraform { required_version = ">= 1.6.0" }

locals {
  protected = var.allow_destroy ? 0 : 1
  unprotected = var.allow_destroy ? 1 : 0
}

# ---------- VPC ----------
resource "aws_vpc" "protected" {
  count                 = local.protected
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = var.name })
  lifecycle { prevent_destroy = true }
}

resource "aws_vpc" "unprotected" {
  count                 = local.unprotected
  cidr_block           = var.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = var.name })
}

locals {
  vpc_id = var.allow_destroy ? aws_vpc.unprotected[0].id : aws_vpc.protected[0].id
}

# ---------- IGW ----------
resource "aws_internet_gateway" "protected" {
  count = local.protected
  vpc_id = local.vpc_id
  tags   = merge(var.tags, { Name = "${var.name}-igw" })
  lifecycle { prevent_destroy = true }
}
resource "aws_internet_gateway" "unprotected" {
  count = local.unprotected
  vpc_id = local.vpc_id
  tags   = merge(var.tags, { Name = "${var.name}-igw" })
}

# ---------- Public Subnets ----------
resource "aws_subnet" "public_protected" {
  count                   = local.protected * length(var.public_subnet_cidrs)
  vpc_id                  = local.vpc_id
  cidr_block              = var.public_subnet_cidrs[count.index]
  map_public_ip_on_launch = true
  availability_zone       = var.azs[count.index]
  tags                    = merge(var.tags, { Name = "${var.name}-public-${count.index}" })
  lifecycle { prevent_destroy = true }
}

resource "aws_subnet" "public_unprotected" {
  count                   = local.unprotected * length(var.public_subnet_cidrs)
  vpc_id                  = local.vpc_id
  cidr_block              = var.public_subnet_cidrs[count.index]
  map_public_ip_on_launch = true
  availability_zone       = var.azs[count.index]
  tags                    = merge(var.tags, { Name = "${var.name}-public-${count.index}" })
}

locals {
  public_subnet_ids = var.allow_destroy ? [for s in aws_subnet.public_unprotected : s.id] : [for s in aws_subnet.public_protected : s.id]
}

# ---------- Private Subnets ----------
resource "aws_subnet" "private_protected" {
  count             = local.protected * length(var.private_subnet_cidrs)
  vpc_id            = local.vpc_id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name}-private-${count.index}" })
  lifecycle { prevent_destroy = true }
}

resource "aws_subnet" "private_unprotected" {
  count             = local.unprotected * length(var.private_subnet_cidrs)
  vpc_id            = local.vpc_id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name}-private-${count.index}" })
}

locals {
  private_subnet_ids = var.allow_destroy ? [for s in aws_subnet.private_unprotected : s.id] : [for s in aws_subnet.private_protected : s.id]
}

# ---------- Public Route Table ----------
resource "aws_route_table" "public_protected" {
  count = local.protected
  vpc_id = local.vpc_id
  tags   = merge(var.tags, { Name = "${var.name}-public-rt" })
  lifecycle { prevent_destroy = true }
}
resource "aws_route_table" "public_unprotected" {
  count = local.unprotected
  vpc_id = local.vpc_id
  tags   = merge(var.tags, { Name = "${var.name}-public-rt" })
}

locals {
  public_rt_id = var.allow_destroy ? aws_route_table.public_unprotected[0].id : aws_route_table.public_protected[0].id
}

resource "aws_route" "public_inet" {
  route_table_id         = local.public_rt_id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = var.allow_destroy ? aws_internet_gateway.unprotected[0].id : aws_internet_gateway.protected[0].id
}

resource "aws_route_table_association" "public_assoc" {
  count          = length(local.public_subnet_ids)
  subnet_id      = local.public_subnet_ids[count.index]
  route_table_id = local.public_rt_id
}

# ---------- NAT (optional) ----------
resource "aws_eip" "nat_protected" {
  count = (var.enable_nat ? local.protected : 0)
  vpc   = true
  tags  = merge(var.tags, { Name = "${var.name}-nat-eip" })
  lifecycle { prevent_destroy = true }
}
resource "aws_eip" "nat_unprotected" {
  count = (var.enable_nat ? local.unprotected : 0)
  vpc   = true
  tags  = merge(var.tags, { Name = "${var.name}-nat-eip" })
}

resource "aws_nat_gateway" "nat_protected" {
  count         = (var.enable_nat ? local.protected : 0)
  allocation_id = aws_eip.nat_protected[0].id
  subnet_id     = local.public_subnet_ids[0]
  tags          = merge(var.tags, { Name = "${var.name}-nat" })
  lifecycle { prevent_destroy = true }
}

resource "aws_nat_gateway" "nat_unprotected" {
  count         = (var.enable_nat ? local.unprotected : 0)
  allocation_id = aws_eip.nat_unprotected[0].id
  subnet_id     = local.public_subnet_ids[0]
  tags          = merge(var.tags, { Name = "${var.name}-nat" })
}

locals {
  nat_gw_id = var.enable_nat ? (var.allow_destroy ? aws_nat_gateway.nat_unprotected[0].id : aws_nat_gateway.nat_protected[0].id) : null
}

resource "aws_route_table" "private_protected" {
  count = (var.enable_nat ? local.protected : 0)
  vpc_id = local.vpc_id
  tags   = merge(var.tags, { Name = "${var.name}-private-rt" })
  lifecycle { prevent_destroy = true }
}
resource "aws_route_table" "private_unprotected" {
  count = (var.enable_nat ? local.unprotected : 0)
  vpc_id = local.vpc_id
  tags   = merge(var.tags, { Name = "${var.name}-private-rt" })
}

locals {
  private_rt_id = var.enable_nat ? (var.allow_destroy ? aws_route_table.private_unprotected[0].id : aws_route_table.private_protected[0].id) : null
}

resource "aws_route" "private_nat" {
  count                  = var.enable_nat ? 1 : 0
  route_table_id         = local.private_rt_id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = local.nat_gw_id
}

resource "aws_route_table_association" "private_assoc" {
  count          = var.enable_nat ? length(local.private_subnet_ids) : 0
  subnet_id      = local.private_subnet_ids[count.index]
  route_table_id = local.private_rt_id
}
