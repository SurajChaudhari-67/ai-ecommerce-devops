# Deployment guide

Replace values in angle brackets with your own. Never commit passwords, tfvars or tfstate.

## 1. Run locally

```bash
docker compose -f docker/docker-compose.yml up -d --build
curl http://localhost:8081/health
```
Port 8081 is used because Jenkins uses 8080.

## 2. Azure login and providers

```powershell
az login --tenant "<tenant-id>" --scope "https://management.core.windows.net//.default"
az provider register --namespace Microsoft.ContainerService
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.Compute
az provider register --namespace Microsoft.Network
```

## 3. Infrastructure (Terraform)

Create `terraform/terraform.tfvars` (ignored by Git): ```powershell
cd terraform
terraform init
terraform plan
terraform apply
```
The region must be one allowed by the subscription policy (indiasouthcentral here).

## 4. Image to ACR

```powershell
az acr login --name acrnexvionz034e
docker build -f docker/Dockerfile -t acrnexvionz034e.azurecr.io/nexvion-web:v1 .
docker push acrnexvionz034e.azurecr.io/nexvion-web:v1
```

## 5. Connect to the cluster

```powershell
az aks get-credentials -g rg-nexvion-dev -n aks-nexvion-dev --overwrite-existing
kubectl get nodes
```
If AKS has no pull access to ACR: `az aks update -g rg-nexvion-dev -n aks-nexvion-dev --attach-acr acrnexvionz034e`

## 6. Ingress controller and application

```powershell
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace --set "controller.service.annotations.service\.beta\.kubernetes\.io/azure-load-balancer-health-probe-request-path=/healthz"

helm install nexvion helm/ecommerce -n nexvion --create-namespace
kubectl get pods,svc,ingress -n nexvion
```
Open `http://<ingress-external-ip>`.

Rolling update and rollback:
```powershell
helm upgrade nexvion helm/ecommerce -n nexvion --set image.tag=<tag>
helm history nexvion -n nexvion
helm rollback nexvion 1 -n nexvion
```

## 7. Jenkins (runs in WSL)

```bash
export JENKINS_HOME=~/jenkins/home
java -jar ~/jenkins/jenkins.war --httpPort=8080
```
Requirements on the Jenkins machine: git, docker, az, kubectl, helm, trivy. The `jenkins` user must be in the `docker` group.

Create a Service Principal with Contributor on the resource group and AcrPush on the registry. In Jenkins add credentials:
- `azure-sp` (username with password): service principal appId and password
- `azure-tenant` (secret text): tenant id

Create a Pipeline job `nexvion-pipeline`: Pipeline script from SCM, repository URL of this repo, branch `*/develop`, script path `jenkins/Jenkinsfile`, Poll SCM `H/5 * * * *`.

## 8. Monitoring

```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace -f monitoring/prometheus/values.yaml --set grafana.adminPassword=<choose-a-password>
kubectl port-forward -n monitoring deploy/monitoring-grafana 3000:3000
```
Open `http://localhost:3000`, user `admin`. Dashboards: Kubernetes / Compute Resources (Namespace Pods, Cluster) and Node Exporter / Nodes.

## 9. Logging (ELK)

```powershell
kubectl apply -f logging/elk/elasticsearch.yaml
kubectl apply -f logging/elk/kibana.yaml
kubectl apply -f logging/elk/filebeat.yaml
kubectl port-forward -n logging svc/kibana 5601:5601
```
In Kibana create a data view `filebeat-*` with timestamp `@timestamp`. Logs appear after the app receives traffic.

## 10. Ansible (target: local WSL)

```powershell
wsl -u root bash -c "apt-get update && apt-get install -y ansible"
wsl -u root bash -c "cd /mnt/c/Users/<user>/ai-ecommerce-devops/ansible && ansible-playbook -i inventory playbook.yml"
```
Run it twice, the second run should report `changed=0` (idempotent).

## 11. AI incident analysis

```powershell
wsl -u root python3 ai/incident-analysis/analyze.py --file ai/incident-analysis/sample_logs.txt
```
From Elasticsearch (with `kubectl port-forward -n logging svc/elasticsearch 9200:9200` running):
```powershell
wsl -u root python3 ai/incident-analysis/analyze.py --es http://localhost:9200 --minutes 120
```

## 12. Stop the cluster after work

```powershell
az aks stop -g rg-nexvion-dev -n aks-nexvion-dev
az aks show -g rg-nexvion-dev -n aks-nexvion-dev --query powerState.code -o tsv
```
The second command must print `Stopped`. Start again with `az aks start`, then run `az aks get-credentials` again.
