stack {
  name        = "mail"
  description = "mail"
  id          = "a447e34d-8b6d-45bb-b489-beaeb349bd5d"
  tags = [ "stack.mail" ]
  after = [ "tag:stack.vpc", "tag:stack.queue" ]
}

globals "dependencies" {
  vpc = null
  queue = null
}
