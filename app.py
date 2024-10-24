# Custom extension for IBM Watson Assistant which provides a
# REST API around a single database table 
#
# The code demonstrates how a simple REST API can be developed and
# then deployed as serverless app to IBM Cloud Code Engine.
#


import os
import ast
from dotenv import load_dotenv
from apiflask import APIFlask, Schema, HTTPTokenAuth, PaginationSchema, pagination_builder, abort
from apiflask.fields import Integer, String, Boolean, Date, List, Nested
from apiflask.validators import Length, Range
# Database access using SQLAlchemy
from flask_sqlalchemy import SQLAlchemy
from flask import abort, request, jsonify, url_for
import html
from datetime import datetime

# Set how this API should be titled and the current version
API_TITLE='Events API for Watson Assistant'
API_VERSION='1.0.1'

# create the app
app = APIFlask(__name__, title=API_TITLE, version=API_VERSION)

# load .env if present
load_dotenv()

# the secret API key, plus we need a username in that record
API_TOKEN="{{'{0}':'appuser'}}".format(os.getenv('API_TOKEN'))
#convert to dict:
tokens=ast.literal_eval(API_TOKEN)

# database URI
DB2_URI=os.getenv('DB2_URI')
# optional table arguments, e.g., to set another table schema
ENV_TABLE_ARGS=os.getenv('TABLE_ARGS')
TABLE_ARGS=None
if ENV_TABLE_ARGS:
    TABLE_ARGS=ast.literal_eval(ENV_TABLE_ARGS)


# specify a generic SERVERS scheme for OpenAPI to allow both local testing
# and deployment on Code Engine with configuration within Watson Assistant
app.config['SERVERS'] = [
    {
        'description': 'Code Engine deployment',
        'url': 'https://{appname}.{projectid}.{region}.codeengine.appdomain.cloud',
        'variables':
        {
            "appname":
            {
                "default": "myapp",
                "description": "application name"
            },
            "projectid":
            {
                "default": "projectid",
                "description": "the Code Engine project ID"
            },
            "region":
            {
                "default": "us-south",
                "description": "the deployment region, e.g., us-south"
            }
        }
    },
    {
        'description': 'local test',
        'url': 'http://127.0.0.1:{port}',
        'variables':
        {
            'port':
            {
                'default': "5000",
                'description': 'local port to use'
            }
        }
    }
]


# set how we want the authentication API key to be passed
auth=HTTPTokenAuth(scheme='ApiKey', header='API_TOKEN')

# configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI']=DB2_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Initialize SQLAlchemy for our database
db = SQLAlchemy(app)


# sample records to be inserted after table recreation
sample_certs=[
    {
        "employeename":"Patrick Dlamini",
        "certificatetype":"Microsoft",
        "certificatedescription":"Azure fundamentals: AZ-900",
        "certificatelink": "https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/?practice-assessment-type=certification",
        "expirydate":"2024-05-30",
        
    },
  

]


# Schema for table "CERTIFICATIONS"
# Set default schema to "CERTIFICATIONS"
class CertModel(db.Model):
    __tablename__ = 'CERTIFICATIONS'
    __table_args__ = TABLE_ARGS
    id = db.Column('ID',db.Integer, primary_key=True)
    employeename = db.Column('EMPLOYEENAME',db.String(32))
    certificatetype = db.Column('CERTIFICATETYPE',db.String(32))
    certificatedescription = db.Column('CERTIFICATEDESCRIPTION',db.String(50))
    certificatelink = db.Column('CERTIFICATELINK',db.String(1000))
    expirydate = db.Column('EXPIRYDATE', db.Date, nullable=True)
    
    

# the Python output for Certifications
class CertOutSchema(Schema):
    id=Integer()
    employeename = String()
    certificatetype = String()
    certificatedescription = String()
    certificatelink =String()
    expirydate = Date(allow_none=True)
   
    
   

# the Python input for Certifications
class CertInSchema(Schema):
    employeename = String(required=True)
    certificatetype = String(required=True)
    certificatedescription = String(required=True)
    certificatelink =String(required=True)
    expirydate = Date(required=False, allow_none=True)
    
