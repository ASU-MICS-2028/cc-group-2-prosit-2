#!/usr/bin/env bash
# Step 3: security group chain CloudFront -> load balancer -> API -> database, plus egress allow-lists.
# See docs/AWS_DEPLOYMENT.md, Step 3.
set -euo pipefail
source ~/hc-aws.env
if [ -n "${ALB_SG:-}" ]; then echo "Security groups already created; stopping."; exit 1; fi

mk_sg() { aws ec2 create-security-group --group-name "$1" --description "$2" --vpc-id "$VPC_ID" \
  --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=$1},{Key=Project,Value=healthconnect}]" \
  --query GroupId --output text; }

echo "== Create groups"
save ALB_SG    "$(mk_sg hc-alb-sg 'Load balancer: from CloudFront only')"
save APP_SG    "$(mk_sg hc-app-sg 'API servers: from load balancer only')"
save LAMBDA_SG "$(mk_sg hc-lambda-sg 'Reminder Lambda: no inbound')"
save DB_SG     "$(mk_sg hc-db-sg 'Database: from API and Lambda only')"
echo "alb=$ALB_SG app=$APP_SG lambda=$LAMBDA_SG db=$DB_SG"

echo "== Inbound rules"
save CF_PL "$(aws ec2 describe-managed-prefix-lists \
  --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
  --query 'PrefixLists[0].PrefixListId' --output text)"
aws ec2 authorize-security-group-ingress --group-id "$ALB_SG" \
  --ip-permissions "IpProtocol=tcp,FromPort=80,ToPort=80,PrefixListIds=[{PrefixListId=$CF_PL,Description=CloudFront}]" >/dev/null
aws ec2 authorize-security-group-ingress --group-id "$APP_SG" \
  --ip-permissions "IpProtocol=tcp,FromPort=8000,ToPort=8000,UserIdGroupPairs=[{GroupId=$ALB_SG,Description=load-balancer}]" >/dev/null
aws ec2 authorize-security-group-ingress --group-id "$DB_SG" \
  --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$APP_SG,Description=api},{GroupId=$LAMBDA_SG,Description=reminder-lambda}]" >/dev/null

echo "== Egress allow-lists (W5 egress filtering)"
ALL_OUT='[{"IpProtocol":"-1","IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'
for SG in "$APP_SG" "$LAMBDA_SG"; do
  aws ec2 revoke-security-group-egress --group-id "$SG" --ip-permissions "$ALL_OUT" >/dev/null
  aws ec2 authorize-security-group-egress --group-id "$SG" \
    --ip-permissions '[{"IpProtocol":"tcp","FromPort":443,"ToPort":443,"IpRanges":[{"CidrIp":"0.0.0.0/0","Description":"HTTPS out: Arkesel, AWS APIs, updates"}]}]' >/dev/null
  aws ec2 authorize-security-group-egress --group-id "$SG" \
    --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$DB_SG,Description=database}]" >/dev/null
done
# Load balancer may only talk to the API; database needs no outbound
aws ec2 revoke-security-group-egress --group-id "$ALB_SG" --ip-permissions "$ALL_OUT" >/dev/null
aws ec2 authorize-security-group-egress --group-id "$ALB_SG" \
  --ip-permissions "IpProtocol=tcp,FromPort=8000,ToPort=8000,UserIdGroupPairs=[{GroupId=$APP_SG,Description=api}]" >/dev/null
aws ec2 revoke-security-group-egress --group-id "$DB_SG" --ip-permissions "$ALL_OUT" >/dev/null

echo "== Result"
aws ec2 describe-security-group-rules --filters "Name=group-id,Values=$ALB_SG,$APP_SG,$LAMBDA_SG,$DB_SG" \
  --query 'SecurityGroupRules[].[GroupId,IsEgress,IpProtocol,FromPort,ToPort,CidrIpv4||PrefixListId||ReferencedGroupInfo.GroupId]' --output table
echo "Step 3 done."
