provider "gitlab" {
  token = var.gitlab_token
}

resource "gitlab_project" "project" {
  name = var.project_name
  description = var.project_description
  visibility_level = "public"
  merge_method = "rebase_merge"
  squash_option = "default_on"
  only_allow_merge_if_all_discussions_are_resolved = true
  only_allow_merge_if_pipeline_succeeds = true
}

resource "gitlab_tag_protection" "protect_v_tags" {
  project             = gitlab_project.project.id
  tag                 = "v*"
  create_access_level = "maintainer"
}

resource "gitlab_project_mirror" "github_mirror" {
  project = gitlab_project.project.id
  url     = "https://${data.github_user.current.login}:${var.github_mirror_token}@github.com/${data.github_user.current.login}/${var.project_name}.git"
}

resource "gitlab_project_milestone" "v1" {
  project = gitlab_project.project.id
  title   = "v1"
  description = "First public release"
}

resource "gitlab_project_milestone" "v1_1" {
  project = gitlab_project.project.id
  title   = "v1.1"
  description = "Release meant to polish things & introduce new features"
}

resource "gitlab_project_milestone" "v2" {
  project = gitlab_project.project.id
  title   = "v2"
  description = "First release after 1.0 allowed to introduce breaking changes"
}

resource "gitlab_project_variable" "example" {
  project   = gitlab_project.project.id
  key       = "PYPI_TOKEN"
  value     = var.pypi_token
  protected = true
  masked    = true
}
