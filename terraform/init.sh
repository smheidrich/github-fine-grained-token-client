#!/bin/bash
# this needs to be run to initialize/sync your local terraform state for the
# first time and can also be run whenever you've added a new provider (but you
# can also just do terraform init -update in that case)
#
# usage: be sure to set up the needed variables in a .env file or something
# (you can use example-env as a template), then run this script with those
# variables defined, i.e.:
#   ( . .env ; ./init.sh )
#
# if there are complaints about something auth-related after e.g. changing
# the GitLab token TF uses, run this with -reconfigure appended to override
# the local state
terraform init \
  -backend-config=address=${TF_ADDRESS} \
  -backend-config=lock_address=${TF_ADDRESS}/lock \
  -backend-config=unlock_address=${TF_ADDRESS}/lock \
  -backend-config=username=${TF_USERNAME} \
  -backend-config=password=${TF_PASSWORD} \
  -backend-config=lock_method=POST \
  -backend-config=unlock_method=DELETE \
  -backend-config=retry_wait_min=5
