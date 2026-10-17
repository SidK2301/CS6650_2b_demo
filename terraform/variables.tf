# Region to deploy into
variable "aws_region" {
  type    = string
  default = "us-west-2"
}

# ECR & ECS settings
variable "ecr_repository_name" {
  type    = string
  default = "cs6650-hw5-product"
}

variable "service_name" {
  type    = string
  default = "cs6650-hw5-product"
}

variable "container_port" {
  type    = number
  default = 8080
}

variable "ecs_count" {
  type    = number
  default = 1
}

# How long to keep logs
variable "log_retention_days" {
  type    = number
  default = 7
}

variable "allowed_cidrs" {
  type        = list(string)
  description = "Public IPv4 CIDRs allowed to reach the API, including each load generator."
  validation {
    condition     = length(var.allowed_cidrs) > 0 && alltrue([for cidr in var.allowed_cidrs : can(cidrnetmask(cidr))])
    error_message = "Supply at least one valid IPv4 CIDR."
  }
}
