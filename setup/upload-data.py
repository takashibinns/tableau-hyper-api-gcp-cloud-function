from google.cloud import firestore
from google.oauth2 import service_account
import json
from pathlib import Path
import random, time, datetime

#   Define constants
current_dir = Path(__file__).absolute().parent
sample_data_file = current_dir / 'sample-data.json'
firestore_credentials_file = current_dir / 'my-gcp-credentials.json'
firestore_collection_name = 'cloud_function_data'
date_range = {
    'from': '1/1/2023 1:00 AM',
    'to': '6/6/2023 1:00 PM'
}

#   Business logic
def main():

    #   Read sample data from JSON file
    f = open(sample_data_file)
    data = json.load(f)

    #   Authenticate to Firestore, and get a reference to the given collection
    credentials = service_account.Credentials.from_service_account_file(firestore_credentials_file)
    db = firestore.Client(credentials=credentials)
    collection = db.collection(firestore_collection_name)

    #   Loop through each document, and import to firestore collection
    for doc in data['documents']:

        #   Randomly create a datetime value, for the last_updated field
        last_updated = random_date(date_range['from'], date_range['to'], '%m/%d/%Y %I:%M %p', random.random())
        doc['last_updated'] = last_updated

        #   Write the document to firestore collection
        collection.add(doc)

#   Create a random timestamp
def random_date(start, end, time_format, prop):
    """Get a time at a proportion of a range of two formatted times.

    start and end should be strings specifying times formatted in the
    given format (strftime-style), giving an interval [start, end].
    prop specifies how a proportion of the interval to be taken after
    start.  The returned time will be in the specified format.
    """

    stime = time.mktime(time.strptime(start, time_format))
    etime = time.mktime(time.strptime(end, time_format))

    ptime = stime + prop * (etime - stime)

    #return time.strftime(time_format, time.localtime(ptime))
    return datetime.datetime.fromtimestamp(ptime)

#   Execute function
main()