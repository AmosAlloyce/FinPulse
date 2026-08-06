locals {
  name = "${var.project_name}-${var.environment}"
}

module "data_platform" {
  source = "./modules/data_platform"

  name                      = local.name
  environment               = var.environment
  aws_region                = var.aws_region
  vpc_id                    = var.vpc_id
  private_subnet_ids        = var.private_subnet_ids
  data_security_group_ids   = var.data_security_group_ids
  redshift_base_capacity    = var.redshift_base_capacity
  alert_email               = var.alert_email
}

