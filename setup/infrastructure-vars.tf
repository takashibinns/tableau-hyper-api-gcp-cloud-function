
/*  Variables for GCP environment */

variable "region" {
  type    = string
  default = "us-west1"
}
variable "zone" {
  type    = string
  default = "us-west1-a"
}
variable "project_id" {
  type    = string
  default = "gcp-project-id"
}
variable "cloud_bucket_name" {
  type    = string
  default = "gcp-bucket-name"
}


/*  Tableau variables  */
variable "tableau_base_url" {
  type    = string
  default = "https://us-east-1.online.tableau.com/"
}
variable "tableau_site" {
  type    = string
  default = "tableau-site-name"
}
variable "tableau_project_name" {
  type    = string
  default = "destination-project-name"
}
variable "tableau_pat_name" {
  type    = string
  default = "my-pat-name"
}
variable "tableau_pat_value" {
  type    = string
  default = "my-pat-secret"
}

/*  Local variables  */
locals {
  gcp = {
    service_account_key_file = "my-gcp-credentials.json",
    services = [
        "file.googleapis.com",                     //  Requried for Firestore
        "compute.googleapis.com",                   //  
        "cloudresourcemanager.googleapis.com",      //  Required for creating containers
        "cloudfunctions.googleapis.com",            //  Required for creating Cloud Functions
        "cloudbuild.googleapis.com",                //  Required for building containers for Cloud Function
        "cloudscheduler.googleapis.com",            //  Required for creating Cloud Scheduled
        "iap.googleapis.com"                        //  Required for setting IAM policies
    ],
    cron_schedule = "0 1 * * *"                     // Everyday at 1am
  }
  names = {
    solution = "firestore-to-tableau"
    code_zip = "cloudfunction.zip"
  }
}