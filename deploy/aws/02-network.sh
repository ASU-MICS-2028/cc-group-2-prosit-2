#!/usr/bin/env bash
# Step 2: VPC, subnets, route tables, S3 gateway endpoint, NAT instance.
# See docs/AWS_DEPLOYMENT.md, Step 2. Saves every ID to ~/hc-aws.env.
set -euo pipefail

# Run with your own CLI profile, e.g.  AWS_PROFILE=my-profile bash deploy/aws/02-network.sh
# The IDs file stays in your home folder, never in this (public) repo.
ENV_FILE=~/hc-aws.env
[ -f "$ENV_FILE" ] || echo "export AWS_PROFILE=${AWS_PROFILE:-default}" > "$ENV_FILE"
grep -q '^save()' "$ENV_FILE" || cat >> "$ENV_FILE" <<'EOF'
export AWS_REGION=eu-north-1
export AWS_DEFAULT_REGION=eu-north-1
save() { echo "export $1=$2" >> ~/hc-aws.env; export "$1=$2"; }
EOF
source "$ENV_FILE"
[ -n "${ACCOUNT_ID:-}" ] || save ACCOUNT_ID "$(aws sts get-caller-identity --query Account --output text)"
[ -n "${REPO_URL:-}" ] || save REPO_URL https://github.com/ASU-MICS-2028/cc-group-2-prosit-2.git

if [ -n "${VPC_ID:-}" ]; then echo "VPC already created ($VPC_ID); stopping so nothing is duplicated."; exit 1; fi

echo "== 2.1 VPC and internet gateway"
save VPC_ID "$(aws ec2 create-vpc --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=healthconnect-vpc},{Key=Project,Value=healthconnect}]' \
  --query Vpc.VpcId --output text)"
aws ec2 wait vpc-available --vpc-ids "$VPC_ID"
aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-support '{"Value":true}'
aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-hostnames '{"Value":true}'
echo "VPC_ID=$VPC_ID"

save IGW_ID "$(aws ec2 create-internet-gateway \
  --tag-specifications 'ResourceType=internet-gateway,Tags=[{Key=Name,Value=healthconnect-igw},{Key=Project,Value=healthconnect}]' \
  --query InternetGateway.InternetGatewayId --output text)"
aws ec2 attach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID"
echo "IGW_ID=$IGW_ID (attached)"

echo "== 2.2 Six subnets"
mk_subnet() { aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block "$1" --availability-zone "$2" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$3},{Key=Project,Value=healthconnect}]" \
  --query Subnet.SubnetId --output text; }
save PUB_A "$(mk_subnet 10.0.1.0/24  eu-north-1a hc-public-a)"
save PUB_B "$(mk_subnet 10.0.2.0/24  eu-north-1b hc-public-b)"
save APP_A "$(mk_subnet 10.0.11.0/24 eu-north-1a hc-app-a)"
save APP_B "$(mk_subnet 10.0.12.0/24 eu-north-1b hc-app-b)"
save DB_A  "$(mk_subnet 10.0.21.0/24 eu-north-1a hc-db-a)"
save DB_B  "$(mk_subnet 10.0.22.0/24 eu-north-1b hc-db-b)"
aws ec2 modify-subnet-attribute --subnet-id "$PUB_A" --map-public-ip-on-launch
aws ec2 modify-subnet-attribute --subnet-id "$PUB_B" --map-public-ip-on-launch
echo "public: $PUB_A $PUB_B | app: $APP_A $APP_B | db: $DB_A $DB_B"

echo "== 2.3 Route tables"
mk_rt() { aws ec2 create-route-table --vpc-id "$VPC_ID" \
  --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=$1},{Key=Project,Value=healthconnect}]" \
  --query RouteTable.RouteTableId --output text; }
