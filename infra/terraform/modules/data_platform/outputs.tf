output "lakehouse_bucket" { value = aws_s3_bucket.lakehouse.id }
output "msk_bootstrap_brokers" { value = aws_msk_serverless_cluster.events.bootstrap_brokers_sasl_iam }
output "redshift_endpoint" { value = aws_redshiftserverless_workgroup.warehouse.endpoint[0].address }
output "feature_store_table" { value = aws_dynamodb_table.online_features.name }
output "emr_serverless_application_id" { value = aws_emrserverless_application.spark.id }
output "emr_serverless_execution_role_arn" { value = aws_iam_role.emr_serverless.arn }
output "alert_topic_arn" { value = aws_sns_topic.alerts.arn }