# use with pagination
class CertQuerySchema(Schema):
    page = Integer(load_default=1)
    per_page = Integer(load_default=20, validate=Range(max=300))

class CerttsOutSchema(Schema):
    certs = List(Nested(CertOutSchema))
    pagination = Nested(PaginationSchema)

# register a callback to verify the token
@auth.verify_token  
def verify_token(token):
    if token in tokens:
        return tokens[token]
    else:
        return None

#get records by validity date(no date)
@app.get('/certifications/nodate')
@app.output(CertOutSchema)
@app.auth_required(auth)
@app.input(CertQuerySchema, 'query')
def get_nodate_certs(query):
    """Get certifications
    Retrieve all certification records that do not expire
    """
    
    pagination = CertModel.query.filter(
        CertModel.expirydate.is_(None)
    ).paginate(
        page=query['page'],
        per_page=query['per_page']
    )
    
    certs_data = {
        'certs': pagination.items,
        'pagination': pagination_builder(pagination)
    }

    # Start building the HTML table
    table_html = "<table border='1'><tr><th>Name</th><th>CertificateType</th><th>CertificateDescription</th><th>CertificateLink</th><th>ExpirationDate</th></tr>"

    # Add each valid certification to the table
    for cert in certs_data['certs']:
        table_html += f"<tr><td>{html.escape(cert.employeename)}</td><td>{html.escape(cert.certificatetype)}</td><td>{html.escape(cert.certificatedescription)}</td><td>{html.escape(cert.certificatelink)}</td><td>{html.escape(str(cert.expirydate))}</td></tr>"

    # Close the table
    table_html += "</table>"

    # Store the table in a variable
    valid_certs_table = table_html

    # Return the table as part of a JSON response
    return jsonify({
        "table": valid_certs_table,
        "pagination": certs_data['pagination'],
        "message": "Certification data retrieved successfully"
    })

#get records by validity date (invalid)
@app.get('/certifications/invalid')
@app.output(CertOutSchema)
@app.auth_required(auth)
@app.input(CertQuerySchema, 'query')
def get_invalid_certs(query):
    """Get invalid certifications
    Retrieve all certification records that have expired (expiry date is before or the current date)
    """
    current_date = datetime.now().date()
    
    pagination = CertModel.query.filter(
        CertModel.expirydate < current_date
    ).paginate(
        page=query['page'],
        per_page=query['per_page']
    )
    
    certs_data = {
        'certs': pagination.items,
        'pagination': pagination_builder(pagination)
    }

    # Start building the HTML table
    table_html = "<table border='1'><tr><th>Name</th><th>CertificateType</th><th>CertificateDescription</th><th>CertificateLink</th><th>ExpirationDate</th></tr>"

    # Add each valid certification to the table
    for cert in certs_data['certs']:
        table_html += f"<tr><td>{html.escape(cert.employeename)}</td><td>{html.escape(cert.certificatetype)}</td><td>{html.escape(cert.certificatedescription)}</td><td>{html.escape(cert.certificatelink)}</td><td>{html.escape(str(cert.expirydate))}</td></tr>"

    # Close the table
    table_html += "</table>"

    # Store the table in a variable
    valid_certs_table = table_html

    # Return the table as part of a JSON response
    return jsonify({
        "table": valid_certs_table,
        "pagination": certs_data['pagination'],
        "message": "inValid certification data retrieved successfully"
    })

