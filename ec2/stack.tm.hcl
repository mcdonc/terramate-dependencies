stack {
  name        = "ec2"
  description = "ec2"
  id          = "f5f1711a-f854-439b-a0f9-d08a2e4d7f71"
  tags = [ "stack.ec2" ]
  after = [ "tag:stack.vpc" ]
}

globals "dependencies" {
  vpc = null
}
