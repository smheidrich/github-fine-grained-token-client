variable "gitlab_token" {
  description = "GitLab access token to use to make changes"
  type        = string
}

variable "github_token" {
  description = "GitHub access token to use to make changes"
  type        = string
}

variable "github_mirror_token" {
  description = "GitHub access token to use for the GitLab -> GitHub mirror"
  type        = string
}

variable "project_name" {
  description = "Name of the project (without namespace prefix)"
  type        = string
}

variable "project_description" {
  description = "Description of project for use on GitLab & GitHub"
  type        = string
}

variable "pypi_token" {
  description = "Token to use to publish to PyPI"
  type        = string
}
