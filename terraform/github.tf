provider "github" {
  token = var.github_token
}

resource "github_repository" "project" {
  name        = var.project_name
  description = "${var.project_description} | mirror of https://gitlab.com/${gitlab_project.project.path_with_namespace}"
  visibility = "public"
  has_issues = true
}

data "github_user" "current" {
  username = ""
}