save RT_PUBLIC "$(mk_rt hc-rt-public)"
save RT_APP    "$(mk_rt hc-rt-app)"
save RT_DB     "$(mk_rt hc-rt-db)"
aws ec2 create-route --route-table-id "$RT_PUBLIC" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW_ID" >/dev/null
for s in "$PUB_A" "$PUB_B"; do aws ec2 associate-route-table --route-table-id "$RT_PUBLIC" --subnet-id "$s" >/dev/null; done
for s in "$APP_A" "$APP_B"; do aws ec2 associate-route-table --route-table-id "$RT_APP" --subnet-id "$s" >/dev/null; done
for s in "$DB_A" "$DB_B";   do aws ec2 associate-route-table --route-table-id "$RT_DB" --subnet-id "$s" >/dev/null; done
echo "public: $RT_PUBLIC (0.0.0.0/0 -> IGW) | app: $RT_APP | db: $RT_DB (local only)"

echo "== 2.4 S3 gateway endpoint (free)"
save S3_ENDPOINT "$(aws ec2 create-vpc-endpoint --vpc-id "$VPC_ID" --vpc-endpoint-type Gateway \
  --service-name "com.amazonaws.$AWS_REGION.s3" --route-table-ids "$RT_APP" \
  --tag-specifications 'ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=hc-s3-endpoint},{Key=Project,Value=healthconnect}]' \
  --query VpcEndpoint.VpcEndpointId --output text)"
echo "S3_ENDPOINT=$S3_ENDPOINT"

echo "== 2.5 NAT instance"
save NAT_SG "$(aws ec2 create-security-group --group-name hc-nat-sg --description 'NAT instance: from app subnets only' \
  --vpc-id "$VPC_ID" --tag-specifications 'ResourceType=security-group,Tags=[{Key=Name,Value=hc-nat-sg},{Key=Project,Value=healthconnect}]' \
  --query GroupId --output text)"
aws ec2 authorize-security-group-ingress --group-id "$NAT_SG" --protocol -1 --cidr 10.0.11.0/24 >/dev/null
aws ec2 authorize-security-group-ingress --group-id "$NAT_SG" --protocol -1 --cidr 10.0.12.0/24 >/dev/null

USERDATA_FILE=$(mktemp)
cat > "$USERDATA_FILE" <<'EOF'
#!/bin/bash
dnf install -y iptables-services
echo 'net.ipv4.ip_forward = 1' > /etc/sysctl.d/90-nat.conf
sysctl -p /etc/sysctl.d/90-nat.conf
IFACE=$(ip route show default | awk '{print $5; exit}')
iptables -t nat -A POSTROUTING -o "$IFACE" -s 10.0.0.0/16 -j MASQUERADE
iptables -P FORWARD ACCEPT
iptables -F FORWARD
service iptables save
systemctl enable --now iptables
EOF
save NAT_ID "$(aws ec2 run-instances \
  --image-id resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 \
  --instance-type t4g.nano --subnet-id "$PUB_A" --security-group-ids "$NAT_SG" \
  --metadata-options HttpTokens=required \
  --user-data "file://$USERDATA_FILE" \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=healthconnect-nat},{Key=Project,Value=healthconnect}]' \
  --query 'Instances[0].InstanceId' --output text)"
rm -f "$USERDATA_FILE"
echo "NAT_ID=$NAT_ID, waiting for it to run..."
aws ec2 wait instance-running --instance-ids "$NAT_ID"
aws ec2 modify-instance-attribute --instance-id "$NAT_ID" --no-source-dest-check
aws ec2 create-route --route-table-id "$RT_APP" --destination-cidr-block 0.0.0.0/0 --instance-id "$NAT_ID" >/dev/null
echo "app route table: 0.0.0.0/0 -> $NAT_ID"

echo "== Result"
aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'sort_by(Subnets,&CidrBlock)[].[Tags[?Key==`Name`]|[0].Value,SubnetId,CidrBlock,AvailabilityZone,MapPublicIpOnLaunch]' --output table
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'RouteTables[].[Tags[?Key==`Name`]|[0].Value,join(`, `,Routes[].join(` -> `,[DestinationCidrBlock||DestinationPrefixListId||``,GatewayId||InstanceId||``]))]' --output table
echo "Step 2 done."
