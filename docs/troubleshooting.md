# Troubleshooting log

Real problems met during the project and how each was fixed.

## Azure

**Region blocked: RequestDisallowedByAzure**
- Cause: the student subscription has an "Allowed resource deployment regions" policy, and centralindia is not allowed.
- Fix: `az policy assignment list` showed the allowed regions (indiasouthcentral, malaysiawest, uaenorth, eastasia, koreacentral). Location changed to indiasouthcentral.

**AADSTS50076 on `az provider register`**
- Cause: the old login had no multi-factor authentication.
- Fix: `az logout`, then `az login --tenant <tenant-id> --scope https://management.core.windows.net//.default` and complete MFA.

**Terraform plan always shows 1 change (node_soak_duration_in_minutes)**
- Cause: Azure sets a default that is not in the Terraform code.
- Fix: added an `upgrade_settings` block (max_surge 10%, node_soak_duration 0) to the default node pool, plan then showed no changes.

**`az aks start` said OperationNotAllowed**
- Cause: the cluster was not stopped, it was still running. An earlier `az aks stop` had not completed and nobody verified it.
- Fix and lesson: always verify with `az aks show --query powerState.code -o tsv`, it must print `Stopped`.

**helm / kubectl: cluster unreachable**
- Cause: AKS was stopped.
- Fix: `az aks start`, `az aks get-credentials --overwrite-existing`, wait for nodes Ready.

## Git and GitHub

**`.gitignore` became a folder**
- Cause: created with the wrong path, so Git ignored nothing and tfstate/tfvars would have been committed.
- Fix: moved the file out, deleted the folder, renamed to `.gitignore`. Verified with `git ls-files --others --exclude-standard terraform` that tfstate and tfvars were not listed.

**Commit went to `develop`, pull request created in the wrong direction**
- Fix: moved the commit to a feature branch, `git reset --hard origin/develop`, opened the PR again with base develop. Rule: check `git branch --show-current` before committing.

**LF/CRLF warnings, shell scripts failing on Linux**
- Fix: added `.gitattributes` with `eol=lf` for sh, yml, yaml, Dockerfile and conf.

**Security Scans stage missing in Jenkins even after merge**
- Cause: the Jenkinsfile change had never been saved and committed (the other files had).
- Fix: checked with `git show origin/develop:jenkins/Jenkinsfile | Select-String "Security Scans"`, re-applied, committed and merged.

## Docker and Kubernetes

**Website did not open on localhost:8080**
- Cause: Jenkins already used port 8080.
- Fix: mapped the website to 8081 (`8081:8080`).

**`kubectl apply -f kubernetes/` failed: namespace not found**
- Cause: files apply alphabetically, so deployment.yaml ran before namespace.yaml.
- Fix: apply the namespace first. Helm does not have this problem.

**Helm not recognised in PowerShell**
- Cause: PATH not refreshed after install.
- Fix: close VS Code completely and reopen. Helm was also installed inside WSL for Jenkins.

## Jenkins

**Could not log in (browser autofill filled wrong credentials)**
- Fix: disabled security temporarily and restarted, then set up a fresh Jenkins running as the normal user (JENKINS_HOME in the home folder), created a new admin and turned security back on.

**"Unable to find Jenkinsfile"**
- Cause: job setting (branch / script path) did not match the repository while the file existed in develop.
- Fix: Script Path `jenkins/Jenkinsfile`, branch `*/develop`.

**Azure Login stage failed: AADSTS90002 tenant not found**
- Cause: appId and tenant id were typed by hand with typos (appId 658edbde-... instead of 658ebde3-...).
- Fix: copy values from the CLI to the clipboard instead of typing: `az ad sp list --display-name <name> --query "[0].appId" -o tsv | Set-Clipboard`.

**`az role assignment create` failed with `<appId>`**
- Cause: placeholder typed literally, PowerShell treats `<` as an operator. A second attempt failed because one character of the appId was mistyped.
- Fix: stored values in variables (`$appId`, `$acr`) and passed those.

**docker permission denied / trivy not found inside Jenkins**
- Fix: added jenkins to the docker group and installed Trivy, restarted Jenkins.

## Monitoring and logging

**Grafana "Could not load plugin", connection reset by peer**
- Cause: Grafana pod restarted repeatedly, memory limit (256Mi) was too low (`kubectl top pods` showed 372Mi).
- Fix: raised the limit to 768Mi in `monitoring/prometheus/values.yaml` and ran `helm upgrade`.

**Kibana data view: "no timestamp field"**
- Cause: Filebeat was connected but no document had been indexed yet.
- Fix: sent traffic to the website, checked `_count` in Elasticsearch, then created the data view.

## Ansible

**Task "Install common packages" failed: Failed to update apt cache**
- Cause: an old HashiCorp apt repository without a public key (NO_PUBKEY) made the cache refresh fail.
- Fix: removed the repository file (Terraform is installed on Windows anyway), refreshed the cache with `apt-get update` in a separate task.

## Lessons learned

- Verify every stop/start of paid resources.
- Never type IDs by hand, copy them.
- Check the current branch before every commit.
- Check `.gitignore` before the first commit that contains state or secrets.
- Confirm what is merged into `develop` before debugging Jenkins.
