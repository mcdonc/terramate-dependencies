stack {
  name        = "queue"
  description = "queue"
  id          = "378d2eb2-e14e-4e5e-a912-886fd8469883"
  tags = [ "queue" ]
  after = [ "tag:dynamodb" ]
}

globals "dependencies" {
  dynamodb = null
}
