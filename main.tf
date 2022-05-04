data "aws_region" "current" {}

data "aws_vpc" "selected" {
  id = var.vpc_id
}

locals {
  sg_count = length(var.security_group_ids) == 0 && length(var.enabled_interface_endpoints) > 0 ? 1 : 0
  sg_ids   = local.sg_count == 1 ? [resource.aws_security_group.endpoints[0].id] : var.security_group_ids
}

resource "aws_security_group" "endpoints" {
  count       = local.sg_count
  name        = "vpc_endpoints"
  description = "VPC endpoints created by the terraform vpc-endpoint module are attached to this security group"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_security_group_rule" "endpoints_allow_ingress_tcp443_from_vpc_cidr" {
  count             = local.sg_count
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [data.aws_vpc.selected.cidr_block]
  ipv6_cidr_blocks  = data.aws_vpc.selected.ipv6_cidr_block != "" ? [data.aws_vpc.selected.ipv6_cidr_block] : null
  security_group_id = aws_security_group.endpoints[count.index].id
}
