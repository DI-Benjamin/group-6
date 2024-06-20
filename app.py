from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from secrets import *
import bcrypt, datetime, requests, json, boto3

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:mhdqny5muz8NDT3gjv@65.109.63.215:2010/pretendifydb'
db = SQLAlchemy(app)
app.secret_key = 'secret_key'

# Initialize the boto3 client
ecs_client = boto3.client('ecs', region_name=AWS_REGION,
                          aws_access_key_id=AWS_ACCESS_KEY,
                          aws_secret_access_key=AWS_SECRET_KEY)

types = ["module_1"]

def request_infrastructure(type_n, email, name):
    request_payload = {
        "input": json.dumps({
            "type": types[type_n],
            "email": email,
            "name": name
        }),
        "name": name,
        "stateMachineArn": STATE_MACHINE_ARN
    }
    api_gateway_url = API_GATEWAY_URL
    response = requests.post(api_gateway_url, json=request_payload)
    print("Response:", response.status_code, response.text)
    return


# Database tables
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(16), unique=True)
    users = db.relationship('User', backref='user')

    def __init__(self, email, phone, name):
        self.name = name
        self.email = email
        self.phone = phone

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    IsAdmin = db.Column(db.Boolean, default=False)
    company = db.Column(db.Integer, db.ForeignKey(Company.id))

    def __init__(self, email, password, name, company):
        self.name = name
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.company = company

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

class Deployments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Integer)
    company = db.Column(db.Integer, db.ForeignKey(Company.id))
    user = db.Column(db.Integer, db.ForeignKey(User.id))

    def __init__(self, name, type, company, user):
        self.name = name
        self.type = type
        self.company = company
        self.user = user

with app.app_context():
    db.create_all()

@app.route("/", methods=['GET', 'POST'])
def home():
    if 'id' in session:
        if request.method == 'POST':
            name = request.form["name"]
            type = int(request.form["type"])
            new_deployment = Deployments(name=name, type=type, user=session['id'],
                                         company=session['company'])
            db.session.add(new_deployment)
            db.session.commit()
            request_infrastructure(type, session['email'], name)
            return redirect(url_for("list_clusters"))
    else:
        return redirect(url_for("login"))
    return render_template('index.html')

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/delete/<id>")
def delete(id):
    to_delete = Deployments.query.filter_by(id=id).first()
    if to_delete:
        db.session.delete(to_delete)
        db.session.commit()
    return redirect(url_for("status"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session['id'] = user.id
            session['company'] = user.company
            session['email'] = user.email
            return redirect(url_for("home"))
        else:
            return render_template('login.html', error='Invalid user')
    return render_template('login.html')

@app.route('/admin/add/user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        company = int(request.form['company'])

        new_user = User(name=name, email=email, password=password, company=company)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("home"))
    companies = Company.query.all()
    return render_template('register.html', companies=companies)

@app.route('/admin/add/company', methods=['GET', 'POST'])
def add_company():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        new_company = Company(name=name, email=email, phone=phone)
        db.session.add(new_company)
        db.session.commit()
        return redirect(url_for("home"))

    return render_template('company.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route("/logout")
def logout():
    session.pop('id')
    session.pop('company')
    session.pop('email')
    return redirect(url_for("login"))

@app.route("/list-clusters", methods=['GET'])
def list_clusters():
    if 'id' in session:
        try:
            clusters_response = ecs_client.list_clusters()
            cluster_arns = clusters_response.get('clusterArns', [])
            return render_template('clusters.html', clusters=cluster_arns)
        except Exception as e:
            return render_template('error.html', message="An error occurred: {}".format(e))
    else:
        return redirect(url_for("login"))

if __name__ == '__main__':
    app.run(debug=True)
