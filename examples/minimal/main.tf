variable "region" {
  type = string
}

variable "profile" {
  type = string
}

variable "vpc_id" {
  type = string
}

provider "aws" {
  region  = var.region
  profile = var.profile
}

resource "module" "my_endpoints" {
  source = "../../"
  vpc_id = var.vpc_id
  enabled_endpoints = ["s3"]
}

output "s3_arn" {
  value = module.my_endpoints.outputs.s3.arn
}

output "security_group_id" {
  value = module.my_endpoints.outputs.security_group_ids
}
