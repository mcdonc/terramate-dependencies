stack {
  name        = "mail"
  description = "mail"
  id          = "a447e34d-8b6d-45bb-b489-beaeb349bd5d"
  tags = [ "mail" ]
  after = [ "tag:vpc", "tag:queue" ]
}

globals "dependencies" {
  vpc = null
  queue = null
}
