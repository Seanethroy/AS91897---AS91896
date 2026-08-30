from flask import Flask, flash, redirect, render_template, request, url_for
import json
import os
from datetime import datetime


app = Flask(__name__)
app.secret_key = "osc_burger_practice_key"


# File locations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PRODUCT_FILE = os.path.join(DATA_DIR, "products.json")
ORDER_FILE = os.path.join(DATA_DIR, "orders.json")


# Business rules
DELIVERY_FEE = 3.00
BULK_DISCOUNT_THRESHOLD = 5
BULK_DISCOUNT_RATE = 0.10
MAX_TOTAL_ITEMS = 10


def load_json(filename, default):
    """Load JSON data from a file."""
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(filename, data):
    """Save data to a JSON file."""
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def load_products():
    """Return the burger products."""
    return load_json(PRODUCT_FILE, {})


def load_orders():
    """Return all saved orders."""
    return load_json(ORDER_FILE, [])


def save_orders(orders):
    """Save all orders."""
    save_json(ORDER_FILE, orders)


def validate_name(name):
    """Check that the customer name is valid."""
    if not name:
        return False, "Please enter your name."

    if len(name) > 50:
        return False, "Name must be 50 characters or fewer."

    return True, ""


def validate_phone(phone):
    """Check that a phone number has a valid number of digits."""
    digits = "".join(
        character for character in phone
        if character.isdigit()
    )

    return 7 <= len(digits) <= 15


def build_cart(products, form_data):
    """Create a cart from submitted quantity fields."""
    cart = {}

    for product_name in products:
        field_name = f"quantity_{product_name}"
        quantity_text = form_data.get(
            field_name,
            "0"
        ).strip()

        if not quantity_text:
            quantity_text = "0"

        try:
            quantity = int(quantity_text)
        except ValueError:
            message = (
                f"Please enter a whole number for "
                f"{product_name}."
            )
            return None, message

        if quantity < 0:
            message = (
                f"Quantity for {product_name} "
                "cannot be negative."
            )
            return None, message

        if quantity > 0:
            cart[product_name] = quantity

    return cart, ""


def validate_cart(cart, products):
    """Check quantities, stock and maximum order size."""
    if not cart:
        return False, "Please select at least one burger."

    total_items = sum(cart.values())

    if total_items > MAX_TOTAL_ITEMS:
        message = (
            f"You can order a maximum of "
            f"{MAX_TOTAL_ITEMS} items per order."
        )
        return False, message

    for product_name, quantity in cart.items():

        if product_name not in products:
            return False, "A selected burger is invalid."

        stock = products[product_name]["stock"]

        if quantity > stock:
            message = (
                f"Only {stock} {product_name}(s) "
                "are currently available."
            )
            return False, message

    return True, ""


def calculate_totals(cart, products, delivery):
    """Calculate subtotal, discount and final total."""
    subtotal = 0.0
    total_items = sum(cart.values())

    for product_name, quantity in cart.items():
        price = products[product_name]["price"]
        subtotal += price * quantity

    if total_items >= BULK_DISCOUNT_THRESHOLD:
        discount = subtotal * BULK_DISCOUNT_RATE
    else:
        discount = 0.0

    if delivery:
        delivery_charge = DELIVERY_FEE
    else:
        delivery_charge = 0.0

    total = subtotal - discount + delivery_charge

    return {
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "delivery_charge": round(delivery_charge, 2),
        "total": round(total, 2),
        "total_items": total_items
    }


def get_next_order_id(orders):
    """Return the next available order number."""
    if not orders:
        return 1

    return max(
        order["order_id"]
        for order in orders
    ) + 1


