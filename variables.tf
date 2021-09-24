variable "enable_all_endpoints" {
  type = bool
  description = "setting this to true enables all endpoints provided by this module with default settings."
  default = false
}

variable "vpc_id" {
  type = string
  description = "ID for the VPC that endpoints are be associated with."
}

variable "route_table_ids" {
  type = list(string)
  description = "One or more route table IDs. Only applicable for endpoints of type Gateway."
  default = []
}

variable "subnet_ids" {
  type = list(string)
  description = "The ID of one or more subnets in which to create a network interface for endpoints. Only applicable for endpoints of type GatewayLoadBalancer and Interface."
  default = []
}

variable "security_group_ids" {
  type = list(string)
  description = "The ID of one or more security groups to associate with the endpoint's network interface. Only applicable for endpoints of type Interface. If interface gateways are to be created and no security group id's are provided, a security group allowing all traffic from inside the vpc will be created by this module."
  default = []
}

variable "private_dns_enabled" {
  type = bool
  description = "Whether or not to associate a private hosted zone with the specified VPC. Only applicable for endpoints of type Interface."
  default = false
}

variable "tags" {
  type = map(string)
  description = "A map of tags to assign to the endpoints. If configured with a provider default_tags configuration block present, tags with matching keys will overwrite those defined at the module-level."
  default = {}
}
