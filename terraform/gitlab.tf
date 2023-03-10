terraform {
  required_providers {
    gitlab = {
      source = "gitlabhq/gitlab"
      version = "15.9.0"
    }
  }
}

provider "gitlab" {
  token = var.gitlab_token
}

resource "gitlab_project" "project" {
  name = var.project_name
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
