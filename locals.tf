locals {
  sg_count = length(var.security_group_ids) == 0 && length(var.enabled_interface_endpoints) > 0 ? 1 : 0
  sg_ids    = local.sg_count == 1 ? [resource.aws_security_group.endpoints[0].id] : var.security_group_ids
}
