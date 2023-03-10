variable "gitlab_token" {
  description = "GitLab access token to use to make changes"
  type        = string
}

variable "project_name" {
  description = "Name of the project (without namespace prefix)"
  type        = string
}
