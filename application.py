import os
import sqlite3

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, send_msg

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded переконайтесь, що шаблони автоматично перезагружаються
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
filepath = os.path.dirname(__file__)
db_path = os.path.join(filepath, 'finance.db')
db = SQL(f"sqlite:///{db_path}")


@app.route("/")
@login_required
def index():

    rows_users = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
    cash = rows_users[0]["cash"]
    user_id = session["user_id"]
    session_list = []

    sqlite_connection = sqlite3.connect('finance.db')
    cursor = sqlite_connection.cursor()
    user_history_cursor = cursor.execute("SELECT symbol, SUM(quantity) from history WHERE user_id=:user_id GROUP BY symbol", {'user_id' : session["user_id"]})

    # symbol, quantity, price, sum, total, cash, total+cash
    total = 0

    for one in user_history_cursor:
        symbol = one[0]
        quantity = one[1]
        quoted = lookup(symbol)
        price = quoted["price"]
        sum_sum = price*quantity
        total = sum_sum + total
        session_list.append({
            'symbol' : symbol,
            'quantity' : quantity,
            'price' : price,
            'sum': sum_sum
        })

    return render_template("index.html", session_list = session_list ,cash=cash, total=total, balance=total+cash )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        try:
            int(request.form.get("shares"))
        except(ValueError):
            return apology("shares doesn't positive int", 400)

        symbol = request.form.get("symbol") #тe, що з форми
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("you didn't provide symbol", 400)

        elif lookup(symbol) is None:
            return apology("you didn't provide symbol", 400)

        elif not shares:
            return apology("you didn't provide number", 400)

        elif shares < 0:
            return apology("you didn't provide positive number", 400)



        rows = db.execute("SELECT * FROM users WHERE id = :id",
                          id=session["user_id"])

        cash = rows[0]["cash"]
        quoted = lookup(symbol) # результат значень які повернула функція лукап
        total_sum = quoted["price"]*shares
        new_cash = cash - quoted["price"]*shares
        if new_cash<0:
            return apology("you have not enough money", 400)

        db.execute(("INSERT INTO history(user_id, symbol, quantity, price,total_sum, new_cash) VALUES(:user_id,:symbol,:quantity,:price,:total_sum, :new_cash)"), user_id=session["user_id"], symbol=symbol, quantity=request.form.get("shares"),price=quoted["price"], total_sum=total_sum, new_cash=new_cash)

        db.execute (("UPDATE users SET cash = :new_cash WHERE id = :user_id"), new_cash=new_cash, user_id=session["user_id"])

        return redirect("/history")


    return render_template("buy.html")




@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    username = request.args.get("username")
    if len(username) <= 1:
        return jsonify(False)

    sqlite_connection = sqlite3.connect('finance.db')
    cursor = sqlite_connection.cursor()
    username_history = cursor.execute("SELECT username FROM users WHERE username = :username", {'username' : username})

    for one in username_history:
        if username == one[0]:
            return jsonify(False)

    return jsonify(True)


@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    history_dict = []

    sqlite_connection = sqlite3.connect('finance.db')
    cursor = sqlite_connection.cursor()
    user_history_cursor = cursor.execute("SELECT symbol, quantity, price, date, total_sum, new_cash  from history WHERE user_id=:user_id", {'user_id' : session["user_id"]})

    for one in user_history_cursor:
        symbol = one[0]
        quantity = one[1]
        price = usd(one[2])
        date = one[3]
        total_sum = usd(one[4])
        new_cash = usd(one[5])
        history_dict.append({
            'symbol' : symbol,
            'quantity' : quantity,
            'price' : price,
            'date': date,
            'total_sum': total_sum,
            'new_cash': new_cash
        })

    return render_template("history.html", history_dict = history_dict)


@app.route("/login", methods=["GET", "POST"])
def login():

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            return apology("must provide username", 403)


        elif not password:
            return apology("must provide password", 403)


        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        try:
            symbol = request.form.get("symbol")
            quote = lookup(symbol)
            return render_template("quoted.html", name=quote["name"], price=quote["price"], symbol=quote["symbol"] )

        except(TypeError):
            return apology("symbol doesn't exists", 400)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation", 400)

        username = request.form.get("username")
        password_1 = request.form.get("password")
        password_2 = request.form.get("confirmation")
        if password_1 != password_2:
            return apology("password no match", 400)

        hash = generate_password_hash(password_1)

        try:
            db.execute(("INSERT INTO users(username, hash) VALUES (%s, %s)"), username, hash)
        except Exception as e:
            send_msg(repr(e))
            return apology("username exists", 400)

        return redirect("/login")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    user_id = session["user_id"]
    rows_users = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)
    cash = rows_users[0]["cash"]
    session_list = []
    symbol_list = []
    quantity_s = {}

    sqlite_connection = sqlite3.connect('finance.db')
    cursor = sqlite_connection.cursor()
    user_history_cursor = cursor.execute("SELECT symbol, SUM(quantity) from history WHERE user_id=:user_id GROUP BY symbol", {'user_id' : session["user_id"]})

    # symbol, quantity, price, sum, total, cash, total+cash
    total = 0
    quantity = 0
    new_cash = 0
    new_quantity = 0

    for one in user_history_cursor:
        symbol = one[0]
        quantity_y = one[1]
        symbol_list.append(symbol)
        quantity_s[symbol] = quantity_y
    if request.method == "POST":
        request_symbol = request.form.get("symbol")
        request_shares = request.form.get("shares")

        if request_symbol not in symbol_list:
            return apology("symbol doesn't exists", 400)
        if not request_symbol:
            return apology("must provide symbol", 400)

        quantity = quantity_s[request_symbol]
        if int(request_shares) > quantity:
            return apology("tooo much quantity", 400)
        quoted = lookup(request_symbol)
        price = quoted["price"]
        total_sum = price*int(request_shares)
        new_cash = cash + price*int(request_shares)


        db.execute (("UPDATE users SET cash = :new_cash WHERE id = :user_id"), new_cash=new_cash, user_id=user_id)
        db.execute(("INSERT INTO history(user_id, symbol, quantity, price, total_sum, new_cash) VALUES(:user_id,:symbol,:quantity,:price, :total_sum, :new_cash)"),
            user_id=user_id,
            symbol=request_symbol,
            quantity=0-int(request_shares),
            price=price,
            total_sum=total_sum,
            new_cash=new_cash)
        return redirect ("/history")
    return render_template("sell.html", symbol_list = symbol_list)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
