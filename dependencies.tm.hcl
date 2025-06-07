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
        # the tm_can/tm_length thing is attempting to determine if the
        # stack value is a string, otherwise it's expected to be null/false/true
        # each of which means "use the current workspace"
        workspace = tm_ternary(tm_can(tm_length(let.dependencies[stack.value])), let.dependencies[stack.value], tm_hcl_expression("terraform.workspace"))
        config = {
          bucket  = global.backend
          key = "terraform/states/by-id/${global.available_dependencies[stack.value]}/terraform.tfstate"
          region  = global.terraform.backend.s3.region
          encrypt = true
        }
      }
    }

    tm_dynamic "resource" {
      for_each = let.dependencies
      labels   = ["null_resource", "retrieve-${remote.value}-remote-state"]
      iterator = remote
      content {
        depends_on = [ tm_hcl_expression("data.terraform_remote_state.${remote.value}") ]
      }
    }

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
