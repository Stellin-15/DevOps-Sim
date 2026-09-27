# Google Cloud CLI Command Reference (DevOps-Relevant)

Source material for `scenarios/gcp/`. Syntax is the Google Cloud CLI (`gcloud`).

## Auth, Projects & Configurations

```
gcloud auth login
gcloud auth list
gcloud auth application-default login
gcloud config list
gcloud config set project <project-id>
gcloud config set compute/zone <zone>
gcloud config configurations list
gcloud config configurations create <name>
gcloud config configurations activate <name>
gcloud projects list
gcloud services list --enabled
gcloud services enable <api>.googleapis.com
```

## Output & Filtering

```
--format="table(name,zone.basename(),status)"
--format=json | yaml | value(<field>)
--filter="status=RUNNING AND labels.env=prod"
--project <project-id>
```

## Compute Engine VMs

```
gcloud compute instances list
gcloud compute instances list --filter="status=RUNNING" --format="table(name,zone.basename(),networkInterfaces[0].networkIP,networkInterfaces[0].accessConfigs[0].natIP)"
gcloud compute instances describe <vm> --zone <zone>
gcloud compute instances create <vm> --zone <zone> --machine-type e2-medium --image-family debian-12 --image-project debian-cloud --subnet <subnet> --tags <tag> --no-address
gcloud compute instances start|stop|reset <vm> --zone <zone>
gcloud compute instances add-tags <vm> --zone <zone> --tags <tag>
gcloud compute instances get-serial-port-output <vm> --zone <zone>
gcloud compute instances set-service-account <vm> --zone <zone> --service-account <sa> --scopes cloud-platform
gcloud compute instance-groups managed list
gcloud compute instance-groups managed rolling-action replace <mig> --zone <zone>
gcloud compute machine-types list --zones <zone>
```

## Connecting

```
gcloud compute ssh <vm> --zone <zone>
gcloud compute ssh <vm> --zone <zone> --tunnel-through-iap
gcloud compute ssh <vm> --zone <zone> --troubleshoot
gcloud compute start-iap-tunnel <vm> <port> --local-host-port=localhost:<port> --zone <zone>
gcloud compute os-login ssh-keys list
```

## VPC Networking

```
gcloud compute networks list
gcloud compute networks create <net> --subnet-mode=custom
gcloud compute networks subnets list --network <net>
gcloud compute networks subnets create <subnet> --network <net> --region <region> --range <cidr> --enable-private-ip-google-access
gcloud compute firewall-rules list --filter="network=<net>" --format="table(name,direction,priority,sourceRanges.list(),allowed[].map().firewall_rule().list(),targetTags.list())"
gcloud compute firewall-rules create <rule> --network <net> --allow tcp:<port> --source-ranges <cidr> --target-tags <tag>
gcloud compute firewall-rules update <rule> --target-tags <tag>
gcloud compute firewall-rules delete <rule>
gcloud compute routes list --filter="network=<net>"
gcloud compute routers list
gcloud compute routers nats create <nat> --router <router> --region <region> --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges
gcloud compute routers get-nat-mapping-info <router> --region <region>
gcloud compute addresses list
gcloud compute networks peerings list
gcloud network-management connectivity-tests create <test> --source-instance <vm> --destination-ip-address <ip> --destination-port <port> --protocol TCP
gcloud network-management connectivity-tests describe <test>
```

## IAM & Service Accounts

```
gcloud projects get-iam-policy <project-id> --flatten="bindings[].members" --filter="bindings.members:<member>" --format="table(bindings.role)"
gcloud projects add-iam-policy-binding <project-id> --member=serviceAccount:<sa> --role=<role>
gcloud iam service-accounts list
gcloud iam service-accounts create <name>
gcloud iam service-accounts keys list --iam-account <sa>
gcloud iam service-accounts keys disable|delete <key-id> --iam-account <sa>
gcloud iam service-accounts add-iam-policy-binding <sa> --member=user:<email> --role=roles/iam.serviceAccountTokenCreator
gcloud storage ls --impersonate-service-account=<sa>
gcloud policy-intelligence troubleshoot-policy iam <resource> --principal-email=<email> --permission=<permission>
gcloud resource-manager org-policies list --project <project-id>
```

## Storage

```
gcloud storage ls
gcloud storage ls gs://<bucket>/**
gcloud storage cp <file> gs://<bucket>/
gcloud storage rsync <dir> gs://<bucket>/<prefix> --recursive
gcloud storage buckets describe gs://<bucket>
gcloud storage buckets get-iam-policy gs://<bucket>
gcloud storage buckets update gs://<bucket> --public-access-prevention
```

## Logging, Monitoring & Quotas

```
gcloud logging read 'resource.type="gce_instance" AND severity>=ERROR' --limit 20 --freshness 1h
gcloud logging read 'protoPayload.methodName="v1.compute.firewalls.insert"' --limit 5
gcloud compute regions describe <region> --format="table(quotas.metric,quotas.limit,quotas.usage)"
gcloud monitoring policies list
```

## GKE

```
gcloud container clusters list
gcloud container clusters get-credentials <cluster> --region <region>
gcloud container node-pools list --cluster <cluster> --region <region>
gcloud container clusters upgrade <cluster> --region <region> --master --cluster-version <v>
```
