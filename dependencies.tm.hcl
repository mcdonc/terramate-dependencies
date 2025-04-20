generate_hcl "dependencies.tf" {
  condition = tm_length(tm_try(global.dependencies, [])) > 0

  lets {
    dependencies           = tm_try(global.dependencies, {})
    available_dependencies = tm_try(global.available_dependencies, {})
  }

  content {
    tm_dynamic "data" {
      for_each = tm_keys(let.dependencies)
      labels   = ["terraform_remote_state", stack.value ]
      iterator = stack

      content {
        backend = "s3"
        workspace = tm_ternary(let.dependencies[stack.value] != null, let.dependencies[stack.value], tm_hcl_expression("terraform.workspace"))
        config = {
          bucket  = global.backend
          key = "terraform/states/by-id/${global.available_dependencies[stack.value]}/terraform.tfstate"
          #key = tm_ternary(let.dependencies[stack.value] == true || let.dependencies[stack.value] == "default",  "terraform/states/by-id/${global.available_dependencies[stack.value]}/terraform.tfstate", "env:/${terraform.workspace}/terraform/states/by-id/${global.available_dependencies[stack.value]}/terraform.tfstate")
          region  = global.terraform.backend.s3.region
          encrypt = true
        }

        depends_on = [
          null_resource.initial_deployment_trigger
        ]
      }
    }

    resource "null_resource" "initial_deployment_trigger" {}
  }


  # General backend configuration checks
  assert {
    assertion = tm_length(tm_try(global.backend, "")) > 0
    message   = "Terramate Global Variable backend is required, but not set"
  }

  assert {
    assertion = tm_length(tm_try(global.terraform.backend.s3.region, "")) > 0
    message   = "Terramate Global Variable terraform.backend.s3.region is required, but not set"
  }
}
