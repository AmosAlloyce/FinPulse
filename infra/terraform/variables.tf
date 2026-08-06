variable "project_name" {
  description = "Resource name prefix."
  type        = string
  default     = "finpulse"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod"
  }
}

variable "aws_region" {
  description = "AWS region for the data platform."
  type        = string
  default     = "af-south-1"
}

variable "vpc_id" {
  description = "Existing VPC for private data services."
  type        = string
}

variable "private_subnet_ids" {
  description = "At least two private subnets in distinct availability zones."
  type        = list(string)
  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "Provide at least two private subnet IDs."
  }
}

variable "data_security_group_ids" {
  description = "Security groups allowing approved application-to-data traffic."
  type        = list(string)
}

variable "redshift_base_capacity" {
  description = "Redshift Serverless RPUs."
  type        = number
  default     = 8
}

variable "alert_email" {
  description = "Optional platform alert subscription email."
  type        = string
  default     = ""
}

