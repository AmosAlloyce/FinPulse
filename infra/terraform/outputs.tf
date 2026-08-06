output "lakehouse_bucket" {
  value = module.data_platform.lakehouse_bucket
}

output "msk_bootstrap_brokers" {
  value     = module.data_platform.msk_bootstrap_brokers
  sensitive = true
}

output "redshift_endpoint" {
  value = module.data_platform.redshift_endpoint
}

output "feature_store_table" {
  value = module.data_platform.feature_store_table
}

output "emr_serverless_application_id" {
  value = module.data_platform.emr_serverless_application_id
}