def create_order(
    customer_name,
    cart,
    products,
    delivery,
    address,
    phone
):
    """Create and save a new order."""
    orders = load_orders()

    totals = calculate_totals(
        cart,
        products,
        delivery
    )

    items = []

    for product_name, quantity in cart.items():

        price = products[product_name]["price"]

        items.append({
            "name": product_name,
            "quantity": quantity,
            "price": price,
            "item_total": round(
                price * quantity,
                2
            )
        })

    order = {
        "order_id": get_next_order_id(orders),
        "customer_name": customer_name,
        "items": items,
        "delivery": delivery,
        "address": address,
        "phone": phone,
        "subtotal": totals["subtotal"],
        "discount": totals["discount"],
        "delivery_charge": totals["delivery_charge"],
        "total": totals["total"],
        "total_items": totals["total_items"],
        "date": datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        ),
        "status": "Active"
    }

    orders.append(order)
    save_orders(orders)

    return order


def update_stock(products, cart, amount):
    """Update product stock using the supplied amount."""
    for product_name, quantity in cart.items():
        products[product_name]["stock"] += (
            amount * quantity
        )

    save_json(PRODUCT_FILE, products)


@app.route("/")
def index():
    """Display the burger menu."""
    products = load_products()

    return render_template(
        "index.html",
        products=products,
        max_items=MAX_TOTAL_ITEMS
    )


@app.route("/order", methods=["POST"])
def place_order():
    """Validate and process a new order."""
    products = load_products()

    customer_name = request.form.get(
        "customer_name",
        ""
    ).strip()

    delivery = request.form.get(
        "delivery",
        "pickup"
    )

    address = request.form.get(
        "address",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    delivery_selected = delivery == "delivery"

    valid, message = validate_name(customer_name)

    if not valid:
        flash(message, "error")
        return redirect(url_for("index"))

    if delivery_selected:

        if not address:
            flash(
                "Please enter a delivery address.",
                "error"
            )
            return redirect(url_for("index"))

        if not validate_phone(phone):
            flash(
                "Please enter a valid phone number.",
                "error"
            )
            return redirect(url_for("index"))

    else:
        address = ""
        phone = ""

    cart, message = build_cart(
        products,
        request.form
    )

    if cart is None:
        flash(message, "error")
        return redirect(url_for("index"))

    valid, message = validate_cart(
        cart,
        products
    )

    if not valid:
        flash(message, "error")
        return redirect(url_for("index"))

    order = create_order(
        customer_name,
        cart,
        products,
        delivery_selected,
        address,
        phone
    )

    update_stock(
        products,
        cart,
        -1
    )

    flash(
        f"Order #{order['order_id']} "
        "created successfully!",
        "success"
    )

    return redirect(
        url_for(
            "receipt",
            order_id=order["order_id"]
        )
    )


@app.route("/receipt/<int:order_id>")
def receipt(order_id):
    """Display an individual order receipt."""
    orders = load_orders()

    order = next(
        (
            item
            for item in orders
            if item["order_id"] == order_id
        ),
        None
    )

    if order is None:
        flash(
            "That order could not be found.",
            "error"
        )
        return redirect(url_for("index"))

    return render_template(
        "receipt.html",
        order=order
    )


@app.route("/orders")
def order_history():
    """Display all saved orders."""
    orders = load_orders()

    return render_template(
        "orders.html",
        orders=orders
    )


@app.route(
    "/cancel/<int:order_id>",
    methods=["POST"]
)
def cancel_order(order_id):
    """Cancel an active order and restore stock."""
    orders = load_orders()

    order = next(
        (
            item
            for item in orders
            if item["order_id"] == order_id
        ),
        None
    )

    if order is None:
        flash(
            "That order could not be found.",
            "error"
        )
        return redirect(url_for("order_history"))

    if order["status"] == "Cancelled":
        flash(
            "This order has already been cancelled.",
            "error"
        )
        return redirect(url_for("order_history"))

    products = load_products()

    cancelled_cart = {
        item["name"]: item["quantity"]
        for item in order["items"]
    }

    update_stock(
        products,
        cancelled_cart,
        1
    )

    order["status"] = "Cancelled"

    save_orders(orders)

    flash(
        f"Order #{order_id} has been cancelled.",
        "success"
    )

    return redirect(url_for("order_history"))


@app.errorhandler(404)
def page_not_found(error):
    """Display a friendly 404 page."""
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)