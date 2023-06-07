# Tableau + GCP: Push data from Cloud Function to Tableau
This project shows an example of how a GCP Cloud Function can take data (from a Firestore collection in this example), and push it to Tableau Cloud/Server.  It leverages Tableau Hyper API to create a data extract file, and then uses Tableau's REST APIs to publish that Hyper file as a [published data source](https://help.tableau.com/current/pro/desktop/en-us/publish_datasources_about.htm).  This Cloud Function can be triggered by a Cloud Schedule to automate the process of pushing data.  Since we don't want to push the entire data set every time, our code checks to see if the data source exists in Tableau first and if so we only append new datapoints.


##  Deploying this sample
To deploy this example automatically, we can use the terraform code included in the setup directory.  

### Step 0: Prerequisites
In order to deploy this example, we assume you have the following
#### Google Cloud Platform access
This solution uses Cloud Function and Cloud Schedule to take data from Google Firestore and push it to Tableau.  You will need access to the GCP Console, and a [service account](https://cloud.google.com/iam/docs/service-account-overview).  The terraform used in this example (as well as some python code) leverages a key file from a service account in order to authenticate.  This means you will either need a service account or the ability to create a service account with the below permissions:
| Role  | API Name | Reason |
| ------------------------- | ------------- | --- |
| Cloud Datastore User      | roles/datastore.user  | Firestore access  |
| Cloud Functions Admin     | roles/cloudfunctions.admin | Create Cloud Functions |
| Cloud Scheduler Admin     | roles/cloudscheduler.admin | Create Cloud Schedule |
| Create Service Accounts   | roles/iam.serviceAccountCreator | Create service account for Cloud Function invoker |
| Delete Service Accounts   | roles/iam.serviceAccountDeleter | Deleting service account for Cloud Function invoker | 
| Security Admin            | roles/iam.securityAdmin | For assigning IAM policies to service account |
| Service Account User      | roles/iam.serviceAccountUser | Needs the actAs permission |
| Storage Object Admin      | roles/storage.objectAdmin | Writing source code files to Cloud Storage |

#### Tableau Server/Cloud
Since we are publishing/updating a data source in a tableau environment, you will need [credentials](https://help.tableau.com/current/online/en-us/security_personal_access_tokens.htm#create-a-pat) with the ability to publish data sources
#### Terraform
The provisioning of GCP resources is done using terraform.  You can install it from [here](https://developer.hashicorp.com/terraform/tutorials/gcp-get-started/install-cli)
#### Python 3.x
The source code for the Cloud Function as well as some setup code is written in Python 3.  Version 3.11 was used while developing this example, but newer versions should work as well
#### [Hyper API](https://tableau.github.io/hyper-db/docs/installation) & [Tableau Server Client](https://tableau.github.io/server-client-python/docs/#install-with-pip-recommended)
These python modeules are used in the Cloud Function to create a Hyper extract and to publish it to Tableau Server/Cloud.  These modules are only needed if you want to try out the Cloud Function code locally (they get installed automatically, when deploying to Cloud Function)
### Step 1: Configure
Before we can run our terraform script, we need to provide some input variables.  Create a new file at setup/dev.tfvars and use the below sample as a reference:
```
project_id = "your-gcp-project-id"
cloud_bucket_name = "name-of-a-cloud-bucket-in-your-gcp-project"
tableau_site = "devplatembed"
tableau_base_url = "https://us-east-1.online.tableau.com/"
tableau_project_name = "destination-project-name"
tableau_pat_name = "personal-access-token-name"
tableau_pat_value = "personal-access-token-secret"
```
*\*If using the default site of Tableau Server, use an empty string as the ```tableau_site```*

*\*```tableau_base_url``` should be the FQDN for your Tableau environment, and make sure to include the / at the end*
### Step 2: Deploy GCP Resources

Open a terminal window, change into the setup directory, and run the below commands:
```
terraform init
terraform apply -var-file="dev.tfvars"
```
The first command tells terraform to download dependencies required to work with GCP, while the second command will provision all the resources needed by this example.  Notice that we pass in the path to the dev.tfvars file created during the Configure step.  Upon completion, terraform should print out the name of the cloud function as well as the schedule it will run on.

### Step 3: Sample Data
Assuming you want to try out the Cloud Function using some sample data, we need to populate a collection in Firestore so that our Cloud Function will have something to query.  In your terminal window run the below command:
```
python upload-data.py
```
This python code will take each JSON object from setup/sample-data.json and add them as Documents to a collection in Firestore.  Once the python script has completed, you can verify by navigating to the Firestore page in GCP console.  You should now see a new collection in Firestore with 30 documents.


##  Customizing this example
Once you've verified that the sample code works, you may want to use your own data from Firestore (or somewhere else).  You will need to modify *cloud-function/config.py*, which is used to define the structure of your Firestore data.  Depending on the JSON data in Firestore, you may need to add a parser to the ```get_data()``` function in *cloud-function/main.py* to handle things like nested objects/arrays.

##  References
* [Tableau Hyper API](https://tableau.github.io/hyper-db/docs/)
* [Tableau Server Client Documentation](https://tableau.github.io/server-client-python/docs/)
* [GCP Cloud Functions](https://cloud.google.com/functions/docs)
* [Terraform GCP reference](https://registry.terraform.io/providers/hashicorp/google/latest/docs)