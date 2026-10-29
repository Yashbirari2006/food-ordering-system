
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from decimal import Decimal

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


def close_db(db, cursor):
    if cursor is not None:
        cursor.close()
    if db is not None and db.is_connected():
        db.close()


@app.route("/")
def home():
    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT food_id, food_name, price "
            "FROM food_items ORDER BY food_id"
        )
        foods = cursor.fetchall()

        cursor.execute("""
            SELECT o.order_id, o.customer_name, o.food_id,
                   f.food_name, f.price, o.quantity,
                   f.price * o.quantity AS total
            FROM orders o
            JOIN food_items f ON o.food_id = f.food_id
            ORDER BY o.order_id DESC
        """)
        orders = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) AS total_orders FROM orders")
        total_orders = cursor.fetchone()["total_orders"]

        cursor.execute("SELECT COUNT(*) AS total_foods FROM food_items")
        total_foods = cursor.fetchone()["total_foods"]

        cursor.execute("""
            SELECT COALESCE(SUM(f.price * o.quantity), 0) AS revenue
            FROM orders o
            JOIN food_items f ON o.food_id = f.food_id
        """)
        revenue = cursor.fetchone()["revenue"]

        return render_template(
            "index.html",
            foods=foods,
            orders=orders,
            total_orders=total_orders,
            total_foods=total_foods,
            revenue=revenue
        )

    except mysql.connector.Error as error:
        flash(f"Database error: {error}", "error")
        return render_template(
            "index.html",
            foods=[],
            orders=[],
            total_orders=0,
            total_foods=0,
            revenue=Decimal("0.00")
        )

    finally:
        close_db(db, cursor)


@app.route("/place-order", methods=["POST"])
def place_order():
    name = request.form.get("customer_name", "").strip()

    try:
        food_id = int(request.form.get("food_id", "0"))
        quantity = int(request.form.get("quantity", "0"))

        if not name:
            flash("Please enter the customer's name.", "error")
            return redirect(url_for("home"))

        if not 1 <= quantity <= 100:
            flash("Quantity must be between 1 and 100.", "error")
            return redirect(url_for("home"))

        db = get_db()
        cursor = db.cursor()

        # Use the MySQL stored procedure.
        cursor.callproc(
            "sp_place_order",
            (name, food_id, quantity)
        )
        db.commit()

        flash("Order saved successfully in MySQL!", "success")

    except (ValueError, TypeError):
        flash("Please enter a valid food item and quantity.", "error")

    except mysql.connector.Error as error:
        if "db" in locals() and db.is_connected():
            db.rollback()
        flash(f"Could not place order: {error}", "error")

    finally:
        if "db" in locals():
            close_db(db, locals().get("cursor"))

    return redirect(url_for("home"))


@app.route("/update-order/<int:order_id>", methods=["POST"])
def update_order(order_id):
    name = request.form.get("customer_name", "").strip()

    try:
        quantity = int(request.form.get("quantity", "0"))

        if not name:
            flash("Customer name is required.", "error")
            return redirect(url_for("home"))

        if not 1 <= quantity <= 100:
            flash("Quantity must be between 1 and 100.", "error")
            return redirect(url_for("home"))

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            UPDATE orders
            SET customer_name = %s, quantity = %s
            WHERE order_id = %s
        """, (name, quantity, order_id))

        if cursor.rowcount == 0:
            flash("Order not found or no changes were made.", "error")
        else:
            flash("Order updated successfully.", "success")

        db.commit()

    except (ValueError, TypeError):
        flash("Please enter valid order details.", "error")

    except mysql.connector.Error as error:
        if "db" in locals() and db.is_connected():
            db.rollback()
        flash(f"Could not update order: {error}", "error")

    finally:
        if "db" in locals():
            close_db(db, locals().get("cursor"))

    return redirect(url_for("home"))


@app.route("/delete/<int:order_id>", methods=["POST"])
def delete_order(order_id):
    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM orders WHERE order_id = %s",
            (order_id,)
        )
        db.commit()

        if cursor.rowcount:
            flash("Order deleted successfully.", "success")
        else:
            flash("Order not found.", "error")

    except mysql.connector.Error as error:
        if db and db.is_connected():
            db.rollback()
        flash(f"Could not delete order: {error}", "error")

    finally:
        close_db(db, cursor)

    return redirect(url_for("home"))


@app.route("/add-food", methods=["POST"])
def add_food():
    name = request.form.get("food_name", "").strip()

    try:
        price = Decimal(request.form.get("price", "0"))

        if not name or len(name) > 100:
            flash("Enter a food name of up to 100 characters.", "error")
            return redirect(url_for("home"))

        if not price.is_finite() or price <= 0 or price > Decimal("999999.99"):
            flash("Enter a valid positive price.", "error")
            return redirect(url_for("home"))

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO food_items (food_name, price) VALUES (%s, %s)",
            (name, price)
        )
        db.commit()
        flash("Food item added successfully.", "success")

    except (ValueError, TypeError):
        flash("Please enter a valid price.", "error")

    except mysql.connector.Error as error:
        if "db" in locals() and db.is_connected():
            db.rollback()
        flash(f"Could not add food item: {error}", "error")

    finally:
        if "db" in locals():
            close_db(db, locals().get("cursor"))

    return redirect(url_for("home"))


@app.route("/delete-food/<int:food_id>", methods=["POST"])
def delete_food(food_id):
    db = None
    cursor = None

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM food_items WHERE food_id = %s",
            (food_id,)
        )
        db.commit()

        if cursor.rowcount:
            flash("Food item deleted successfully.", "success")
        else:
            flash("Food item not found.", "error")

    except mysql.connector.IntegrityError:
        flash(
            "This food item is used by existing orders. "
            "Delete those orders before removing the food item.",
            "error"
        )

    except mysql.connector.Error as error:
        if db and db.is_connected():
            db.rollback()
        flash(f"Could not delete food item: {error}", "error")

    finally:
        close_db(db, cursor)

    return redirect(url_for("home"))


@app.route("/reports")
def reports():
    db = None
    cursor = None
    report_rows = []
    report_error = None

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Run the cursor-based MySQL stored procedure.
        cursor.callproc("sp_order_report")

        for result in cursor.stored_results():
            report_rows = result.fetchall()

        cursor.execute("""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(f.price * o.quantity), 0) AS revenue,
                COALESCE(AVG(f.price * o.quantity), 0) AS average_order
            FROM orders o
            JOIN food_items f ON o.food_id = f.food_id
        """)
        summary = cursor.fetchone()

        cursor.execute("""
            SELECT food_name, price
            FROM food_items
            WHERE price > (SELECT AVG(price) FROM food_items)
            ORDER BY price DESC
        """)
        above_average_foods = cursor.fetchall()

        return render_template(
            "reports.html",
            report_rows=report_rows,
            summary=summary,
            above_average_foods=above_average_foods
        )

    except mysql.connector.Error as error:
        report_error = str(error)
        return render_template(
            "reports.html",
            report_rows=[],
            summary={
                "total_orders": 0,
                "revenue": 0,
                "average_order": 0
            },
            above_average_foods=[],
            report_error=report_error
        )

    finally:
        close_db(db, cursor)


if __name__ == "__main__":
    app.run(debug=True)
