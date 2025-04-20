globals {
  backend                               = "mcdonc-terramate-testing"
  vpc_module_source                     = "terraform-aws-modules/vpc/aws"
  vpc_module_source_version             = "~> 5.17.0"
}

globals "terraform" {
  version = "1.10.4"
}

globals "terraform" "backend" "s3" {
  region = "us-east-1"
}

globals "terraform" "modules" "vpc" {
  version = "2.2.0"
}

globals "terraform" "providers" "aws" {
  version = "5.94.1"
}

globals "terraform" "providers" "null" {
  version = "3.2.3"
}

globals "available_dependencies" {
  vpc  = "daadbae0-240b-4cea-ba23-5b79ba080751"
  website = "f5f1711a-f854-439b-a0f9-d08a2e4d7f71"
  mail = "a447e34d-8b6d-45bb-b489-beaeb349bd5d"
  dynamodb = "7d466f45-7030-4da2-9620-5f67e6d1f3ee"
}
