stack {
  name        = "ec2-jack"
  description = "ec2-jack"
  id          = "f5f1711a-f854-439b-a0f9-d08a2e4d7f71"
  tags = [ "stack.ec2-jack" ]
  after = [ "tag:stack.vpc" ]
}

globals "dependencies" {
  vpc = null
}
