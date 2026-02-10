# Migration Summary & Verification Guide

This project has been migrated from the legacy FRU Analytics project. The "sophisticated logic" (Backend Agents, API, and Frontend) is now integrated into `core-app`.

## Key Changes
- **Unified Container:** `core-app` runs a multi-stage build containing both the React frontend and Flask backend, served via Nginx.
- **Spark Isolation:** Spark jobs are now separated into `core-app/analytics` and run as independent Jobs/CronJobs on EKS.
- **Port Mapping:** The application now listens on port **5001** (via Nginx), which proxies API requests to the Flask app on port 5000.

## Automated Verification
The `orchestrator.py deploy` command now performs:
1. Infrastructure check.
2. Build and Push of migrated images (with correct platform `linux/amd64`).
3. Kubernetes manifest application (including API Deployment and Service).
4. Endpoint health check (via updated `verify_plumbing.py`).

## Manual Verification Hints

### 1. Identify Service URL
Run the following command to get the LoadBalancer hostname:
```bash
kubectl get svc fru-api-svc -n fru -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

### 2. Test API Health
```bash
# Replace <LB_URL> with the hostname from step 1
curl http://<LB_URL>/health
```
*Expected: `{"status": "ok", ...}` (Note: may show database disconnected if DB is not yet provisioned).*

### 3. Access Frontend
Open your browser and navigate to:
`http://<LB_URL>/`

### 4. Check Spark Job Progress
```bash
kubectl get pods -n fru -l job-name=fru-analytics-bootstrap
kubectl logs -l job-name=fru-analytics-bootstrap -n fru
```

## Troubleshooting
- **ImagePullBackOff:** Ensure the EKS nodes have internet access (NAT Gateway) and ECR permissions. Verify the image URI in `.env`.
- **CrashLoopBackOff:** Check logs (`kubectl logs`). Common issues include missing environment variables (`PGPASSWORD`, `OPENAI_API_KEY`) or database connectivity.
- **ResourceNotFound (Logs):** The `verify_plumbing.py` script may fail to find CloudWatch logs if logging agents are not installed in the EKS cluster. This does not mean the deployment failed.
