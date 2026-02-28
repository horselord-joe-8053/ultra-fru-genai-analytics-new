output "bucket_name" { value = google_storage_bucket.frontend.name }
output "cdn_domain_name" { value = google_compute_global_forwarding_rule.frontend.ip_address }
output "url_map_name" { value = google_compute_url_map.frontend.name }
