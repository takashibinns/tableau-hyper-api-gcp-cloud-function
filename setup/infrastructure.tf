/********************************/
/*  Define the provider: GCP    */
/********************************/

//  Set the required provider for terraform
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google-beta"
      version = "4.58.0"
    }
  }
}

//  Init the provider, using a JSON file with GCP credentials/details
provider "google" {
  credentials = file(local.gcp.service_account_key_file)
  project     = var.project_id
  region      = var.region
  zone        = var.zone
}

//  Enable all GCP service APIs
resource "google_project_service" "services" {
  for_each                      = toset(local.gcp.services)
  project                       = var.project_id
  service                       = each.value
  disable_dependent_services    = false
  disable_on_destroy            = false
}

/********************************/
/*  Create a service account    */
/********************************/

# Create service account to invoke the Cloud Function
resource "google_service_account" "firestore_to_tableau" {
  account_id   = "cloud-function-invoker"
  display_name = "This account invokes the Cloud Function for ${local.names.solution}"
}
# Allow access to query Firestore, for the service account
resource "google_project_iam_member" "firestore_to_tableau" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.firestore_to_tableau.email}"
}
# Allow the service account to invoke the cloud function
resource "google_cloudfunctions_function_iam_member" "firestore_to_tableau_serviceaccount" {
  project        = google_cloudfunctions_function.firestore_to_tableau.project
  region         = google_cloudfunctions_function.firestore_to_tableau.region
  cloud_function = google_cloudfunctions_function.firestore_to_tableau.name
  role   = "roles/cloudfunctions.invoker"
  member = "serviceAccount:${google_service_account.firestore_to_tableau.email}"
}
# Allow all users to invoke the cloud function
resource "google_cloudfunctions_function_iam_member" "firestore_to_tableau_allusers" {
  project        = google_cloudfunctions_function.firestore_to_tableau.project
  region         = google_cloudfunctions_function.firestore_to_tableau.region
  cloud_function = google_cloudfunctions_function.firestore_to_tableau.name
  role   = "roles/cloudfunctions.invoker"
  member = "allUsers"
}

/********************************/
/*  Create the Cloud Function   */
/********************************/

//  Create zip file from source code (run every time, to ensure all changes are incorporated)
resource "null_resource" "zip_code_for_cloud_function" {
  triggers = {
    always_run = "${timestamp()}"
  }
  provisioner "local-exec" {
    working_dir = "${path.module}"
    command = <<EOT
      cd ../cloud-function
      zip -r ${local.names.code_zip} * -x "*.vscode*"
      mv ${local.names.code_zip} ../setup/${local.names.code_zip}
    EOT
  }
}

//  Upload the zipped source code to the bucket
resource "google_storage_bucket_object" "firestore_to_tableau" {
  name   = local.names.code_zip
  bucket = var.cloud_bucket_name
  source = local.names.code_zip
  depends_on = [
    null_resource.zip_code_for_cloud_function
  ]
}

//  Create a new cloud function, reference source code from storage bucket
resource "google_cloudfunctions_function" "firestore_to_tableau" {
  name                  = local.names.solution
  description           = "Cloud Function for pushing data from Firestore to Tableau"
  runtime               = "python311"
  available_memory_mb   = 512
  source_archive_bucket = var.cloud_bucket_name
  source_archive_object = google_storage_bucket_object.firestore_to_tableau.name
  entry_point           = "handle_http"
  trigger_http          = true
  service_account_email = google_service_account.firestore_to_tableau.email
  environment_variables = {
    IS_GCP              = "True"
    TABLEAU_SITE        = var.tableau_site
    TABLEAU_BASE_URL    = var.tableau_base_url
    TABLEAU_PROJECT_NAME= var.tableau_project_name
    TABLEAU_PAT_NAME    = var.tableau_pat_name
    TABLEAU_PAT_VALUE   = var.tableau_pat_value
  }
  depends_on = [
    google_project_service.services
  ]
}

/********************************/
/*  Create the Cloud Schedule   */
/********************************/

# Create a schedule to run the export function automatically
resource "google_cloud_scheduler_job" "firestore_to_tableau" {
  name             = local.names.solution
  description      = "Trigger the ${google_cloudfunctions_function.firestore_to_tableau.name} Cloud Function everyday at 1am EST"
  schedule         = local.gcp.cron_schedule
  time_zone        = "America/New_York"
  attempt_deadline = "600s"
  retry_config {
    retry_count = 1
  }
  http_target {
    http_method = "GET"
    uri         = google_cloudfunctions_function.firestore_to_tableau.https_trigger_url
    oidc_token {
      service_account_email = google_service_account.firestore_to_tableau.email
    }
  }
  depends_on = [
    google_project_service.services
  ]
}

/********************************/
/*  Output                      */
/********************************/
output "Status" {
  value = "Cloud Function ${local.names.solution} will run automatically based on the following cron schedule: ${local.gcp.cron_schedule}"
}