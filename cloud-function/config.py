from tableauhyperapi import SqlType

#   Define a list of tables to collect data from, and push to Tableau
tables = [
    {
        'firestore': {
            'collection': 'cloud_function_data',
            'timestamp_field': 'last_updated',
            'fields': [
                { 'name': 'Document ID',        'type': SqlType.text()      },
                { 'name': 'brand',              'type': SqlType.text()      },
                { 'name': 'category',           'type': SqlType.text()      },
                { 'name': 'description',        'type': SqlType.text()      },
                { 'name': 'discountPercentage', 'type': SqlType.double()   },
                { 'name': 'last_updated',       'type': SqlType.timestamp() },
                { 'name': 'price',              'type': SqlType.double()   },
                { 'name': 'productId',          'type': SqlType.int()       },
                { 'name': 'rating',             'type': SqlType.double()   },
                { 'name': 'stock',              'type': SqlType.int()       },
                { 'name': 'title',              'type': SqlType.text()      },
            ]
        },
        'tableau': {
            'datasource_name': 'Cloud Function Data'
        }
    }
]