#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
REGION=${AWS_REGION:-$(terraform -chdir="$ROOT/terraform" output -raw aws_region)}
CLUSTER=$(terraform -chdir="$ROOT/terraform" output -raw ecs_cluster_name)
SERVICE=$(terraform -chdir="$ROOT/terraform" output -raw ecs_service_name)
TASK=$(aws ecs list-tasks --region "$REGION" --cluster "$CLUSTER" --service-name "$SERVICE" --desired-status RUNNING --query 'taskArns[0]' --output text)
[ "$TASK" != None ] || { echo 'No running task found' >&2; exit 1; }
ENI=$(aws ecs describe-tasks --region "$REGION" --cluster "$CLUSTER" --tasks "$TASK" --query 'tasks[0].attachments[].details[?name==`networkInterfaceId`].value[] | [0]' --output text)
[ "$ENI" != None ] || { echo 'Task has no network interface yet' >&2; exit 1; }
IP=$(aws ec2 describe-network-interfaces --region "$REGION" --network-interface-ids "$ENI" --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
[ "$IP" != None ] || { echo 'Task has no public IP yet' >&2; exit 1; }
printf '%s\n' "$IP"
