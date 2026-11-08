# Deploying HealthConnect Ghana on AWS (step by step)

This is the exact runbook: what to create, in what order, with the commands to run.
Each step says **why** in one line and which lecture it comes from (W5 = networking, W6 = security, W7 = serverless).

Region: **eu-north-1 (Stockholm)**. All commands are for a Mac/Linux terminal with the AWS CLI v2.

```
Phone ──HTTPS──► CloudFront ──/*──────► S3 (web app, private)
                      │
                      └──/api/*──► Load balancer (private) ──► EC2: FastAPI ──► RDS PostgreSQL
                                                                 │                  ▲
                                   EventBridge (10 min) ──► Lambda: reminders ──────┘
                                                                 │ fails 3× → SQS dead-letter queue
                                   EC2 + Lambda ──► NAT instance ──► Arkesel SMS
                                   Phones ◄──► coturn TURN relay (video when direct fails)
```

**Time:** about one day for Step 1 (code), then about half a day for Steps 2 to 9.
**Cost:** roughly $60–70/month if left running. See [Step 13](#step-13-control-the-cost) to stop things between demos.

---

## Contents

0. [Get ready](#step-0-get-ready)
1. [Change the code (on your laptop)](#step-1-change-the-code-on-your-laptop)
2. [Build the network](#step-2-build-the-network)
3. [Security groups](#step-3-security-groups)
4. [Database and secrets](#step-4-database-and-secrets)
5. [Permissions for the server (IAM)](#step-5-permissions-for-the-server-iam)
6. [API server, load balancer and auto scaling](#step-6-api-server-load-balancer-and-auto-scaling)
7. [First admin account (or demo data)](#step-7-first-admin-account-or-demo-data)
8. [Web app and CloudFront](#step-8-web-app-and-cloudfront)
9. [SMS reminders as a Lambda function](#step-9-sms-reminders-as-a-lambda-function)
10. [Alarms and logs](#step-10-alarms-and-logs)
11. [Automatic deployment from GitHub](#step-11-automatic-deployment-from-github)
12. [TURN relay for video calls](#step-12-turn-relay-for-video-calls)
13. [Control the cost](#step-13-control-the-cost)
14. [Final checklist](#step-14-final-checklist)

---

## Step 0: Get ready

**Why:** every later command needs a working AWS login and a place to remember the IDs AWS gives back.

1. **Fix the AWS CLI login.** Use an IAM user with MFA, not the root account (W6: MFA for admin access).

   ```bash
   aws configure
   ```

   Enter your access key ID, secret key, region `eu-north-1`, output `json`. Then check it works:

   ```bash
   aws sts get-caller-identity
   ```

2. **Install the Session Manager plugin** so you can open a shell on servers without SSH:

   ```bash
   brew install --cask session-manager-plugin
   ```

3. **Create a file that remembers every ID.** Each step adds to it with `save NAME value`. If you open a new terminal, run `source ~/hc-aws.env` first.

   ```bash
   cat > ~/hc-aws.env <<'EOF'
   export AWS_REGION=eu-north-1
   export AWS_DEFAULT_REGION=eu-north-1
   save() { echo "export $1=$2" >> ~/hc-aws.env; export "$1=$2"; }
   EOF
   source ~/hc-aws.env
   save ACCOUNT_ID "$(aws sts get-caller-identity --query Account --output text)"
   save REPO_URL https://github.com/ASU-MICS-2028/cc-group-2-prosit-2.git
   ```

4. **Run every command from the repository root** (`cc-group-2-prosit-2/`). Steps 8, 9 and 11 use paths like `frontend/` and `backend/`.

5. **Agree with the team** (Alice owns Phase 3 in the README) who runs which step.

---

## Step 1: Change the code (on your laptop)

**Status: done** on branch `clifford/aws-postgres`. 36 backend tests pass on SQLite **and** on PostgreSQL 16; GitHub Actions runs both.
What was built, in short:
- `backend/config.py`: settings from `.env` locally, from Secrets Manager in the cloud (`APP_SECRET_ID`, `DB_SECRET_ID`, `DB_HOST`, `DB_NAME`, `DB_SSLROOTCERT`). Re-reads the DB secret if AWS rotated the password.
- `backend/database.py`: SQLite when `DATABASE_URL` is unset (laptops, unchanged), PostgreSQL when it's set. One set of SQL for both.
- `GET /health`, `Cache-Control: no-store` on every response, `REMINDERS_IN_PROCESS=off` for the cloud.
- `backend/reminders.py`: claim-before-send (idempotent), 3 attempts, stale claims released after 15 minutes. `backend/lambda_handler.py` for Step 9.
- CI: backend tests on both databases, `pip-audit` and `npm audit --audit-level=high` (high-severity frontend issues fixed with `npm audit fix`).
- Not done yet: 1.11 (TURN credentials endpoint), needed only for Step 12.

The table below is the original plan, kept for the report.

**Why:** the app was written for SQLite on one laptop. The cloud needs a shared database, secrets from Secrets Manager, and reminders that can't double-send.
Nothing here touches AWS. Merge to `main` when all tests pass, because the servers install from `main`.

| # | Change | File(s) | Lecture |
|---|---|---|---|
| 1.1 | Switch from `sqlite3` to `psycopg` (PostgreSQL). Rows as dicts (`dict_row`). `?` → `%s`. | `database.py` and every query | W6 managed DB |
| 1.2 | Rewrite SQLite-only SQL: `datetime('now')` → `now()`, `datetime('now', ?)` → `now() + %s::interval`, `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY`, `cur.lastrowid` → `INSERT … RETURNING id`, `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`, `PRAGMA table_info` → `information_schema.columns` | `database.py`, `main.py`, `surveillance.py`, `seed*.py` | |
| 1.3 | New `config.py`: if `APP_SECRET_ID` is set, read `JWT_SECRET`, `ARKESEL_*`, `FRONTEND_ORIGINS`, `TURN_SECRET` from Secrets Manager (boto3). Read the DB password from `DB_SECRET_ID`. Connect with `sslmode=require`. Fall back to `.env` locally. | `config.py`, `auth.py`, `sms.py`, `main.py` | W6 secrets management |
| 1.4 | Add `GET /health`: returns 200 when the database answers `SELECT 1`. | `main.py` | W5 health checks |
| 1.5 | Add `Cache-Control: no-store` to every API response (patient data must never be cached by CloudFront or the browser). | `main.py` middleware | W6 confidentiality |
| 1.6 | **Idempotent reminders:** claim each appointment with `UPDATE … SET reminder_status='sending' WHERE id=%s AND reminder_status IS NULL RETURNING id` *before* sending. On failure, put it back to `NULL` and add 1 to `reminder_attempts`; after 3 tries mark it `failed`. | `reminders.py`, `database.py` | W7 idempotency |
| 1.7 | New `lambda_handler.py` with `handler(event, context)` that calls `send_due_reminders()` and raises if anything failed (so Lambda retries). | new file | W7 serverless |
| 1.8 | Only run the in-process loop when `REMINDERS_IN_PROCESS=on` (local dev) or `DEMO_MODE=on` (demo refresh). In the cloud, Lambda sends reminders. | `main.py` | W7, W5 stateless |
| 1.9 | `requirements.txt`: add `psycopg[binary]` and `boto3`. | `requirements.txt` | |
| 1.10 | Tests run against PostgreSQL: a `postgres:16` container locally and a `services: postgres` block in `.github/workflows/tests.yml`. Add `pip-audit` and `npm audit --audit-level=high`. | tests, CI | W6 vulnerability scanning |
| 1.11 | (For Step 12) `GET /calls/ice-servers` returns STUN + TURN with short-lived credentials (HMAC-SHA1 of `expiry:user_id` with `TURN_SECRET`). `VideoCall.jsx` uses them. | `calls.py`, `VideoCall.jsx` | W7 TURN |

Run a local PostgreSQL for testing:

```bash
docker run -d --name hc-pg -e POSTGRES_PASSWORD=localdev -e POSTGRES_DB=healthconnect -p 5432:5432 postgres:16
```

**Done when:** `pytest` and `npm test` pass against PostgreSQL, the app works locally, and it's merged to `main`.

---

## Step 2: Build the network

**Why:** the database must sit somewhere the internet has no route to (W5 reference layout: public subnet → private app subnet → private DB subnet).

### 2.1 VPC and internet gateway

```bash
source ~/hc-aws.env
save VPC_ID "$(aws ec2 create-vpc --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=healthconnect-vpc}]' \
  --query Vpc.VpcId --output text)"
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support '{"Value":true}'
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames '{"Value":true}'

save IGW_ID "$(aws ec2 create-internet-gateway --query InternetGateway.InternetGatewayId --output text)"
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID
```

### 2.2 Six subnets (three tiers × two Availability Zones)

The load balancer and the RDS subnet group both require two AZs. W5 rule: `/16` for the VPC, `/24` per subnet.

```bash
mk_subnet() { aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block $1 --availability-zone $2 \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=$3}]" --query Subnet.SubnetId --output text; }

save PUB_A "$(mk_subnet 10.0.1.0/24  eu-north-1a hc-public-a)"
save PUB_B "$(mk_subnet 10.0.2.0/24  eu-north-1b hc-public-b)"
save APP_A "$(mk_subnet 10.0.11.0/24 eu-north-1a hc-app-a)"
save APP_B "$(mk_subnet 10.0.12.0/24 eu-north-1b hc-app-b)"
save DB_A  "$(mk_subnet 10.0.21.0/24 eu-north-1a hc-db-a)"
save DB_B  "$(mk_subnet 10.0.22.0/24 eu-north-1b hc-db-b)"

# Only public subnets give new machines a public IP
aws ec2 modify-subnet-attribute --subnet-id $PUB_A --map-public-ip-on-launch
aws ec2 modify-subnet-attribute --subnet-id $PUB_B --map-public-ip-on-launch
```

### 2.3 Route tables

```bash
mk_rt() { aws ec2 create-route-table --vpc-id $VPC_ID \
  --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=$1}]" --query RouteTable.RouteTableId --output text; }

save RT_PUBLIC "$(mk_rt hc-rt-public)"
save RT_APP    "$(mk_rt hc-rt-app)"
save RT_DB     "$(mk_rt hc-rt-db)"

# Public: internet both ways
aws ec2 create-route --route-table-id $RT_PUBLIC --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID
for s in $PUB_A $PUB_B; do aws ec2 associate-route-table --route-table-id $RT_PUBLIC --subnet-id $s; done

# App: outbound through the NAT instance (route added in 2.5)
for s in $APP_A $APP_B; do aws ec2 associate-route-table --route-table-id $RT_APP --subnet-id $s; done

# DB: no route out at all, only inside the VPC
for s in $DB_A $DB_B; do aws ec2 associate-route-table --route-table-id $RT_DB --subnet-id $s; done
```

### 2.4 Free S3 gateway endpoint

S3 traffic from the app subnets then skips the NAT (W5: VPC endpoints).

```bash
aws ec2 create-vpc-endpoint --vpc-id $VPC_ID --vpc-endpoint-type Gateway \
  --service-name com.amazonaws.$AWS_REGION.s3 --route-table-ids $RT_APP
```

### 2.5 NAT instance

**Why:** private servers must reach Arkesel and download updates, but nothing outside may connect in. A NAT instance costs about $3/month; a managed NAT Gateway costs about $35/month plus data.
W5 calls a single NAT instance "a defensible choice" for an MVP. **Write the trade-off in the report:** if it dies, SMS and updates stop until it's replaced. The app itself keeps working.

First create its security group (only the app subnets may use it):

```bash
save NAT_SG "$(aws ec2 create-security-group --group-name hc-nat-sg --description 'NAT instance' \
  --vpc-id $VPC_ID --query GroupId --output text)"
aws ec2 authorize-security-group-ingress --group-id $NAT_SG --protocol -1 --cidr 10.0.11.0/24
aws ec2 authorize-security-group-ingress --group-id $NAT_SG --protocol -1 --cidr 10.0.12.0/24
```

Its start-up script:

```bash
cat > /tmp/nat-userdata.sh <<'EOF'
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
```

Launch it, then turn off the source/destination check (required for any NAT) and point the app route table at it:

```bash
save NAT_ID "$(aws ec2 run-instances \
  --image-id resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 \
  --instance-type t4g.nano --subnet-id $PUB_A --security-group-ids $NAT_SG \
  --metadata-options HttpTokens=required \
  --user-data file:///tmp/nat-userdata.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=healthconnect-nat}]' \
  --query 'Instances[0].InstanceId' --output text)"
aws ec2 wait instance-running --instance-ids $NAT_ID
aws ec2 modify-instance-attribute --instance-id $NAT_ID --no-source-dest-check
aws ec2 create-route --route-table-id $RT_APP --destination-cidr-block 0.0.0.0/0 --instance-id $NAT_ID
```

**Check:** in the VPC console, `hc-rt-app` shows `0.0.0.0/0 → i-…` (the NAT), and `hc-rt-db` has only the `local` route.

---

## Step 3: Security groups

**Why:** each layer only accepts traffic from the layer in front of it: CloudFront → load balancer → API → database (W5 security groups, W6 "two layers of defense").
W5 egress filtering: we also remove "allow all outbound" and allow only what's needed.

```bash
mk_sg() { aws ec2 create-security-group --group-name $1 --description "$2" --vpc-id $VPC_ID --query GroupId --output text; }
save ALB_SG    "$(mk_sg hc-alb-sg 'Load balancer: from CloudFront only')"
save APP_SG    "$(mk_sg hc-app-sg 'API servers: from load balancer only')"
save LAMBDA_SG "$(mk_sg hc-lambda-sg 'Reminder Lambda')"
save DB_SG     "$(mk_sg hc-db-sg 'Database: from API and Lambda only')"

# CloudFront's own address list
save CF_PL "$(aws ec2 describe-managed-prefix-lists \
  --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
  --query 'PrefixLists[0].PrefixListId' --output text)"

# Load balancer: in from CloudFront on 80
aws ec2 authorize-security-group-ingress --group-id $ALB_SG \
  --ip-permissions "IpProtocol=tcp,FromPort=80,ToPort=80,PrefixListIds=[{PrefixListId=$CF_PL}]"

# API: in from the load balancer on 8000
aws ec2 authorize-security-group-ingress --group-id $APP_SG --protocol tcp --port 8000 --source-group $ALB_SG

# Database: in from API and Lambda on 5432
aws ec2 authorize-security-group-ingress --group-id $DB_SG --protocol tcp --port 5432 --source-group $APP_SG
aws ec2 authorize-security-group-ingress --group-id $DB_SG --protocol tcp --port 5432 --source-group $LAMBDA_SG

# Egress allow-list for API and Lambda: HTTPS out (Arkesel, AWS APIs, updates) and Postgres to the DB only
for SG in $APP_SG $LAMBDA_SG; do
  aws ec2 revoke-security-group-egress --group-id $SG \
    --ip-permissions '[{"IpProtocol":"-1","IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]'
  aws ec2 authorize-security-group-egress --group-id $SG \
    --ip-permissions 'IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0}]'
  aws ec2 authorize-security-group-egress --group-id $SG \
    --ip-permissions "IpProtocol=tcp,FromPort=5432,ToPort=5432,UserIdGroupPairs=[{GroupId=$DB_SG}]"
done
```

> The CloudFront prefix list counts as about 55 rules toward the security group's limit of 60. That's why `hc-alb-sg` has only this one inbound rule.

---

## Step 4: Database and secrets

### 4.1 RDS PostgreSQL

**Why:** a managed, encrypted database every server can share (W6: encryption at rest with KMS, TLS in transit).
We create a **new** instance inside the new VPC. Lab 6's `healthconnect-db` lives in the default VPC; stop it after this step to save money (`aws rds stop-db-instance --db-instance-identifier healthconnect-db`).

```bash
# Use AWS's current default PostgreSQL version and its parameter family
read PG_VER PG_FAMILY < <(aws rds describe-db-engine-versions --engine postgres --default-only \
  --query 'DBEngineVersions[0].[EngineVersion,DBParameterGroupFamily]' --output text)
save PG_VER $PG_VER; save PG_FAMILY $PG_FAMILY

aws rds create-db-subnet-group --db-subnet-group-name healthconnect-db-subnets \
  --db-subnet-group-description "HealthConnect private DB subnets" --subnet-ids $DB_A $DB_B

# Force TLS on every connection (same as Lab 6)
aws rds create-db-parameter-group --db-parameter-group-name healthconnect-pg \
  --db-parameter-group-family $PG_FAMILY --description "HealthConnect: force TLS"
aws rds modify-db-parameter-group --db-parameter-group-name healthconnect-pg \
  --parameters "ParameterName=rds.force_ssl,ParameterValue=1,ApplyMethod=immediate"

aws rds create-db-instance \
  --db-instance-identifier healthconnect-prod \
  --engine postgres --engine-version $PG_VER \
  --db-instance-class db.t4g.micro \
  --allocated-storage 20 --storage-type gp3 --storage-encrypted \
  --db-name healthconnect --master-username hcadmin --manage-master-user-password \
  --db-subnet-group-name healthconnect-db-subnets --vpc-security-group-ids $DB_SG \
  --db-parameter-group-name healthconnect-pg \
  --no-publicly-accessible --no-multi-az \
  --backup-retention-period 7 --deletion-protection --copy-tags-to-snapshot

aws rds wait db-instance-available --db-instance-identifier healthconnect-prod   # about 10 minutes

save DB_HOST "$(aws rds describe-db-instances --db-instance-identifier healthconnect-prod \
  --query 'DBInstances[0].Endpoint.Address' --output text)"
save DB_SECRET_ARN "$(aws rds describe-db-instances --db-instance-identifier healthconnect-prod \
  --query 'DBInstances[0].MasterUserSecret.SecretArn' --output text)"
```

`--manage-master-user-password` means RDS creates the password, keeps it in Secrets Manager and rotates it. Nobody ever types it.

**Check:** RDS console → `healthconnect-prod`: *Encryption: Enabled*, *Publicly accessible: No*.

### 4.2 App secret

**Why:** `JWT_SECRET` and the Arkesel key must not live in code or `.env` on a server (W6 secrets management). The commands below never print them.

```bash
JWT=$(python3 -c "import secrets; print(secrets.token_hex(32))")
TURN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
read -rsp "Arkesel API key (press Enter to skip SMS for now): " ARK; echo
SECRET_JSON=$(python3 -c 'import json,sys; print(json.dumps({"JWT_SECRET":sys.argv[1],"TURN_SECRET":sys.argv[2],"ARKESEL_API_KEY":sys.argv[3],"ARKESEL_SENDER":"HealthConn","FRONTEND_ORIGINS":""}))' "$JWT" "$TURN" "$ARK")
save APP_SECRET_ARN "$(aws secretsmanager create-secret --name healthconnect/app \
  --secret-string "$SECRET_JSON" --query ARN --output text)"
unset JWT TURN ARK SECRET_JSON
```

`ARKESEL_SENDER` must be a sender ID you've registered with Arkesel (11 characters max). Change it in the console if yours differs.

---

## Step 5: Permissions for the server (IAM)

**Why:** the server gets temporary credentials from a role, never stored keys, and only the permissions it needs (W6 least privilege, your Lab 6 policy).

```bash
cat > /tmp/ec2-trust.json <<'EOF'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}
EOF

cat > /tmp/api-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "ReadOwnSecrets", "Effect": "Allow",
     "Action": ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
     "Resource": ["$APP_SECRET_ARN", "$DB_SECRET_ARN"]},
    {"Sid": "DenyDestructiveDbActions", "Effect": "Deny",
     "Action": ["rds:DeleteDBInstance", "rds:DeleteDBCluster", "rds:ModifyDBInstance"],
     "Resource": "*"}
  ]
}
EOF

aws iam create-role --role-name healthconnect-api-role --assume-role-policy-document file:///tmp/ec2-trust.json
aws iam put-role-policy --role-name healthconnect-api-role --policy-name healthconnect-api --policy-document file:///tmp/api-policy.json
# Shell access without SSH (Session Manager) and log shipping to CloudWatch
aws iam attach-role-policy --role-name healthconnect-api-role --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam attach-role-policy --role-name healthconnect-api-role --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy

aws iam create-instance-profile --instance-profile-name healthconnect-api-profile
aws iam add-role-to-instance-profile --instance-profile-name healthconnect-api-profile --role-name healthconnect-api-role
```

---

## Step 6: API server, load balancer and auto scaling

### 6.1 Start-up script for each API server

**Why:** an Auto Scaling group can replace a broken server at any time, so the server must set itself up from scratch with no human (W5 auto scaling).
It runs **one** uvicorn worker: video-call rooms live in memory until they move into the database (W5: stateless services).

```bash
cat > /tmp/api-userdata.sh <<'EOF'
#!/bin/bash
set -euo pipefail
dnf install -y git python3.11 python3.11-pip amazon-cloudwatch-agent
useradd --system --home-dir /opt/healthconnect --shell /sbin/nologin hc || true
mkdir -p /opt/healthconnect /var/log/healthconnect
git clone --depth 1 --branch main __REPO_URL__ /opt/healthconnect/app
python3.11 -m venv /opt/healthconnect/venv
/opt/healthconnect/venv/bin/pip install --quiet -r /opt/healthconnect/app/backend/requirements.txt
# RDS certificate bundle: lets the app check it is talking to the real database (sslmode=verify-full)
curl -fsSL -o /opt/healthconnect/rds-ca.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
chown -R hc:hc /opt/healthconnect /var/log/healthconnect

cat > /etc/systemd/system/healthconnect.service <<'UNIT'
[Unit]
Description=HealthConnect API
After=network-online.target
Wants=network-online.target
[Service]
User=hc
WorkingDirectory=/opt/healthconnect/app/backend
Environment=AWS_REGION=__REGION__
Environment=APP_SECRET_ID=healthconnect/app
Environment=DB_SECRET_ID=__DB_SECRET_ARN__
Environment=DB_HOST=__DB_HOST__
Environment=DB_NAME=healthconnect
Environment=DB_SSLROOTCERT=/opt/healthconnect/rds-ca.pem
Environment=REMINDERS_IN_PROCESS=off
ExecStart=/opt/healthconnect/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips=*
StandardOutput=append:/var/log/healthconnect/api.log
StandardError=append:/var/log/healthconnect/api.log
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
UNIT

cat > /opt/aws/amazon-cloudwatch-agent/etc/config.json <<'CW'
{"logs":{"logs_collected":{"files":{"collect_list":[
  {"file_path":"/var/log/healthconnect/api.log","log_group_name":"/healthconnect/api",
   "log_stream_name":"{instance_id}","retention_in_days":30}]}}}}
CW
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json

systemctl daemon-reload
systemctl enable --now healthconnect
EOF

sed -i '' -e "s|__REPO_URL__|$REPO_URL|" -e "s|__REGION__|$AWS_REGION|" \
  -e "s|__DB_SECRET_ARN__|$DB_SECRET_ARN|" -e "s|__DB_HOST__|$DB_HOST|" /tmp/api-userdata.sh
```

(On Linux, use `sed -i` without the `''`.)

### 6.2 Launch template

```bash
USERDATA=$(base64 < /tmp/api-userdata.sh | tr -d '\n')
cat > /tmp/lt.json <<EOF
{
  "ImageId": "resolve:ssm:/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64",
  "InstanceType": "t3.small",
  "IamInstanceProfile": {"Name": "healthconnect-api-profile"},
  "SecurityGroupIds": ["$APP_SG"],
  "MetadataOptions": {"HttpTokens": "required"},
  "UserData": "$USERDATA",
  "TagSpecifications": [{"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": "healthconnect-api"}]}]
}
EOF
aws ec2 create-launch-template --launch-template-name healthconnect-api --launch-template-data file:///tmp/lt.json
```

`HttpTokens: required` turns on IMDSv2, which protects the server's role credentials from a common attack (SSRF).

### 6.3 Internal load balancer and target group

**Why:** health checks plus automatic replacement (W5: "health checks are what make fault tolerance real").
The load balancer is **internal** (in the private app subnets). CloudFront reaches it through a *VPC origin*, so the traffic between them never crosses the public internet.

```bash
save TG_ARN "$(aws elbv2 create-target-group --name healthconnect-api --protocol HTTP --port 8000 \
  --vpc-id $VPC_ID --target-type instance --health-check-path /health \
  --health-check-interval-seconds 15 --healthy-threshold-count 2 --unhealthy-threshold-count 3 \
  --query 'TargetGroups[0].TargetGroupArn' --output text)"

save ALB_ARN "$(aws elbv2 create-load-balancer --name healthconnect-alb --type application \
  --scheme internal --subnets $APP_A $APP_B --security-groups $ALB_SG \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text)"

aws elbv2 create-listener --load-balancer-arn $ALB_ARN --protocol HTTP --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN

# The load balancer may only send to the API on 8000
aws ec2 authorize-security-group-egress --group-id $ALB_SG \
  --ip-permissions "IpProtocol=tcp,FromPort=8000,ToPort=8000,UserIdGroupPairs=[{GroupId=$APP_SG}]"
```

### 6.4 Auto Scaling group

Min 1, max 1, desired 1: one server, replaced automatically if it fails. Raise max to 2 only after call rooms move into the database.

```bash
aws autoscaling create-auto-scaling-group --auto-scaling-group-name healthconnect-api \
  --launch-template 'LaunchTemplateName=healthconnect-api,Version=$Latest' \
  --min-size 1 --max-size 1 --desired-capacity 1 \
  --vpc-zone-identifier "$APP_A,$APP_B" \
  --target-group-arns $TG_ARN --health-check-type ELB --health-check-grace-period 300
```

**Check** (wait about 5 minutes):

```bash
aws elbv2 describe-target-health --target-group-arn $TG_ARN \
  --query 'TargetHealthDescriptions[].TargetHealth.State'
```

It should say `healthy`. If not, open a shell on the server and read the logs:

```bash
API_ID=$(aws ec2 describe-instances --filters Name=tag:Name,Values=healthconnect-api Name=instance-state-name,Values=running \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
aws ssm start-session --target $API_ID
```

Then on the server: `sudo tail -100 /var/log/cloud-init-output.log` and `sudo tail -100 /var/log/healthconnect/api.log`.

---

## Step 7: First admin account (or demo data)

Open a shell on the API server (see the end of Step 6), then:

```bash
sudo -u hc bash
cd /opt/healthconnect/app/backend
export AWS_REGION=eu-north-1 APP_SECRET_ID=healthconnect/app DB_NAME=healthconnect
export DB_SSLROOTCERT=/opt/healthconnect/rds-ca.pem
export DB_SECRET_ID=$(systemctl show healthconnect -p Environment | tr ' ' '\n' | sed -n 's/^DB_SECRET_ID=//p')
export DB_HOST=$(systemctl show healthconnect -p Environment | tr ' ' '\n' | sed -n 's/^DB_HOST=//p')
```

Then **one** of:

- **Real use:** `../../venv/bin/python prepare_real_use.py <admin_username> "<Full name>"`. It prints a temporary password once.
- **Presentation demo** (fake data only): `../../venv/bin/python seed.py && ../../venv/bin/python seed_demo_data.py`. Label the site as a demo, and run `prepare_real_use.py` before any real patient touches it.

---

## Step 8: Web app and CloudFront

### 8.1 Private S3 bucket

```bash
save WEB_BUCKET healthconnect-web-$ACCOUNT_ID
aws s3api create-bucket --bucket $WEB_BUCKET --create-bucket-configuration LocationConstraint=$AWS_REGION
aws s3api put-public-access-block --bucket $WEB_BUCKET --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

(W6: a public bucket is the most common cloud misconfiguration. Nobody reads this bucket except CloudFront.)

### 8.2 Build and upload

```bash
cd frontend
VITE_API_URL=/api npm run build

# Hashed files: cache for a year. No --delete: phones may still run an older saved copy (PWA)
# that asks for last version's file names; deleting them gives those users a blank white page.
aws s3 sync dist/ s3://$WEB_BUCKET/ \
  --exclude index.html --exclude sw.js --exclude registerSW.js --exclude manifest.webmanifest \
  --cache-control "public,max-age=31536000,immutable"
# Files that must always be fresh, or phones get stuck on an old version of the PWA
for f in index.html sw.js registerSW.js manifest.webmanifest; do
  [ -f dist/$f ] && aws s3 cp dist/$f s3://$WEB_BUCKET/$f --cache-control "no-cache"
done
cd ..
```

### 8.3 CloudFront Function that removes `/api`

The phone calls `/api/patients`; the API expects `/patients`.

```bash
cat > /tmp/strip-api.js <<'EOF'
function handler(event) {
  var request = event.request;
  request.uri = request.uri.replace(/^\/api(?=\/|$)/, '');
  if (request.uri === '') { request.uri = '/'; }
  return request;
}
EOF
aws cloudfront create-function --name hc-strip-api \
  --function-config Comment="Remove /api prefix",Runtime=cloudfront-js-2.0 \
  --function-code fileb:///tmp/strip-api.js
ETAG=$(aws cloudfront describe-function --name hc-strip-api --query ETag --output text)
aws cloudfront publish-function --name hc-strip-api --if-match $ETAG
```

### 8.4 API cache policy (important)

CloudFront drops the `Authorization` header on GET requests unless it's part of a cache policy. Without this, every logged-in GET fails with 401.
This policy includes the header but caches nothing (default TTL 0, and the API sends `Cache-Control: no-store` from Step 1.5).

```bash
cat > /tmp/api-cache-policy.json <<'EOF'
{
  "Name": "hc-api-no-cache",
  "Comment": "API: forward Authorization, never cache",
  "MinTTL": 0, "DefaultTTL": 0, "MaxTTL": 1,
  "ParametersInCacheKeyAndForwardedToOrigin": {
    "EnableAcceptEncodingGzip": true, "EnableAcceptEncodingBrotli": true,
    "HeadersConfig": {"HeaderBehavior": "whitelist", "Headers": {"Quantity": 1, "Items": ["Authorization"]}},
    "CookiesConfig": {"CookieBehavior": "none"},
    "QueryStringsConfig": {"QueryStringBehavior": "all"}
  }
}
EOF
aws cloudfront create-cache-policy --cache-policy-config file:///tmp/api-cache-policy.json
```

### 8.5 Distribution (in the console; much easier than the CLI)

1. **CloudFront → VPC origins → Create VPC origin.**
   Origin ARN: the load balancer (`healthconnect-alb`). Protocol: **HTTP only**, port **80**. Wait until it says *Deployed* (about 10 minutes).
   *If VPC origins aren't offered in eu-north-1:* recreate the load balancer with `--scheme internet-facing --subnets $PUB_A $PUB_B` and use it as a normal origin. Note in the report that CloudFront → load balancer is then plain HTTP over the internet (fix it with your own domain and an ACM certificate on the load balancer).
2. **Create distribution.**
   - Origin: your S3 bucket from the list. Origin access: **Origin access control settings (recommended)** → create a new OAC.
   - Viewer protocol policy: **Redirect HTTP to HTTPS**.
   - Cache policy: **CachingOptimized**.
   - Web Application Firewall: **Do not enable** (costs extra; mention it as a production step).
   - Price class: **Use all edge locations** (the cheaper classes leave out Africa).
   - Default root object: `index.html`.
   - **Do not add custom error pages.** They would hide the API's real 403/404 answers.
3. After creating it, the console shows a **bucket policy**. Copy it into S3 → `healthconnect-web-…` → Permissions → Bucket policy.
4. **Origins → Create origin:** choose the VPC origin from step 1.
5. **Behaviors → Create behavior:**
   - Path pattern: `/api/*`, origin: the VPC origin.
   - Viewer protocol policy: **Redirect HTTP to HTTPS**.
   - Allowed methods: **GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE**.
   - Cache policy: **hc-api-no-cache**. Origin request policy: **AllViewerExceptHostHeader**.
   - Function associations → Viewer request → CloudFront Functions → **hc-strip-api**.

Save the address:

```bash
save CF_DOMAIN dxxxxxxxxxxxx.cloudfront.net        # from the console
save CF_ID EXXXXXXXXXXXXX                          # the distribution ID
```

### 8.6 Tell the API its own address and restart it

```bash
python3 - <<EOF > /tmp/secret.json
import json, subprocess
s = json.loads(subprocess.check_output(["aws","secretsmanager","get-secret-value","--secret-id","healthconnect/app","--query","SecretString","--output","text"]))
s["FRONTEND_ORIGINS"] = "https://$CF_DOMAIN"
print(json.dumps(s))
EOF
aws secretsmanager put-secret-value --secret-id healthconnect/app --secret-string file:///tmp/secret.json
rm /tmp/secret.json

aws ssm send-command --document-name AWS-RunShellScript \
  --targets Key=tag:Name,Values=healthconnect-api \
  --parameters 'commands=["systemctl restart healthconnect"]'
```

**Check:** open `https://<CF_DOMAIN>` on your phone and log in. `https://<CF_DOMAIN>/api/health` should answer.

---

## Step 9: SMS reminders as a Lambda function

**Why:** W7 names appointment reminders as the textbook serverless job: short, bursty, fine with a cold start. EventBridge runs it every 10 minutes, it retries on failure, and anything that still fails lands in a dead-letter queue instead of vanishing.

### 9.1 Dead-letter queue

```bash
save DLQ_URL "$(aws sqs create-queue --queue-name healthconnect-reminders-dlq \
  --attributes MessageRetentionPeriod=1209600 --query QueueUrl --output text)"
save DLQ_ARN "$(aws sqs get-queue-attributes --queue-url $DLQ_URL --attribute-names QueueArn \
  --query Attributes.QueueArn --output text)"
```

### 9.2 Role for the function

```bash
cat > /tmp/lambda-trust.json <<'EOF'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}
EOF
cat > /tmp/lambda-policy.json <<EOF
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["secretsmanager:GetSecretValue"],"Resource":["$APP_SECRET_ARN","$DB_SECRET_ARN"]},
  {"Effect":"Allow","Action":["sqs:SendMessage"],"Resource":"$DLQ_ARN"}
]}
EOF
save LAMBDA_ROLE_ARN "$(aws iam create-role --role-name healthconnect-reminders-role \
  --assume-role-policy-document file:///tmp/lambda-trust.json --query Role.Arn --output text)"
aws iam put-role-policy --role-name healthconnect-reminders-role --policy-name reminders --policy-document file:///tmp/lambda-policy.json
aws iam attach-role-policy --role-name healthconnect-reminders-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
sleep 10   # new roles take a few seconds to be usable
```

### 9.3 Package and create the function

```bash
rm -rf build/lambda && mkdir -p build/lambda
pip install --quiet --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 \
  --only-binary=:all: --target build/lambda "psycopg[binary]" requests python-dotenv
cp backend/{lambda_handler,reminders,database,sms,config}.py build/lambda/
curl -fsSL -o build/lambda/rds-ca.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
(cd build/lambda && zip -qr ../reminders.zip .)

save FN_ARN "$(aws lambda create-function --function-name healthconnect-send-reminders \
  --runtime python3.12 --architectures x86_64 --handler lambda_handler.handler \
  --zip-file fileb://build/reminders.zip --role $LAMBDA_ROLE_ARN \
  --timeout 60 --memory-size 256 \
  --vpc-config SubnetIds=$APP_A,$APP_B,SecurityGroupIds=$LAMBDA_SG \
  --environment "Variables={APP_SECRET_ID=healthconnect/app,DB_SECRET_ID=$DB_SECRET_ARN,DB_HOST=$DB_HOST,DB_NAME=healthconnect,DB_SSLROOTCERT=/var/task/rds-ca.pem}" \
  --dead-letter-config TargetArn=$DLQ_ARN \
  --query FunctionArn --output text)"
aws lambda wait function-active-v2 --function-name healthconnect-send-reminders
aws lambda put-function-event-invoke-config --function-name healthconnect-send-reminders --maximum-retry-attempts 2
```

### 9.4 Schedule it every 10 minutes

```bash
cat > /tmp/scheduler-trust.json <<'EOF'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"scheduler.amazonaws.com"},"Action":"sts:AssumeRole"}]}
EOF
save SCHED_ROLE_ARN "$(aws iam create-role --role-name healthconnect-scheduler-role \
  --assume-role-policy-document file:///tmp/scheduler-trust.json --query Role.Arn --output text)"
aws iam put-role-policy --role-name healthconnect-scheduler-role --policy-name invoke-reminders \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"lambda:InvokeFunction\",\"Resource\":\"$FN_ARN\"}]}"
sleep 10

aws scheduler create-schedule --name healthconnect-reminders \
  --schedule-expression "rate(10 minutes)" --flexible-time-window Mode=OFF \
  --target "Arn=$FN_ARN,RoleArn=$SCHED_ROLE_ARN"
```

**Check:**

```bash
aws lambda invoke --function-name healthconnect-send-reminders /tmp/out.json && cat /tmp/out.json
aws sqs get-queue-attributes --queue-url $DLQ_URL --attribute-names ApproximateNumberOfMessages
```

Book a test appointment for tomorrow on a test phone number and confirm exactly **one** reminder arrives.

---

## Step 10: Alarms and logs

**Why:** in the cloud nobody watches the terminal. AWS must tell you when something breaks (W7 observability). Never log patient data (W6).

```bash
save TOPIC_ARN "$(aws sns create-topic --name healthconnect-alerts --query TopicArn --output text)"
read -rp "Email for alerts: " EMAIL
aws sns subscribe --topic-arn $TOPIC_ARN --protocol email --notification-endpoint "$EMAIL"
# Click the confirmation link in the email

LB_DIM=${ALB_ARN#*loadbalancer/}
TG_DIM=${TG_ARN##*:}
alarm() { aws cloudwatch put-metric-alarm --alarm-actions $TOPIC_ARN --treat-missing-data notBreaching "$@"; }

alarm --alarm-name hc-api-5xx --namespace AWS/ApplicationELB --metric-name HTTPCode_Target_5XX_Count \
  --dimensions Name=LoadBalancer,Value=$LB_DIM --statistic Sum --period 300 --evaluation-periods 1 \
  --threshold 5 --comparison-operator GreaterThanOrEqualToThreshold

alarm --alarm-name hc-api-unhealthy --namespace AWS/ApplicationELB --metric-name UnHealthyHostCount \
  --dimensions Name=LoadBalancer,Value=$LB_DIM Name=TargetGroup,Value=$TG_DIM --statistic Maximum \
  --period 60 --evaluation-periods 3 --threshold 1 --comparison-operator GreaterThanOrEqualToThreshold

alarm --alarm-name hc-db-cpu --namespace AWS/RDS --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value=healthconnect-prod --statistic Average \
  --period 300 --evaluation-periods 3 --threshold 80 --comparison-operator GreaterThanThreshold

alarm --alarm-name hc-db-storage --namespace AWS/RDS --metric-name FreeStorageSpace \
  --dimensions Name=DBInstanceIdentifier,Value=healthconnect-prod --statistic Minimum \
  --period 300 --evaluation-periods 1 --threshold 2147483648 --comparison-operator LessThanThreshold

alarm --alarm-name hc-reminders-dlq --namespace AWS/SQS --metric-name ApproximateNumberOfMessagesVisible \
  --dimensions Name=QueueName,Value=healthconnect-reminders-dlq --statistic Maximum \
  --period 300 --evaluation-periods 1 --threshold 1 --comparison-operator GreaterThanOrEqualToThreshold

alarm --alarm-name hc-reminders-errors --namespace AWS/Lambda --metric-name Errors \
  --dimensions Name=FunctionName,Value=healthconnect-send-reminders --statistic Sum \
  --period 900 --evaluation-periods 1 --threshold 1 --comparison-operator GreaterThanOrEqualToThreshold
```

**Budget alert (console):** Billing → Budgets → Create budget → Monthly cost budget, **$40**, email at 80% and 100%. W7: surprise bills come from misconfiguration (a retry loop), not base prices.

**Logs:** API logs are in CloudWatch log group `/healthconnect/api`; Lambda logs are in `/aws/lambda/healthconnect-send-reminders`.

---

## Step 11: Automatic deployment from GitHub

**Why:** every push to `main` is tested and deployed with no manual steps, and GitHub holds **no AWS keys**: it gets short-lived credentials through OIDC (W6: roles over long-lived keys).

### 11.1 Let GitHub assume a deploy role

```bash
aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com

cat > /tmp/gh-trust.json <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
  "Principal":{"Federated":"arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"},
  "Action":"sts:AssumeRoleWithWebIdentity",
  "Condition":{
    "StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com"},
    "StringLike":{"token.actions.githubusercontent.com:sub":"repo:ASU-MICS-2028/cc-group-2-prosit-2:ref:refs/heads/main"}}}]}
EOF
cat > /tmp/gh-policy.json <<EOF
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":["s3:ListBucket"],"Resource":"arn:aws:s3:::$WEB_BUCKET"},
  {"Effect":"Allow","Action":["s3:PutObject","s3:DeleteObject"],"Resource":"arn:aws:s3:::$WEB_BUCKET/*"},
  {"Effect":"Allow","Action":["cloudfront:CreateInvalidation"],"Resource":"arn:aws:cloudfront::$ACCOUNT_ID:distribution/$CF_ID"},
  {"Effect":"Allow","Action":["ssm:SendCommand"],"Resource":"arn:aws:ssm:$AWS_REGION::document/AWS-RunShellScript"},
  {"Effect":"Allow","Action":["ssm:SendCommand"],"Resource":"arn:aws:ec2:$AWS_REGION:$ACCOUNT_ID:instance/*",
   "Condition":{"StringEquals":{"aws:ResourceTag/Name":"healthconnect-api"}}},
  {"Effect":"Allow","Action":["lambda:UpdateFunctionCode"],"Resource":"$FN_ARN"}
]}
EOF
save GH_ROLE_ARN "$(aws iam create-role --role-name healthconnect-github-deploy \
  --assume-role-policy-document file:///tmp/gh-trust.json --query Role.Arn --output text)"
aws iam put-role-policy --role-name healthconnect-github-deploy --policy-name deploy --policy-document file:///tmp/gh-policy.json
echo "AWS_ROLE_ARN=$GH_ROLE_ARN  WEB_BUCKET=$WEB_BUCKET  CF_ID=$CF_ID"
```

A repo admin adds those three as **repository variables** (Settings → Secrets and variables → Actions → Variables).

### 11.2 Workflow `.github/workflows/deploy.yml`

```yaml
name: Deploy to AWS
on:
  push:
    branches: [main]
permissions:
  id-token: write   # lets GitHub request an AWS token
  contents: read
jobs:
  tests:
    uses: ./.github/workflows/tests.yml   # tests.yml needs "on: workflow_call" added
  deploy:
    needs: tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: eu-north-1
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - name: Build and upload the web app
        working-directory: frontend
        run: |
          npm ci
          VITE_API_URL=/api npm run build
          # No --delete: older saved copies of the PWA still need last version's files
          aws s3 sync dist/ s3://${{ vars.WEB_BUCKET }}/ \
            --exclude index.html --exclude sw.js --exclude registerSW.js --exclude manifest.webmanifest \
            --cache-control "public,max-age=31536000,immutable"
          for f in index.html sw.js registerSW.js manifest.webmanifest; do
            [ -f dist/$f ] && aws s3 cp dist/$f s3://${{ vars.WEB_BUCKET }}/$f --cache-control no-cache
          done
          aws cloudfront create-invalidation --distribution-id ${{ vars.CF_ID }} --paths "/index.html" "/sw.js"
      - name: Update the API server
        run: |
          aws ssm send-command --document-name AWS-RunShellScript \
            --targets Key=tag:Name,Values=healthconnect-api \
            --parameters 'commands=["cd /opt/healthconnect/app && sudo -u hc git pull --ff-only && sudo -u hc /opt/healthconnect/venv/bin/pip install -q -r backend/requirements.txt && systemctl restart healthconnect"]'
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Update the reminder Lambda
        run: |
          mkdir -p build/lambda
          pip install -q --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 \
            --only-binary=:all: --target build/lambda "psycopg[binary]" requests python-dotenv
          cp backend/{lambda_handler,reminders,database,sms,config}.py build/lambda/
          curl -fsSL -o build/lambda/rds-ca.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
          (cd build/lambda && zip -qr ../reminders.zip .)
          aws lambda update-function-code --function-name healthconnect-send-reminders --zip-file fileb://build/reminders.zip
```

---

## Step 12: TURN relay for video calls

**Why:** on Ghanaian mobile networks, direct phone-to-phone video often fails. TURN relays it (W7). A relayed call uses several hundred MB an hour, so budget for data transfer (about $0.09/GB).
Needs code change 1.11.

```bash
save TURN_SG "$(aws ec2 create-security-group --group-name hc-turn-sg --description 'coturn relay' \
  --vpc-id $VPC_ID --query GroupId --output text)"
aws ec2 authorize-security-group-ingress --group-id $TURN_SG --ip-permissions \
  'IpProtocol=udp,FromPort=3478,ToPort=3478,IpRanges=[{CidrIp=0.0.0.0/0}]' \
  'IpProtocol=tcp,FromPort=3478,ToPort=3478,IpRanges=[{CidrIp=0.0.0.0/0}]' \
  'IpProtocol=udp,FromPort=49152,ToPort=65535,IpRanges=[{CidrIp=0.0.0.0/0}]'

save TURN_EIP_ALLOC "$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)"
save TURN_IP "$(aws ec2 describe-addresses --allocation-ids $TURN_EIP_ALLOC --query 'Addresses[0].PublicIp' --output text)"
TURN_SECRET=$(aws secretsmanager get-secret-value --secret-id healthconnect/app --query SecretString --output text \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["TURN_SECRET"])')

cat > /tmp/turn-userdata.sh <<EOF
#!/bin/bash
apt-get update && apt-get install -y coturn
PRIVATE_IP=\$(hostname -I | awk '{print \$1}')
cat > /etc/turnserver.conf <<CONF
listening-port=3478
external-ip=$TURN_IP/\$PRIVATE_IP
realm=healthconnect
use-auth-secret
static-auth-secret=$TURN_SECRET
min-port=49152
max-port=65535
fingerprint
no-cli
no-multicast-peers
# Never relay into private networks (stops the relay being used to reach the VPC)
denied-peer-ip=10.0.0.0-10.255.255.255
denied-peer-ip=172.16.0.0-172.31.255.255
denied-peer-ip=192.168.0.0-192.168.255.255
denied-peer-ip=169.254.0.0-169.254.255.255
user-quota=12
total-quota=200
CONF
sed -i 's/^#\?TURNSERVER_ENABLED=.*/TURNSERVER_ENABLED=1/' /etc/default/coturn || true
systemctl enable --now coturn
EOF

save TURN_ID "$(aws ec2 run-instances \
  --image-id resolve:ssm:/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
  --instance-type t3.micro --subnet-id $PUB_A --security-group-ids $TURN_SG \
  --metadata-options HttpTokens=required --user-data file:///tmp/turn-userdata.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=healthconnect-turn}]' \
  --query 'Instances[0].InstanceId' --output text)"
aws ec2 wait instance-running --instance-ids $TURN_ID
aws ec2 associate-address --instance-id $TURN_ID --allocation-id $TURN_EIP_ALLOC
unset TURN_SECRET; rm /tmp/turn-userdata.sh
```

Add `TURN_HOST=<TURN_IP>` to the app secret (same way as Step 8.6) and restart the API.
**Check:** with <https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/> and a credential from `/api/calls/ice-servers`, you should see a `relay` candidate.

---

## Step 13: Control the cost

**Stop everything between demos** (the database restarts by itself after 7 days, so stop it again if needed):

```bash
source ~/hc-aws.env
aws autoscaling update-auto-scaling-group --auto-scaling-group-name healthconnect-api --min-size 0 --desired-capacity 0
aws rds stop-db-instance --db-instance-identifier healthconnect-prod
aws ec2 stop-instances --instance-ids $NAT_ID $TURN_ID
aws scheduler update-schedule --name healthconnect-reminders --state DISABLED \
  --schedule-expression "rate(10 minutes)" --flexible-time-window Mode=OFF --target "Arn=$FN_ARN,RoleArn=$SCHED_ROLE_ARN"
```

**Start again** (about 10 minutes before a demo):

```bash
aws rds start-db-instance --db-instance-identifier healthconnect-prod
aws ec2 start-instances --instance-ids $NAT_ID $TURN_ID
aws rds wait db-instance-available --db-instance-identifier healthconnect-prod
aws autoscaling update-auto-scaling-group --auto-scaling-group-name healthconnect-api --min-size 1 --desired-capacity 1
aws scheduler update-schedule --name healthconnect-reminders --state ENABLED \
  --schedule-expression "rate(10 minutes)" --flexible-time-window Mode=OFF --target "Arn=$FN_ARN,RoleArn=$SCHED_ROLE_ARN"
```

The load balancer (~$18/month) and the Elastic IP keep costing money while stopped. Delete them if there's a long gap.

**Rough monthly cost while running:**

| Item | Size | About per month |
|---|---|---|
| EC2 API | t3.small | $15–17 |
| RDS PostgreSQL + 20 GB | db.t4g.micro | $14–16 |
| Load balancer | 1 | $18–20 |
| NAT instance | t4g.nano | $3 |
| TURN relay | t3.micro | $8 + data |
| Lambda, EventBridge, SQS | class volume | ~$0 |
| Secrets Manager | 2 secrets | $1 |
| CloudFront, S3, CloudWatch | small | $2–4 |
| **Total** | | **~$60–70** |

These are estimates. Confirm them in the AWS Pricing Calculator for the report.

---

## Step 14: Final checklist

Test on a real phone over mobile data, not Wi-Fi:

- [ ] `https://<CF_DOMAIN>` loads and shows the padlock
- [ ] Login works for each role (CHV, nurse, doctor, GHS, admin)
- [ ] A CHV registers a patient (with consent) and records a visit
- [ ] Airplane mode: record a check offline, turn signal back on, and it syncs
- [ ] CHV → nurse referral; nurse escalates; doctor completes it
- [ ] Booking an appointment sends **one** confirmation SMS; the reminder arrives **once**
- [ ] A video call connects between two phones on different networks (TURN)
- [ ] GHS dashboard shows district totals and the map
- [ ] RDS: encryption on, not public. S3: all public access blocked
- [ ] `psql` from your laptop to the database **fails** (it's private)
- [ ] Stopping the API server: the Auto Scaling group replaces it within about 5 minutes
- [ ] CloudWatch has logs in `/healthconnect/api` with no patient names in them
- [ ] An alarm email arrives when you put a test message in the DLQ
- [ ] The README's Phase 3 boxes are ticked, and the report records: region choice (Act 843), the NAT instance trade-off, one API server until calls are stateless, and the TURN data cost
