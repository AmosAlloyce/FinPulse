data "aws_caller_identity" "current" {}

resource "aws_kms_key" "data" {
  description             = "${var.name} data platform encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "data" {
  name          = "alias/${var.name}-data"
  target_key_id = aws_kms_key.data.key_id
}

resource "aws_s3_bucket" "lakehouse" {
  bucket = "${var.name}-lakehouse-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.data.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "lakehouse" {
  bucket                  = aws_s3_bucket.lakehouse.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id
  rule {
    id     = "medallion-retention"
    status = "Enabled"
    filter {}
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}

resource "aws_glue_catalog_database" "lakehouse" {
  name        = replace("${var.name}_lakehouse", "-", "_")
  description = "FinPulse bronze, silver, and gold catalog"
}

resource "aws_msk_serverless_cluster" "events" {
  cluster_name = "${var.name}-events"

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = var.data_security_group_ids
  }
  client_authentication {
    sasl { iam { enabled = true } }
  }
}

resource "aws_dynamodb_table" "online_features" {
  name         = "${var.name}-online-features"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customer_id"
  range_key    = "feature_version"

  attribute {
    name = "customer_id"
    type = "S"
  }
  attribute {
    name = "feature_version"
    type = "S"
  }
  point_in_time_recovery { enabled = true }
  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.data.arn
  }
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}

resource "random_password" "redshift" {
  length  = 32
  special = true
}

resource "aws_secretsmanager_secret" "redshift" {
  name                    = "${var.name}/redshift/admin"
  kms_key_id              = aws_kms_key.data.arn
  recovery_window_in_days = 30
}

resource "aws_secretsmanager_secret_version" "redshift" {
  secret_id = aws_secretsmanager_secret.redshift.id
  secret_string = jsonencode({
    username = "finpulse_admin"
    password = random_password.redshift.result
  })
}

resource "aws_iam_role" "redshift" {
  name = "${var.name}-redshift"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "redshift.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "redshift_lakehouse" {
  role = aws_iam_role.redshift.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.lakehouse.arn, "${aws_s3_bucket.lakehouse.arn}/*"]
      },
      {
        Effect = "Allow"
        Action = ["glue:GetDatabase", "glue:GetDatabases", "glue:GetTable", "glue:GetTables", "glue:GetPartitions"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.data.arn
      }
    ]
  })
}

resource "aws_redshiftserverless_namespace" "warehouse" {
  namespace_name      = replace("${var.name}-warehouse", "_", "-")
  db_name             = "finpulse"
  admin_username      = "finpulse_admin"
  admin_user_password = random_password.redshift.result
  iam_roles           = [aws_iam_role.redshift.arn]
  kms_key_id          = aws_kms_key.data.arn
  log_exports         = ["userlog", "connectionlog", "useractivitylog"]
}

resource "aws_redshiftserverless_workgroup" "warehouse" {
  workgroup_name       = replace("${var.name}-warehouse", "_", "-")
  namespace_name       = aws_redshiftserverless_namespace.warehouse.namespace_name
  base_capacity        = var.redshift_base_capacity
  subnet_ids           = var.private_subnet_ids
  security_group_ids   = var.data_security_group_ids
  publicly_accessible  = false
  enhanced_vpc_routing = true

  config_parameter {
    parameter_key   = "enable_user_activity_logging"
    parameter_value = "true"
  }
}

resource "aws_iam_role" "emr_serverless" {
  name = "${var.name}-emr-serverless"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "emr-serverless.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "emr_serverless" {
  role = aws_iam_role.emr_serverless.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.lakehouse.arn, "${aws_s3_bucket.lakehouse.arn}/*"]
      },
      {
        Effect = "Allow"
        Action = ["glue:GetDatabase", "glue:GetTable", "glue:GetPartitions", "glue:CreatePartition", "glue:UpdatePartition"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.data.arn
      }
    ]
  })
}

resource "aws_emrserverless_application" "spark" {
  name          = "${var.name}-spark"
  release_label = "emr-7.2.0"
  type          = "SPARK"

  auto_start_configuration { enabled = true }
  auto_stop_configuration {
    enabled              = true
    idle_timeout_minutes = 15
  }
  maximum_capacity {
    cpu    = "32 vCPU"
    memory = "128 GB"
    disk   = "500 GB"
  }
  network_configuration {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = var.data_security_group_ids
  }
}

resource "aws_sns_topic" "alerts" {
  name              = "${var.name}-data-platform-alerts"
  kms_master_key_id = aws_kms_key.data.id
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_log_group" "spark" {
  name              = "/aws/finpulse/${var.name}/spark"
  retention_in_days = var.environment == "prod" ? 90 : 14
  kms_key_id        = aws_kms_key.data.arn
}

