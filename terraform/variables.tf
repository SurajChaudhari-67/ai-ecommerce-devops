variable "subscription_id" {
  type        = string
  description = "Azure subscription ID"
}

variable "location" {
  type    = string
  default = "indiasouthcentral"
}

variable "project" {
  type    = string
  default = "nexvion"
}
variable "aks_vm_size" {
  type    = string
  default = "Standard_B2s_v2"
}

variable "aks_node_count" {
  type    = number
  default = 2
}