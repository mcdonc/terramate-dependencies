generate_hcl "provider.tf" {
  content {
    terraform {
      required_version = ">= ${global.terraform.version}"


      required_providers {
        aws = {
          source  = "hashicorp/aws"
          version = global.terraform.providers.aws.version
        }
        null = {
          source  = "hashicorp/null"
          version = global.terraform.providers.null.version
        }
      }
    }

    provider "aws" {
      region = global.terraform.backend.s3.region
    }
  }
}
