variable "test_input" {
  type = object({
    a = bool
    b = bool
    c = bool
  })
  default = {
    b = true
  }
  "validation": {
        "condition": "${var.enabled_gateway_endpoints} == [] ? true : can([for s in ${var.enabled_gateway_endpoints} : regex(\"||$dynamodb^||$s3^\", s)]",
        "error_message": "Endpoint names can only contain one or more of the following ['dynamodb', 's3']."
      }
}

module "testmod" {
  source = "../"
  test_input = var.test_input
}

output "test_output" {
  value = testmod.test_output
}
