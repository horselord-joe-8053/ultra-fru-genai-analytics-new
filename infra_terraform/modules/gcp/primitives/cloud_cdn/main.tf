# Reference: infra_terraform/modules/aws/primitives/cloudfront/main.tf
# GCP: Cloud CDN + GCS bucket for frontend static assets. Optional API origin:
# - cloud_run_service_name: nonkube (Cloud Run via serverless NEG)
# - api_origin_hostname: kube (GKE LoadBalancer via Internet NEG; hostname or IP)

locals {
  use_cloud_run_api = var.cloud_run_service_name != null
  use_internet_api  = var.api_origin_hostname != null
  use_api           = local.use_cloud_run_api || local.use_internet_api
  # GKE often exposes only IP; INTERNET_IP_PORT accepts IP, INTERNET_FQDN_PORT requires hostname
  api_origin_is_ip  = local.use_internet_api && can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+$", var.api_origin_hostname))
  api_origin_is_fqdn = local.use_internet_api && !local.api_origin_is_ip
  # Single backend service for internet API (stable name) avoids destroy-order issues when switching FQDN<->IP
  api_internet_neg_id = local.api_origin_is_fqdn ? google_compute_global_network_endpoint_group.api_internet_fqdn[0].id : (local.api_origin_is_ip ? google_compute_global_network_endpoint_group.api_internet_ip[0].id : null)
  api_backend_id      = local.use_cloud_run_api ? google_compute_backend_service.api[0].id : (local.use_internet_api ? google_compute_backend_service.api_internet[0].id : null)
}

resource "google_storage_bucket" "frontend" {
  name          = "${var.prefix}-${var.env}-frontend-${var.suffix}-${var.gcp_region}-${var.gcp_project_id}"
  location      = upper(var.gcp_region)
  force_destroy = true

  labels = var.tags
}

resource "google_compute_backend_bucket" "frontend" {
  name        = "${var.prefix}-${var.env}-frontend-${var.suffix}-${replace(var.gcp_region, "-", "")}"
  bucket_name = google_storage_bucket.frontend.name
  enable_cdn  = true

  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 3600
    max_ttl           = 86400
    client_ttl        = 3600
    negative_caching = true
  }
}

# Optional: serverless NEG + backend service for Cloud Run API origin (nonkube)
resource "google_compute_region_network_endpoint_group" "api" {
  count                 = local.use_cloud_run_api ? 1 : 0
  name                  = "${var.prefix}-${var.env}-api-neg-${var.suffix}"
  network_endpoint_type = "SERVERLESS"
  region                = var.gcp_region

  cloud_run {
    service = var.cloud_run_service_name
  }
}

resource "google_compute_backend_service" "api" {
  count   = local.use_cloud_run_api ? 1 : 0
  name    = "${var.prefix}-${var.env}-api-backend-${var.suffix}"
  protocol = "HTTP"
  # timeout_sec not supported for Serverless NEG (Cloud Run)

  backend {
    group = google_compute_region_network_endpoint_group.api[0].id
  }
}

# Optional: Internet NEG + backend service for GKE LoadBalancer API origin (kube)
# GKE may expose hostname or IP only; use INTERNET_FQDN_PORT for hostname, INTERNET_IP_PORT for IP
resource "google_compute_global_network_endpoint_group" "api_internet_fqdn" {
  count                   = local.api_origin_is_fqdn ? 1 : 0
  name                    = "${var.prefix}-${var.env}-api-internet-neg-${var.suffix}"
  network_endpoint_type   = "INTERNET_FQDN_PORT"
  default_port            = 80
}

resource "google_compute_global_network_endpoint" "api_internet_fqdn" {
  count                         = local.api_origin_is_fqdn ? 1 : 0
  global_network_endpoint_group = google_compute_global_network_endpoint_group.api_internet_fqdn[0].name
  fqdn                          = var.api_origin_hostname
  port                          = 80
}

resource "google_compute_global_network_endpoint_group" "api_internet_ip" {
  count                   = local.api_origin_is_ip ? 1 : 0
  name                    = "${var.prefix}-${var.env}-api-internet-ip-neg-${var.suffix}"
  network_endpoint_type   = "INTERNET_IP_PORT"
  default_port            = 80
}

resource "google_compute_global_network_endpoint" "api_internet_ip" {
  count                         = local.api_origin_is_ip ? 1 : 0
  global_network_endpoint_group = google_compute_global_network_endpoint_group.api_internet_ip[0].name
  ip_address                    = var.api_origin_hostname
  port                          = 80
}

# Single backend service (stable name) so url_map can switch FQDN<->IP without destroy-order issues
resource "google_compute_backend_service" "api_internet" {
  count        = local.use_internet_api ? 1 : 0
  name         = "${var.prefix}-${var.env}-api-internet-backend-${var.suffix}"
  protocol     = "HTTP"
  timeout_sec  = 60
  backend {
    group = local.api_internet_neg_id
  }
}

resource "google_compute_url_map" "frontend" {
  name            = "${var.prefix}-${var.env}-frontend-${var.suffix}"
  default_service = google_compute_backend_bucket.frontend.id

  dynamic "host_rule" {
    for_each = local.use_api ? [1] : []
    content {
      hosts        = ["*"]
      path_matcher = "api"
    }
  }

  dynamic "path_matcher" {
    for_each = local.use_api ? [1] : []
    content {
      name            = "api"
      default_service = google_compute_backend_bucket.frontend.id

      path_rule {
        paths   = ["/query", "/query/*", "/analytics", "/analytics/*", "/rawdata", "/rawdata/*", "/version", "/health"]
        service = local.api_backend_id
      }
    }
  }
}

resource "google_compute_target_http_proxy" "frontend" {
  name    = "${var.prefix}-${var.env}-frontend-${var.suffix}"
  url_map = google_compute_url_map.frontend.id
}

resource "google_compute_global_forwarding_rule" "frontend" {
  name       = "${var.prefix}-${var.env}-frontend-${var.suffix}"
  target     = google_compute_target_http_proxy.frontend.id
  port_range = "80"
}
