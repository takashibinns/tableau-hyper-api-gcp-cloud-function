#   Import dependencies
import tableauserverclient as TSC
from tableauhyperapi import HyperProcess, Connection, Telemetry, CreateMode, TableDefinition, TableName, SqlType, Inserter
import datetime, time, os, uuid
from google.cloud import firestore
from google.oauth2 import service_account
from flask import escape
import functions_framework

#   Import list of firestore tables from config.py
from config import tables

#   Retrieve env variables
running_in_gcp = (os.environ.get('IS_GCP','False') == 'True')
tableau_site = os.environ.get('TABLEAU_SITE','')
tableau_base_url = os.environ.get('TABLEAU_BASE_URL','')
tableau_pat_name = os.environ.get('TABLEAU_PAT_NAME','')
tableau_pat_value = os.environ.get('TABLEAU_PAT_VALUE','')
tableau_project_name = os.environ.get('TABLEAU_PROJECT_NAME','')

#   Constants
hyper_dir = '/tmp/' if running_in_gcp else 'C:\\tmp\\'
hyper_schema = 'Extract'
hyper_keyfield = 'Document ID'
service_account_key_file = 'my-gcp-credentials.json'
default_last_updated_date = datetime.datetime(2020, 1, 1, 0, 0, 0)   # There will never be data prior to this date in our collection
default_time_buffer_min = 15 

#   Helper function to verify we have the proper env variables set
def check_env_vars():
    if tableau_site == '':
        print('No tableau site name provided, will try to authenticate without specifying the site (must be connecting to the Default site of Tableau Server)')
        return { 'status': 'ok', 'details': 'No Tableau site defined'}
    elif tableau_base_url == '':
        return { 'status': 'error', 'details': 'No Tableau URL defined'}
    elif tableau_pat_name == '':
        return { 'status': 'error', 'details': 'No Tableau Personal Access Token name provided'}
    elif tableau_pat_value == '':
        return { 'status': 'error', 'details': 'No Tableau Personal Access Token value provided'}
    elif tableau_project_name == '':
        return { 'status': 'error', 'details': 'No Tableau project specified'}
    elif len(tables) == 0:
        return { 'status': 'error', 'details': 'No collections defined in config.py'}
    else:
        return { 'status': 'ok' }
    
#   Helper function to conver epoch dates to timestamp strings (https://tableau.github.io/hyper-db/docs/sql/datatype/datetime)
def epoch_to_timestamp(epoch):
    try:
        return datetime.datetime.fromtimestamp(epoch)
    except:
        return None

#   Function to fetch the details of a published data source in Tableau
def get_datasource(tableau_auth, server, dn_name, project):

    #   Sign in
    with server.auth.sign_in(tableau_auth):

        #   Define the filter options for our REST API call
        req_option = TSC.RequestOptions()
        req_option.filter.add(
            TSC.Filter(
                TSC.RequestOptions.Field.Name,
                TSC.RequestOptions.Operator.Equals,
                dn_name
            )
        )
        req_option.filter.add(
            TSC.Filter(
                TSC.RequestOptions.Field.ProjectName,
                TSC.RequestOptions.Operator.Equals,
                project
            )
        )

        #   Execute API call to search for datasource with a matching name/project
        datasources, pagination_item = server.datasources.get(req_option)
        print(f"Found {pagination_item.total_available} data sources with name {dn_name} in the {project} project")

        #   Get the first matching data source (since it's returned within an array)
        existing_ds = next(iter(datasources or []),None)

        #   Return the tableau data source, if a match was found
        if existing_ds:
            return existing_ds
        else:
            return None

#   Function to fetch event data
def get_data(collection_name, timestamp_field, date_filter):

    #   Initialize a client for Firestore
    db = None
    if running_in_gcp:
        #   When running in GCP, auth is inherited from the service account of the cloud function
        db = firestore.Client()
    else:
        #   When developing locally, use the service account's key file (json) to authenticate
        credentials = service_account.Credentials.from_service_account_file(service_account_key_file)
        db = firestore.Client(credentials=credentials)
    
    #   Get all documents newer than the date_filter
    print(f'[{collection_name}] Query for all documents where {timestamp_field} > {date_filter}')
    docs_query = db.collection(collection_name).where(timestamp_field,'>',date_filter).stream()

    #   Loop through each document returned
    docs = []
    for doc_result in docs_query:
        #   Convert the document into a python dictionary (json)
        document = doc_result.to_dict()
        #   Append the Document ID
        document[hyper_keyfield] = doc_result.id
        #   Store in the docs array
        docs.append(document)

    #   Return the data
    print(f'[{collection_name}] Data fetch complete, {len(docs)} new documents captured')
    return docs

