terraform {
  required_providers {
    gitlab = {
      source = "gitlabhq/gitlab"
      version = "15.9.0"
    }
    github = {
      source = "integrations/github"
      version = "5.18.0"
    }
  }
}
