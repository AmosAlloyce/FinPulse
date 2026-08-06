variable "name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "data_security_group_ids" { type = list(string) }
variable "redshift_base_capacity" { type = number }
variable "alert_email" { type = string }

