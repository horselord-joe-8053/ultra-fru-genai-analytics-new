# Reference: infra_terraform/modules/aws/primitives/aurora/main.tf
# GCP Cloud SQL PostgreSQL (Aurora equivalent)

resource "google_sql_database_instance" "main" {
  name             = var.instance_name
  database_version = "POSTGRES_15"
  region           = var.region
  root_password    = var.root_password

  deletion_protection = var.deletion_protection

  settings {
    tier = var.tier

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
  }
}

resource "google_sql_database" "db" {
  name     = var.database_name
  instance = google_sql_database_instance.main.name
}
