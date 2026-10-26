terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.7.0"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "ecr_repository_name" {
  type    = string
  default = "cs6650-hw5-product"
}

provider "aws" {
  region = var.aws_region
}

module "ecr" {
  source          = "../terraform/modules/ecr"
  repository_name = var.ecr_repository_name
}

output "repository_url" {
  value = module.ecr.repository_url
}
