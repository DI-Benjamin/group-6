from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import bcrypt, requests, json, boto3
from dotenv import load_dotenv
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
import os

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
db = SQLAlchemy(app)
app.secret_key = os.getenv('SECRET_KEY')

admin = Admin()
admin.init_app(app)

# Initialize the boto3 client
ecs_client = boto3.client(
    'ecs',
    region_name=os.getenv('AWS_REGION'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('AWS_SECRET_KEY')
)

types = ["module_1"]

def request_infrastructure(type_n, email, name):
    request_payload = {
        "input": json.dumps({
            "type": types[type_n],
            "email": email,
            "name": name
        }),
        "name": name,
        "stateMachineArn": os.getenv('STATE_MACHINE_ARN')
    }
    api_gateway_url = os.getenv('API_GATEWAY_URL')
    response = requests.post(api_gateway_url, json=request_payload)
    print("Response:", response.status_code, response.text)
    return

# Database tables
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    IsAdmin = db.Column(db.Boolean, default=False)

    def __init__(self, email, password, name):
        self.name = name
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

class Deployments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.Integer)
    user = db.Column(db.Integer, db.ForeignKey(User.id))

    def __init__(self, name, type, user):
        self.name = name
        self.type = type
        self.user = user

admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Deployments, db.session))

with app.app_context():
    db.create_all()

@app.route("/", methods=['GET', 'POST'])
def home():
    return render_template('index.html')

@app.route("/deploy", methods=['GET', 'POST'])
def deploy():
    if 'id' in session:
        if request.method == 'POST':
            name = request.form["name"]
            type = int(request.form["type"])
            new_deployment = Deployments(name=name, type=type, user=session['id'])
            db.session.add(new_deployment)
            db.session.commit()
            request_infrastructure(type, session['email'], name)
            return redirect(url_for("list_clusters"))
    else:
        return redirect(url_for("login"))
    return render_template('deploy.html')

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
            session['email'] = user.email
            session['admin'] = user.IsAdmin
            return redirect(url_for("home"))
        else:
            return render_template('login.html', error='Invalid user')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        new_user = User(name=name, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template('register.html')

@app.route("/logout")
def logout():
    session.pop('id')
    session.pop('email')
    session.pop('admin')
    return redirect(url_for("home"))

@app.route("/list-clusters", methods=['GET'])
def list_clusters():
    if 'id' in session:
        try:
            clusters_response = ecs_client.list_clusters()
            cluster_arns = clusters_response.get('clusterArns', [])
            return render_template('clusters.html', clusters=cluster_arns)
        except Exception as e:
            return redirect(url_for("home"))
    else:
        return redirect(url_for("login"))

if __name__ == '__main__':
    app.run(debug=True)