#get records by validity date
@app.get('/certifications/valid')
@app.output(CertOutSchema)
@app.auth_required(auth)
@app.input(CertQuerySchema, 'query')
def get_valid_certs(query):
    """Get valid certifications
    Retrieve all certification records that have not expired (expiry date is after the current date)
    """
    current_date = datetime.now().date()
    
    pagination = CertModel.query.filter(
        CertModel.expirydate > current_date
    ).paginate(
        page=query['page'],
        per_page=query['per_page']
    )
    
    certs_data = {
        'certs': pagination.items,
        'pagination': pagination_builder(pagination)
    }

    # Start building the HTML table
    table_html = "<table border='1'><tr><th>Name</th><th>CertificateType</th><th>CertificateDescription</th><th>CertificateLink</th><th>ExpirationDate</th></tr>"

    # Add each valid certification to the table
    for cert in certs_data['certs']:
        table_html += f"<tr><td>{html.escape(cert.employeename)}</td><td>{html.escape(cert.certificatetype)}</td><td>{html.escape(cert.certificatedescription)}</td><td>{html.escape(cert.certificatelink)}</td><td>{html.escape(str(cert.expirydate))}</td></tr>"

    # Close the table
    table_html += "</table>"

    # Store the table in a variable
    valid_certs_table = table_html

    # Return the table as part of a JSON response
    return jsonify({
        "table": valid_certs_table,
        "pagination": certs_data['pagination'],
        "message": "Valid certification data retrieved successfully"
    })

#retrieve records with same name 
@app.get('/certifications/name/<string:employeename>')
@app.output(CertOutSchema)
@app.auth_required(auth)
@app.input(CertQuerySchema, 'query')
def get_certs_by_name(employeename, query):
    """Get certifications by name
    Retrieve all certification records with the specified employee name
    """
    pagination = CertModel.query.filter(CertModel.employeename == employeename).paginate(
        page=query['page'],
        per_page=query['per_page']
    )
    def get_page_url(page):
        return url_for('get_certs_by_name', employeename=employeename, page=page, per_page=query['per_page'], _external=True)

    pagination_info = {
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
        'total': pagination.total,
        'current': get_page_url(pagination.page),
        'first': get_page_url(1),
        'last': get_page_url(pagination.pages),
        'prev': get_page_url(pagination.prev_num) if pagination.has_prev else None,
        'next': get_page_url(pagination.next_num) if pagination.has_next else None
    }
    certs_data = {
        'certs': pagination.items,
        'pagination': pagination_info
    }

    # Start building the HTML table
    table_html = "<table border='1'><tr><th>Name</th><th>CertificateType</th><th>CertificateDescription</th><th>CertificateLink</th><th>ExpirationDate</th></tr>"
    
    # Add each certification to the table
    for cert in certs_data['certs']:
        table_html += f"<tr><td>{html.escape(cert.employeename)}</td><td>{html.escape(cert.certificatetype)}</td><td>{html.escape(cert.certificatedescription)}</td><td>{html.escape(cert.certificatelink)}</td><td>{html.escape(str(cert.expirydate))}</td></tr>"
    
    # Close the table
    table_html += "</table>"
    
    # Store the table in a variable
    Certs_table = table_html
    
    # Return the table as part of a JSON response
    return jsonify({
        "table": Certs_table,
        "pagination": certs_data['pagination'],
        "message": "Certification data retrieved successfully"
    })

#retrieve records with a keyword
@app.get('/certifications/keyword/<string:tkeyword>')
@app.output(CertOutSchema)
@app.auth_required(auth)
@app.input(CertQuerySchema, 'query')

def get_certs_by_keyword(tkeyword, query):
    """Get CERTS by KEYWORD
    Retrieve all records with the specified KEYWORD
    """
    pagination = CertModel.query.filter(
        (CertModel.certificatedescription.ilike(f'%{tkeyword}%')) |
        (CertModel.certificatetype.ilike(f'%{tkeyword}%'))
    ).paginate(
        page=query['page'],
        per_page=query['per_page']
    )
    
    def get_page_url(page):
        return url_for('get_certs_by_keyword', tkeyword=tkeyword, page=page, per_page=query['per_page'], _external=True)

    pagination_info = {
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
        'total': pagination.total,
        'current': get_page_url(pagination.page),
        'first': get_page_url(1),
        'last': get_page_url(pagination.pages),
        'prev': get_page_url(pagination.prev_num) if pagination.has_prev else None,
        'next': get_page_url(pagination.next_num) if pagination.has_next else None
    }
    certs_data = {
        'certs': pagination.items,
        'pagination': pagination_info
    }

    # Start building the HTML table
    table_html = "<table border='1'><tr><th>Name</th><th>CertificateType</th><th>CertificateDescription</th><th>CertificateLink</th><th>ExpirationDate</th></tr>"

    # Add each matching certification to the table
    for cert in certs_data['certs']:
        table_html += f"<tr><td>{html.escape(cert.employeename)}</td><td>{html.escape(cert.certificatetype)}</td><td>{html.escape(cert.certificatedescription)}</td><td>{html.escape(cert.certificatelink)}</td><td>{html.escape(str(cert.expirydate))}</td></tr>"

    # Close the table
    table_html += "</table>"

    # Store the table in a variable
    Certs_table = table_html

    # Return the table as part of a JSON response
    return jsonify({
        "table": Certs_table,
        "pagination": certs_data['pagination'],
        "message": "Certification data retrieved successfully by keyword"
    })


