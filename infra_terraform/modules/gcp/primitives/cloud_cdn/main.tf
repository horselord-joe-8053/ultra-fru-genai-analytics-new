# Reference: infra_terraform/modules/aws/primitives/cloudfront/main.tf
# GCP: Cloud CDN + GCS bucket for frontend static assets. Optional API origin (Cloud Run via serverless NEG).

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

# Optional: serverless NEG + backend service for Cloud Run API origin
resource "google_compute_region_network_endpoint_group" "api" {
  count                 = var.cloud_run_service_name != null ? 1 : 0
  name                  = "${var.prefix}-${var.env}-api-neg-${var.suffix}"
  network_endpoint_type = "SERVERLESS"
  region                = var.gcp_region

  cloud_run {
    service = var.cloud_run_service_name
  }
}

resource "google_compute_backend_service" "api" {
  count    = var.cloud_run_service_name != null ? 1 : 0
  name     = "${var.prefix}-${var.env}-api-backend-${var.suffix}"
  protocol = "HTTP"
  # timeout_sec not supported for Serverless NEG (Cloud Run)

  backend {
    group = google_compute_region_network_endpoint_group.api[0].id
  }
}

resource "google_compute_url_map" "frontend" {
  name            = "${var.prefix}-${var.env}-frontend-${var.suffix}"
  default_service = google_compute_backend_bucket.frontend.id

  dynamic "host_rule" {
    for_each = var.cloud_run_service_name != null ? [1] : []
    content {
      hosts        = ["*"]
      path_matcher = "api"
    }
  }

  dynamic "path_matcher" {
    for_each = var.cloud_run_service_name != null ? [1] : []
    content {
      name            = "api"
      default_service = google_compute_backend_bucket.frontend.id

      path_rule {
        paths   = ["/query", "/query/*", "/analytics", "/analytics/*", "/version", "/health"]
        service = google_compute_backend_service.api[0].id
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