#   Function to create a hyper extract
def create_hyper_file(data, filepath, table_name, fields):
    print(f'[{table_name}] Creating new hyper file {filepath}')

    #   Begin the hyper process (make sure all logs are written to the output directory)
    process_params = {
        "log_dir": hyper_dir,
        "default_database_version": "2"
    }
    with HyperProcess(Telemetry.SEND_USAGE_DATA_TO_TABLEAU, parameters = process_params) as hyper:
        #   Create a connection
        with Connection(hyper.endpoint, filepath, CreateMode.CREATE_AND_REPLACE) as connection:
            #   Create the schema
            connection.catalog.create_schema(hyper_schema)

            #   Create table definitions for each "column" in our event data
            #def processColumn(field):
            #    return TableDefinition.Column(field['name'],field['type'])
            processColumn = lambda field: TableDefinition.Column(field['name'],field['type'])
            columns = map(processColumn,fields)

            #   Define the table metadata
            data_table = TableDefinition(TableName(hyper_schema,table_name), columns)

            #   Create the table
            connection.catalog.create_table(data_table)

            #   Insert data using the `Inserter` class
            with Inserter(connection, data_table) as inserter:
                #   Loop through each row in our data to add
                for row in data:
                    #   Create placeholder array for this row of data
                    data_row = []

                    #   Loop through each column, and insert the value
                    for field in fields:
                        #   Safely extract the value from the row
                        try:
                            value = row.get(field['name'],None)
                        except:
                            value = None
                        # convert timestamps from Firestore (epochs) to Tableau datetime compatible strings
                        #if field['type'] == SqlType.timestamp():
                        #    value = epoch_to_timestamp(value)
                        data_row.append(value)

                    #   Row is complete, use Inserter's add_row function
                    inserter.add_row(data_row)
                
                #   Add all the rows to the table
                inserter.execute()

    print(f'[{table_name}] Hyper file created successfully.')

#   Function to publish an extract to Tableau Cloud
def publish_hyper(tableau_auth, server, ds_name, proj_name, table_name, hyper_path, existing_ds):

    #   Sign in
    with server.auth.sign_in(tableau_auth):

        #   Do we have the data source's ID?
        if existing_ds:

            #   Data source exists already, just append new data
            print(f"Found existing datasource ({existing_ds.id}) on Tableau Cloud, so just append new data (match on [Document ID])")

            # Create a new random request id. 
            request_id = str(uuid.uuid4())

            # Create one action that inserts from the new table into the existing table.
            # For more details, see https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_how_to_update_data_to_hyper.htm#action-batch-descriptions
            actions = [
                {
                    "action": "upsert",
                    "source-schema": hyper_schema,
                    "source-table": table_name,
                    "target-schema": hyper_schema,
                    "target-table": table_name,
                    "condition": {"op": "eq", "target-col": hyper_keyfield, "source-col": hyper_keyfield}
                }
            ]

            # Start the update job on Server.
            job = server.datasources.update_hyper_data(existing_ds.id, request_id=request_id, actions=actions, payload=hyper_path)
            print(f"Update job posted (ID: {job.id}). Waiting for the job to complete...")

            # Wait for the job to finish.
            job = server.jobs.wait_for_job(job)
            print("Job finished successfully")  

        else :
            # Define publish mode - Overwrite, Append, or CreateNew
            publish_mode = TSC.Server.PublishMode.Overwrite
            
            # Get project_id from project_name
            all_projects, pagination_item = server.projects.get()
            for project in TSC.Pager(server.projects):
                if project.name == proj_name:
                    project_id = project.id
        
            # Create the datasource object with the project_id
            datasource = TSC.DatasourceItem(project_id, name=ds_name)
            
            # Publish datasource
            print(f"Publishing {ds_name} to {proj_name}...")
            datasource = server.datasources.publish(datasource, hyper_path, publish_mode)
            print(f"Datasource published. Datasource ID: {datasource.id}")


#   Main Business Logic
def main():
    start_time = datetime.datetime.now()
    status = ""

    #   Step 0: Do we have everything we need to get started?
    env_status = check_env_vars()
    if env_status['status'] == 'error':
        #   Something is missing, skip everything
        print(env_status['details'])
        return env_status['details']

    #   Step 1: Authenticate to Tableau Cloud
    tableau_auth = TSC.PersonalAccessTokenAuth(tableau_pat_name, tableau_pat_value, tableau_site)
    server = TSC.Server(tableau_base_url, use_server_version=True)

    #   Loop through each table from config.py
    for table in tables:
        tableau_details = table['tableau']
        firestore_details = table['firestore']

        #   Step 2: Determine last update date of data source (use the default date for the firestore query, if no existing tableau data source)
        existing_ds = get_datasource(tableau_auth, server, tableau_details['datasource_name'], tableau_project_name)
        last_updated = existing_ds.updated_at if existing_ds else default_last_updated_date

        #   Step 3: Get the data from Firestore
        data = get_data(firestore_details['collection'], firestore_details['timestamp_field'], last_updated)

        #   Only continue if there is new data
        if len(data) == 0:
            table_status = f"[{firestore_details['collection']}] No new data found, don't bother pushing to Tableau"
            print(table_status)
            status += f'\n{table_status}'
        else:
            #   Step 4: Create a hyper extract (file)
            hyper_fullpath = f"{hyper_dir}{firestore_details['collection']}.hyper"
            create_hyper_file(data, hyper_fullpath, firestore_details['collection'], firestore_details['fields'])

            #   Step 5: Publish the extract to Tableau Cloud
            publish_hyper(tableau_auth, server, tableau_details['datasource_name'], tableau_project_name, firestore_details['collection'], hyper_fullpath, existing_ds)

            table_status = f"[{firestore_details['collection']}] New data found, successfully pushed to Tableau Cloud as {tableau_details['datasource_name']}"
            print(table_status)
            status += f'\n{table_status}'
    
    duration = datetime.datetime.now() - start_time
    status += f'\nProcess complete in {duration.seconds} seconds'
    return status

main()
#   Handle HTTP Request
@functions_framework.http
def handle_http(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    request_json = request.get_json(silent=True)
    request_args = request.args

    status = main()
    return status