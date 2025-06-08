generate_hcl "backend.tf" {
  content {
    terraform {
      backend "s3" {
        bucket = "mcdonc-terramate-testing"
        key  = "terraform/states/by-id/${terramate.stack.id}/terraform.tfstate"
        region = "us-east-1"
      }
    }
  }
}
