output "ecs_cluster_name" {
  description = "Name of the created ECS cluster"
  value       = module.ecs.cluster_name
}

output "ecs_service_name" {
  description = "Name of the running ECS service"
  value       = module.ecs.service_name
}
output "aws_region" {
  value = var.aws_region
}

output "image_tag" {
  value = local.image_tag
}

output "alb_dns" {
  value = module.network.alb_dns
}
output "target_group_arn" {
  value = module.network.target_group_arn
}
