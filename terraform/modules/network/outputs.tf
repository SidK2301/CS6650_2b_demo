output "subnet_ids" {
  description = "IDs of the default VPC subnets"
  value       = data.aws_subnets.default.ids
}

output "security_group_id" {
  description = "Security group ID for ECS"
  value       = aws_security_group.this.id
}

output "target_group_arn" {
  value = try(aws_lb_target_group.this[0].arn, null)
}
output "target_group_suffix" {
  value = try(aws_lb_target_group.this[0].arn_suffix, null)
}
output "alb_suffix" {
  value = try(aws_lb.this[0].arn_suffix, null)
}
output "alb_dns" {
  value = try(aws_lb.this[0].dns_name, null)
}
