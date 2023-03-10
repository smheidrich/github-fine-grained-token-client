#!/bin/bash
# this was used to import the already-created project from GitLab (you can't
# create it via Terraform if you want to use its state storage, obviously).
# if you ever lose the terraform state, you can run this again to try and
# re-import it.
terraform import gitlab_project.project "$PROJECT_ID"
