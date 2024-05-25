from flask import Flask, render_template, request, redirect, url_for ,session, jsonify
from flask_sqlalchemy import SQLAlchemy
import bcrypt, datetime, requests, json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:mhdqny5muz8NDT3gjv@65.109.63.215:2010/pretendifydb'
db = SQLAlchemy(app)
app.secret_key = 'secret_key'

tiers = ["t2.micro","t2.small","t2.medium","t2.large","t2.xlarge"]
regions = ["eu-central-1","eu-west-1","eu-west-2","eu-west-3","eu-north-1"]
types = ["module_1","module_2"]

def request_infrastructure(github,region,type_n,tier,email,name):
    request = {
        "github" : github,
        "region" : regions[region],
        "type" : types[type_n],
        "tier" : tiers[tier],
        "email" : email,
        "name" : name
    }
    data = json.dumps(request, indent = 4)
    print(data)
    api_gateway_url = 'https://adl6r3xk3m.execute-api.eu-central-1.amazonaws.com/prod/infrastructure'
    response = requests.post(api_gateway_url, json=data)
    print(jsonify(response.json()))
    return


#Database tables
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(16), unique=True)
    users = db.relationship('User', backref='user')

    def __init__(self,email,phone,name):
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

    def __init__(self,email,password,name,company):
        self.name = name
        self.email = email
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        self.company = company
    
    def check_password(self,password):
        return bcrypt.checkpw(password.encode('utf-8'),self.password.encode('utf-8'))

    
class Deployments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    github = db.Column(db.String(100), unique=True)
    type = db.Column(db.Integer)
    tier = db.Column(db.Integer)
    company = db.Column(db.Integer, db.ForeignKey(Company.id))
    user = db.Column(db.Integer, db.ForeignKey(User.id))

    def __init__(self,name,github,type,tier,company,user):
        self.name = name
        self.github = github
        self.type = type
        self.tier = tier
        self.company = company
        self.user = user
    
class Tickets(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Integer, nullable=False)
    content = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Boolean, default=False)
    submission_time = db.Column(db.DateTime, default=datetime.datetime.now)
    resolved_time = db.Column(db.DateTime, nullable=True)
    company = db.Column(db.Integer, db.ForeignKey(Company.id))
    user = db.Column(db.Integer, db.ForeignKey(User.id))
    resolved_by = db.Column(db.Integer, db.ForeignKey(User.id), nullable=True)

def __init__(self,type,content,company,user):
        self.type = type
        self.content = content
        self.company = company
        self.user = user

with app.app_context():
    db.create_all()

@app.route("/", methods=['GET', 'POST'])
def home():
    if 'id' in session:
        if request.method == 'POST':
            name = request.form["name"]
            tier = int(request.form["tier"])
            link = request.form["link"]
            type = int(request.form["type"])
            region = int(request.form["region"])
            new_deployment = Deployments(name=name,github=link,type=type,tier=tier,user=session['id'],company=session['company'])
            db.session.add(new_deployment)
            db.session.commit()
            request_infrastructure(link,region,type,tier,session['email'],name)
            return redirect(url_for("status"))
    else:
        return redirect(url_for("login"))
    return render_template('index.html')

@app.route("/help", methods=['GET', 'POST'])
def help():
    if 'id' in session:
        if request.method == 'POST':
            content = request.form["content"]
            type = int(request.form["type"])
            new_ticket = Tickets(type=type,content=content,company=session['company'],user=session['id'])
            db.session.add(new_ticket)
            db.session.commit()
            return redirect(url_for("status"))
    else:
        return redirect(url_for("login"))
    return render_template('service.html')

@app.route("/status")
def status():
    if 'id' in session:
        deployments = Deployments.query.filter_by(user=session['id'])
        return render_template("status.html",deployments=deployments)
    else:
        return redirect(url_for("login"))

@app.route("/admin/status")
def all_status():
    deployments = Deployments.query
    return render_template("status.html",deployments=deployments)

@app.route("/admin/tickets")
def all_tickets():
    tickets = Tickets.query
    return render_template("tickets.html",tickets=tickets.reverse())

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
    

@app.route('/login',methods=['GET','POST'])
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
            return render_template('login.html',error='Invalid user')
    return render_template('login.html')

@app.route('/admin/add/user',methods=['GET','POST'])
def add_user():
    if request.method == 'POST':
        # handle request
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        company = int(request.form['company'])

        new_user = User(name=name,email=email,password=password,company=company)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("home"))
    companies = Company.query.all()
    print(companies)
    return render_template('register.html',companies=companies)

@app.route('/admin/add/company',methods=['GET','POST'])
def add_company():
    if request.method == 'POST':
        # handle request
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        new_company = Company(name=name,email=email,phone=phone)
        print(name)
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

if __name__ == '__main__':
    app.run(debug=True)