stack {
  name        = "website"
  description = "website"
  id          = "f5f1711a-f854-439b-a0f9-d08a2e4d7f71"
  tags = [ "stack.website" ]
  after = [ "tag:stack.vpc" ]
}

globals "dependencies" {
  vpc = null
}
