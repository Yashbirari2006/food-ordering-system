
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = "food-ordering-local-key"


def get_db():
    return mysql.connector.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="yash",
        database="food_ordering_db"
    )


@app.route("/", methods=["GET", "POST"])
def home():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["customer_name"].strip()
        food_id = int(request.form["food_id"])
        quantity = int(request.form["quantity"])

        if name and 1 <= quantity <= 100:
            cursor.execute(
                "INSERT INTO orders (customer_name, food_id, quantity) "
                "VALUES (%s, %s, %s)",
                (name, food_id, quantity)
            )
            db.commit()
            flash("Order saved successfully in MySQL!")
        else:
            flash("Please enter valid order details.")

        cursor.close()
        db.close()
        return redirect(url_for("home"))

    cursor.execute("SELECT * FROM food_items ORDER BY food_id")
    foods = cursor.fetchall()

    cursor.execute("""
        SELECT o.order_id, o.customer_name, f.food_name,
               o.quantity, f.price * o.quantity AS total
        FROM orders o
        JOIN food_items f ON o.food_id = f.food_id
        ORDER BY o.order_id DESC
    """)
    orders = cursor.fetchall()

    cursor.close()
    db.close()
    return render_template("index.html", foods=foods, orders=orders)


@app.route("/delete/<int:order_id>", methods=["POST"])
def delete_order(order_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM orders WHERE order_id = %s",
        (order_id,)
    )
    db.commit()
    cursor.close()
    db.close()

    flash("Order deleted successfully.")
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
