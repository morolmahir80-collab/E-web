import os, uuid
from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Product, ProductImage, CartItem, Order, OrderItem

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png','jpg','jpeg'}

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "secret123"
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

@app.before_first_request
def create_tables():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", password=generate_password_hash("admin"), is_admin=True)
        db.session.add(admin)
        db.session.commit()

# ---------------- AUTH ----------------
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")

# ---------------- PRODUCTS ----------------
@app.route("/")
def index():
    products = Product.query.all()
    return render_template("index.html", products=products)

@app.route("/product/<int:id>")
def product_detail(id):
    product = Product.query.get(id)
    return render_template("product_detail.html", product=product)

# ---------------- CART ----------------
@app.route("/add/<int:product_id>")
@login_required
def add_to_cart(product_id):
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        item.quantity += 1
    else:
        item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(item)
    db.session.commit()
    return redirect("/cart")

@app.route("/cart")
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    cart_data, total = [], 0
    for item in items:
        product = Product.query.get(item.product_id)
        subtotal = product.price * item.quantity
        total += subtotal
        cart_data.append({"id": item.id, "name": product.name, "price": product.price, "quantity": item.quantity, "subtotal": subtotal})
    return render_template("cart.html", cart=cart_data, total=total)

@app.route("/update/<int:item_id>/<action>")
@login_required
def update_cart(item_id, action):
    item = CartItem.query.get(item_id)
    if action=="increase":
        item.quantity += 1
    elif action=="decrease":
        item.quantity -= 1
        if item.quantity<=0:
            db.session.delete(item)
    db.session.commit()
    return redirect("/cart")

# ---------------- CHECKOUT ----------------
@app.route("/checkout")
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(Product.query.get(i.product_id).price*i.quantity for i in items)
    order = Order(user_id=current_user.id, total=total)
    db.session.add(order)
    db.session.commit()
    for i in items:
        order_item = OrderItem(order_id=order.id, product_id=i.product_id, quantity=i.quantity)
        db.session.add(order_item)
        db.session.delete(i)
    db.session.commit()
    return render_template("checkout.html", total=total)

# ---------------- ADMIN ----------------
@app.route("/admin/products")
@login_required
def admin_products():
    if not current_user.is_admin:
        return redirect("/")
    products = Product.query.all()
    return render_template("admin_products.html", products=products)

@app.route("/add_product", methods=["GET","POST"])
@login_required
def add_product():
    if not current_user.is_admin:
        return redirect("/")
    if request.method=="POST":
        name = request.form["name"]
        price = request.form["price"]
        product = Product(name=name, price=price)
        db.session.add(product)
        db.session.commit()
        files = request.files.getlist("images")
        for file in files:
            if file and allowed_file(file.filename):
                filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                img = ProductImage(product_id=product.id, filename=filename)
                db.session.add(img)
        db.session.commit()
        return redirect("/admin/products")
    return render_template("add_product.html")

# ---------------- RUN ----------------
if __name__=="__main__":
    app.run(debug=True)