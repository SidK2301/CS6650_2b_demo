resource "aws_cloudwatch_dashboard" "hw6_scaling" {
  count          = var.enable_scaling ? 1 : 0
  dashboard_name = "HW6-Part3"
  dashboard_body = jsonencode({
    start          = "-PT30M"
    periodOverride = "inherit"
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title   = "Service CPU (%)", region = var.aws_region, period = 60, stat = "Average", view = "timeSeries"
          metrics = [["AWS/ECS", "CPUUtilization", "ClusterName", module.ecs.cluster_name, "ServiceName", var.service_name]]
          yAxis   = { left = { min = 0, max = 100 } }
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title   = "CPU per task (%)", region = var.aws_region, period = 60, stat = "Average", view = "timeSeries"
          metrics = [[{ expression = "SEARCH('{ECS/ContainerInsights,ClusterName,ServiceName,TaskId} MetricName=\"TaskCpuUtilization\" ClusterName=\"${module.ecs.cluster_name}\" ServiceName=\"${var.service_name}\"', 'Average', 60)", id = "taskcpu" }]]
          yAxis   = { left = { min = 0, max = 100 } }
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          title = "Desired vs running tasks", region = var.aws_region, period = 60, stat = "Average", view = "timeSeries"
          metrics = [
            ["ECS/ContainerInsights", "DesiredTaskCount", "ClusterName", module.ecs.cluster_name, "ServiceName", var.service_name],
            ["ECS/ContainerInsights", "RunningTaskCount", "ClusterName", module.ecs.cluster_name, "ServiceName", var.service_name]
          ]
          yAxis = { left = { min = 0 } }
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title   = "ALB healthy targets", region = var.aws_region, period = 60, stat = "Minimum", view = "timeSeries"
          metrics = [["AWS/ApplicationELB", "HealthyHostCount", "LoadBalancer", module.network.alb_suffix, "TargetGroup", module.network.target_group_suffix]]
          yAxis   = { left = { min = 0 } }
        }
      },
      {
        type = "metric", x = 0, y = 12, width = 12, height = 6
        properties = {
          title   = "ALB requests per minute", region = var.aws_region, period = 60, stat = "Sum", view = "timeSeries"
          metrics = [["AWS/ApplicationELB", "RequestCount", "LoadBalancer", module.network.alb_suffix]]
        }
      },
      {
        type = "metric", x = 12, y = 12, width = 12, height = 6
        properties = {
          title = "ALB target response time (seconds)", region = var.aws_region, period = 60, stat = "Average", view = "timeSeries"
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", module.network.alb_suffix, { stat = "Average", label = "Average" }],
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", module.network.alb_suffix, { stat = "p95", label = "p95" }]
          ]
        }
      }
    ]
  })
}