#retrieve records with same certificate type 
@app.get('/certifications/certtype/<string:tcerttype>')
@app.output(CertOutSchema)
@app.auth_required(auth)
@app.input(CertQuerySchema, 'query')

def get_certs_by_certtype(tcerttype, query):
    """Get Certifications by type
    Retrieve all records with the specified type
    """
    pagination = CertModel.query.filter(CertModel.certificatetype == tcerttype).paginate(
        page=query['page'],
        per_page=query['per_page']
    )

    
    def get_page_url(page):
        return url_for('get_certs_by_certtype', tcerttype=tcerttype, page=page, per_page=query['per_page'], _external=True)

    pagination_info = {
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
        'total': pagination.total,
        'current': get_page_url(pagination.page),
        'first': get_page_url(1),
        'last': get_page_url(pagination.pages),
        'prev': get_page_url(pagination.prev_num) if pagination.has_prev else None,
        'next': get_page_url(pagination.next_num) if pagination.has_next else None
    }
    certs_data = {
        'certs': pagination.items,
        'pagination': pagination_info
    }

    # Start building the HTML table
    table_html = "<table border='1'><tr><th>Name</th><th>CertificateType</th><th>CertificateDescription</th><th>CertificateLink</th><th>ExpirationDate</th></tr>"
    
    # Add each patient to the table
    for cert in certs_data['certs']:
        table_html += f"<tr><td>{html.escape(cert.employeename)}</td><td>{html.escape(cert.certificatetype)}</td><td>{html.escape(cert.certificatedescription)}</td><td>{html.escape(cert.certificatelink)}</td><td>{html.escape(str(cert.expirydate))}</td></tr>"
    
    # Close the table
    table_html += "</table>"
    
    # Store the table in a variable
    Certs_table = table_html
    
    # Return the table as part of a JSON response
    return jsonify({
        "table": Certs_table,
        "pagination": certs_data['pagination'],
        "message": "Certification data retrieved successfully"
    })


# create a record
@app.post('/Certifications')
@app.input(CertInSchema, location='json')
@app.output(CertOutSchema, 201)
@app.auth_required(auth)
def create_record(data):
    """Insert a new record
    Insert a new record with the given attributes. Its new ID is returned.
    """
    cert = CertModel(**data)
    db.session.add(cert)
    db.session.commit()
    return cert


# (re-)create the cert table with sample records
@app.post('/database/recreate')
@app.input({'confirmation': Boolean(load_default=False)}, location='query')
#@app.output({}, 201)
@app.auth_required(auth)
def create_database(query):
    """Recreate the database schema
    Recreate the database schema and insert sample data.
    Request must be confirmed by passing query parameter.
    """
    if query['confirmation'] is True:
        db.drop_all()
        db.create_all()
        for e in sample_certs:
            cert = CertModel(**e)
            db.session.add(cert)
        db.session.commit()
    else:
        abort(400, message='confirmation is missing',
            detail={"error":"check the API for how to confirm"})
        return {"message": "error: confirmation is missing"}
    return {"message":"database recreated"}


# default "homepage", also needed for health check by Code Engine
@app.get('/')
def print_default():
    """ Greeting
    health check
    """
    # returning a dict equals to use jsonify()
    return {'message': 'This is the certifications API server'}


# Start the actual app
# Get the PORT from environment or use the default
port = os.getenv('PORT', '5000')
if __name__ == "__main__":
    app.run(host='0.0.0.0',port=int(port))
