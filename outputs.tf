output "interface_endpoints" {
  description = "map of properties for all enabled interface endpoints"
  value       = { for k, v in local.interface_output_dict : k => v if v != null }
}

output "gateway_endpoints" {
  description = "map of properties for all enabled gateway endpoints"
  value       = { for k, v in local.gateway_output_dict : k => v if v != null }
}
