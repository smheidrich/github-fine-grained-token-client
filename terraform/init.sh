#!/bin/bash
# this needs to be run to initialize your local terraform state for the first
#   time and also whenever you added a new provider (this installs the dep)
#
# usage: define the variables referenced below as follows in an extra file
# called .env or something like that:
#   export PROJECT_ID="44151191"
#   export TF_USERNAME="<your username>"
#   export TF_PASSWORD="<your token>"
#   export TF_ADDRESS="https://gitlab.com/api/v4/projects/${PROJECT_ID}/terraform/state/state"
#   # for main config => GitLab provider
#   export TF_VAR_gitlab_token="$TF_PASSWORD"
#   export TF_VAR_project_name="github-fine-grained-token-client"
# then run this script with those variables defined, i.e.
#   ( . .env ; ./init.sh )
terraform init \
  -backend-config=address=${TF_ADDRESS} \
  -backend-config=lock_address=${TF_ADDRESS}/lock \
  -backend-config=unlock_address=${TF_ADDRESS}/lock \
  -backend-config=username=${TF_USERNAME} \
  -backend-config=password=${TF_PASSWORD} \
  -backend-config=lock_method=POST \
  -backend-config=unlock_method=DELETE \
  -backend-config=retry_wait_min=5
