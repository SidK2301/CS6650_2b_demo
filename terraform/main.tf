locals {
  src_hash  = sha1(join("", [for f in sort(fileset("${path.module}/../src", "**")) : filesha1("${path.module}/../src/${f}")]))
  image_tag = "${module.ecr.repository_url}:${local.src_hash}"
}

# Wire together four focused modules: network, ecr, logging, ecs.

module "network" {
  source         = "./modules/network"
  service_name   = var.service_name
  container_port = var.container_port
  cidr_blocks    = var.allowed_cidrs
}

module "ecr" {
  source          = "./modules/ecr"
  repository_name = var.ecr_repository_name
}

module "logging" {
  source            = "./modules/logging"
  service_name      = var.service_name
  retention_in_days = var.log_retention_days
}

# Reuse an existing IAM role for ECS tasks
data "aws_iam_role" "lab_role" {
  name = "LabRole"
}

module "ecs" {
  source             = "./modules/ecs"
  service_name       = var.service_name
  image              = local.image_tag
  container_port     = var.container_port
  subnet_ids         = module.network.subnet_ids
  security_group_ids = [module.network.security_group_id]
  execution_role_arn = data.aws_iam_role.lab_role.arn
  task_role_arn      = data.aws_iam_role.lab_role.arn
  log_group_name     = module.logging.log_group_name
  ecs_count          = var.ecs_count
  region             = var.aws_region
  depends_on         = [docker_registry_image.app]
}


// Build & push the Go app image into ECR
resource "docker_image" "app" {
  # Tag the image with a hash of all source/build inputs.
  name = local.image_tag

  build {
    # relative path from terraform/ → src/
    context  = "../src"
    platform = "linux/amd64"
    # Dockerfile defaults to "Dockerfile" in that context
  }
}

resource "docker_registry_image" "app" {
  # Push the same content-tagged image referenced by the task definition.
  name = docker_image.app.name
}
