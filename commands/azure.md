# Azure CLI Command Reference (DevOps-Relevant)

Source material for `scenarios/azure/`. Syntax is Azure CLI 2.x (`az`).

## Login, Subscriptions & Defaults

```
az login
az login --use-device-code
az account show
az account list --output table
az account set --subscription <name-or-id>
az configure --defaults group=<rg> location=<region>
az group list --output table
az group create --name <rg> --location <region>
az group delete --name <rg> --yes --no-wait
az resource list --resource-group <rg> --output table
```

## Output & Filtering

```
--output json | table | tsv | yaml
--query '<JMESPath>'
-g <rg>   (short for --resource-group)
-n <name> (short for --name)
```

## Virtual Machines

```
az vm list --output table
az vm list -d --query "[].{name:name, state:powerState, ip:publicIps}" --output table
az vm show -g <rg> -n <vm> -d
az vm create -g <rg> -n <vm> --image Ubuntu2204 --size Standard_B2s --admin-username azureuser --ssh-key-values ~/.ssh/id_ed25519.pub --public-ip-address ""
az vm start|stop|deallocate|restart -g <rg> -n <vm>
az vm get-instance-view -g <rg> -n <vm> --query instanceView.statuses
az vm run-command invoke -g <rg> -n <vm> --command-id RunShellScript --scripts "<cmd>"
az vm boot-diagnostics get-boot-log -g <rg> -n <vm>
az vm resize -g <rg> -n <vm> --size <size>
az vm list-sizes --location <region>
az vm extension list -g <rg> --vm-name <vm>
az vmss list-instances -g <rg> -n <vmss>
```

## Connecting

```
az ssh vm -g <rg> -n <vm>
az network bastion ssh --name <bastion> -g <rg> --target-resource-id <vm-id> --auth-type ssh-key --username azureuser --ssh-key <key>
ssh azureuser@<public-ip>
```

## Networking (VNets, NSGs, Routes)

```
az network vnet list --output table
az network vnet show -g <rg> -n <vnet>
az network vnet subnet list -g <rg> --vnet-name <vnet> --output table
az network nsg list --output table
az network nsg rule list -g <rg> --nsg-name <nsg> --output table
az network nsg rule create -g <rg> --nsg-name <nsg> -n <rule> --priority <n> --direction Inbound --access Allow --protocol Tcp --destination-port-ranges <port> --source-address-prefixes <cidr>
az network nsg rule update -g <rg> --nsg-name <nsg> -n <rule> --access Deny
az network nic list-effective-nsg -g <rg> -n <nic>
az network nic show-effective-route-table -g <rg> -n <nic> --output table
az network route-table list --output table
az network route-table route list -g <rg> --route-table-name <rt> --output table
az network route-table route delete -g <rg> --route-table-name <rt> -n <route>
az network public-ip list --output table
az network watcher test-ip-flow -g <rg> --vm <vm> --direction Inbound --protocol TCP --local <ip:port> --remote <ip:port>
az network nat gateway list --output table
az network private-endpoint list --output table
```

## Identity & Access (Entra ID / RBAC)

```
az ad signed-in-user show
az role assignment list --assignee <principal> --all --output table
az role assignment list --scope <scope> --output table
az role assignment create --assignee <principal-id> --role "<role>" --scope <scope>
az role definition list --name "<role>"
az vm identity assign -g <rg> -n <vm>
az identity show -g <rg> -n <identity>
az ad sp list --display-name <name>
```

## Key Vault & Storage

```
az keyvault list --output table
az keyvault secret list --vault-name <kv>
az keyvault secret show --vault-name <kv> -n <secret>
az keyvault secret set --vault-name <kv> -n <secret> --value <value>
az storage account list --output table
az storage account show -n <account> --query networkRuleSet
az storage account update -n <account> -g <rg> --default-action Deny
az storage account network-rule add -g <rg> --account-name <account> --subnet <subnet-id>
az storage blob list --account-name <account> --container-name <c> --auth-mode login --output table
```

## Monitoring

```
az monitor activity-log list --resource-group <rg> --offset 1h --output table
az monitor metrics list --resource <id> --metric "Percentage CPU" --interval PT5M
az monitor log-analytics query -w <workspace-id> --analytics-query "<KQL>"
az monitor alert list --output table
```

## AKS

```
az aks list --output table
az aks get-credentials -g <rg> -n <cluster>
az aks show -g <rg> -n <cluster> --query kubernetesVersion
az aks nodepool list -g <rg> --cluster-name <cluster> --output table
az aks upgrade -g <rg> -n <cluster> --kubernetes-version <v>
```
