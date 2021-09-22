variable "test_input" {
  type = map(any)
  default = {"a": 1, "b": 2}
}

output "test_output" {
  value = [for k, v in var.test_input: k]
}