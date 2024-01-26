import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, date
from re import search

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    list = db.execute(
        "SELECT userid, symbol ,name, quantity FROM holdings WHERE userid=?",
        session["user_id"],
    )
    cashq = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
    grandTotal = cashq[0]["cash"]
    total = {}
    current_price = {}
    for j in list:
        total = lookup(j["symbol"])["price"] * int(j["quantity"])
        current_price = lookup(j["symbol"])["price"]
        grandTotal = grandTotal + total
    return render_template(
        "index.html",
        grandTotal=grandTotal,
        list=list,
        cash=cashq[0]["cash"],
        total=total,
        current_price=current_price,
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        user_balance = db.execute(
            "SELECT cash FROM users WHERE id=?", session["user_id"]
        )

        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if symbol == None:
            return apology("Please provide symbol, try again!!")

        if lookup(symbol) == None:
            return apology("Invalid Symbol!!")

        if shares is None or not shares.isdigit() or int(shares) <= 0:
            return apology("Select valid number of shares")

        if user_balance[0]["cash"] < (lookup(symbol)["price"] * int(shares)):
            return apology("Insufficient funds")

        day = date.today()
        d = day.strftime("%d/%m/%Y")

        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")

        amount = lookup(symbol)["price"] * int(shares)

        trade = db.execute(
            "INSERT INTO transactions (userid, date, time, symbol, name, price, quantity, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            session["user_id"],
            d,
            current_time,
            symbol,
            lookup(symbol)["name"],
            lookup(symbol)["price"],
            shares,
            amount,
        )

        check = db.execute(
            "SELECT symbol FROM holdings WHERE symbol=? AND userid=?",
            symbol,
            session["user_id"],
        )

        update = db.execute(
            "UPDATE users SET cash=? WHERE id=? ",
            user_balance[0]["cash"] - amount,
            session["user_id"],
        )

        if len(check) >= 1:
            quantity = db.execute(
                "SELECT quantity FROM holdings WHERE userid=? AND symbol=? ",
                session["user_id"],
                symbol,
            )

            update_holdings = db.execute(
                "UPDATE holdings SET quantity=? WHERE symbol=? AND userid=?",
                int(quantity[0]["quantity"]) + int(shares),
                symbol,
                session["user_id"],
            )
        else:
            update_holdings = db.execute(
                "INSERT INTO holdings (userid, symbol, name, quantity) VALUES (?, ?, ?, ?)",
                session["user_id"],
                symbol,
                lookup(symbol)["name"],
                shares,
            )

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    list = db.execute(
        "SELECT * FROM transactions WHERE userid=? ORDER BY id DESC",
        session["user_id"],
    )
    return render_template("history.html", list=list)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
        symbol = request.form.get("symbol")
        if lookup(symbol) == None:
            return apology("Invalid Symbol!!")
        else:
            response = lookup(symbol)
            msg = (
                response["name"]
                + " ("
                + response["symbol"]
                + ") cost is $"
                + "{:.2f}".format(response["price"])
                + "."
            )
            return render_template("quoted.html", message=msg)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        if not password:
            return apology("must provide password", 400)

        # Ensure confirm password was submitted:
        if not confirmation:
            return apology("must provide confirm password", 400)

        if password != confirmation:
            return apology("password and confirm-password doesn't match", 400)

        if len(password) < 8:
            msg = "Make sure your password is at lest 8 letters"
            return render_template("register.html", message=msg)
        elif search('[0-9]', password) is None:
            msg = "Make sure your password has a number in it"
            return render_template("register.html", message=msg)
        elif search('[A-Z]', password) is None:
            msg = "Make sure your password has a capital letter in it"
            return render_template("register.html", message=msg)

        hash_password = generate_password_hash(password)

        try:
            new_user = db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)",
                request.form.get("username"),
                hash_password,
            )
        except:
            return apology("Username already exists")
        session["user_id"] = new_user

        # Redirect user to home page
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        quantity = db.execute(
            "SELECT quantity FROM holdings WHERE userid=? AND symbol=?",
            session["user_id"],
            symbol,
        )
        capital = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])

        if symbol == None:
            return apology("Select Stock")

        if lookup(symbol) == None:
            return apology("Don't own shares of this stock")

        if shares is None or not shares.isdigit() or int(shares) <= 0:
            return apology("Select valid number of shares")

        if int(shares) > quantity[0]["quantity"]:
            return apology("Not enough shares")

        day = date.today()
        d = day.strftime("%d/%m/%Y")

        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")

        amount = lookup(symbol)["price"] * int(request.form.get("shares"))

        trade = db.execute(
            "INSERT INTO transactions (userid, date, time, symbol, name, price, quantity, total) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            session["user_id"],
            d,
            current_time,
            symbol,
            lookup(symbol)["name"],
            lookup(symbol)["price"],
            -(int(shares)),
            amount,
        )
        user = db.execute(
            "UPDATE users SET cash=? WHERE id=? ",
            capital[0]["cash"] + amount,
            session["user_id"],
        )
        holding = db.execute(
            "UPDATE holdings SET quantity=? WHERE userid=? AND symbol=?",
            int(quantity[0]["quantity"]) - int(request.form.get("shares")),
            session["user_id"],
            symbol,
        )

        return redirect("/")
    else:
        list = db.execute(
            "SELECT symbol,quantity FROM holdings WHERE userid=?", session["user_id"]
        )
        return render_template("sell.html", list=list)
