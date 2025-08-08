from flask import Flask, request,render_template,session,redirect,url_for,flash,jsonify
from flask_session import Session
from flask_cors import CORS
import mysql.connector
import bcrypt
import os,datetime,qrcode,base64
from io import BytesIO
from datetime import date, timedelta
app = Flask(__name__, static_folder='static')
CORS(app)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
app.secret_key = os.urandom(24)
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="mysql@Marg27",
    database="virtual_bus_pass_system"
)
cursor = db.cursor()
admin_id = "ADM/3030/22"
full_name = "Principal"
email = "principal@gmail.com"
password = "principal" 
role = "Super Admin"
hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
cursor.execute("SELECT admin_id FROM admins WHERE admin_id = %s", (admin_id,))
existing_admin = cursor.fetchone()
if not existing_admin:
    query = "INSERT INTO admins (admin_id, full_name, email, password, role) VALUES (%s, %s, %s, %s, %s)"
    values = (admin_id, full_name, email, hashed_password, role)
    try:
        cursor.execute(query, values)
        db.commit()
        print("Super Admin added successfully!")
    except mysql.connector.Error as e:
        print(f"Error inserting Super Admin: {e}")
else:
    print("Super Admin already exists, skipping insertion.")

# Function to Generate QR Code and Convert to Base64
def generate_qr_code(register_number, pass_type, issue_date, expiry_date):
    qr_data = f"Register Number: {register_number}\nPass Type: {pass_type}\nIssue Date: {issue_date}\nExpiry Date: {expiry_date}"
    
    qr = qrcode.make(qr_data)
    buffered = BytesIO()
    qr.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return qr_base64  # ✅ Returns Base64-encoded QR Code

@app.route('/generate_bus_pass', methods=['POST'])
def generate_bus_pass():
    if "user" not in session:
        return jsonify({"success": False, "error": "Session expired. Please log in again."}), 403

    try:
        register_number = session["user"]
        pass_type = session["student_type"]
        issue_date = date.today()

        # Determine expiry_date based on pass type
        if pass_type == "Day Scholar":
            expiry_date = issue_date + timedelta(days=90 if session.get("duration") == "3" else 180)
        else:  # Hosteller
            reach_date = session.get("reach_date")
            expiry_date = datetime.datetime.strptime(reach_date, "%Y-%m-%d").date() if reach_date else issue_date

        # Generate QR Code
        qr_code = generate_qr_code(register_number, pass_type, issue_date, expiry_date)

        # Insert into `bus_passes` table
        cursor.execute("""
            INSERT INTO bus_passes (register_number, pass_type, issue_date, expiry_date, qr_code)
            VALUES (%s, %s, %s, %s, %s)
        """, (register_number, pass_type, issue_date, expiry_date, qr_code))
        db.commit()

        # Store QR Code in session for frontend display
        session["qr_code"] = qr_code

        return jsonify({"success": True, "qr_code": qr_code})

    except mysql.connector.Error as e:
        db.rollback()
        return jsonify({"success": False, "error": f"Database error: {e}"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/payment')
def payment():
    if "user" not in session:
        return redirect(url_for("login"))
    
    # ✅ Fetch the QR code from the database
    cursor.execute("SELECT qr_code FROM bus_passes WHERE register_number = %s", (session["user"],))
    qr_result = cursor.fetchone()
    qr_code = qr_result[0] if qr_result else ""

    session["qr_code"] = qr_code  # ✅ Store in session
    payment_details = {
        "full_name": session.get("full_name"),
        "email": session.get("email"),
        "student_type": session.get("student_type"),
        "bus_name": session.get("bus_name"),
        "drop_off": session.get("drop_off"),
        "reach_date": session.get("reach_date"),
        "total_amount": session.get("total_amount"),
        "qr_code": qr_code,  # ✅ Pass QR code
    }

    return render_template("payment.html", payment_details=payment_details)


@app.route('/verify_qr_code', methods=['POST'])
def verify_qr_code():
    if 'role' not in session or session['role'] not in ['Security', 'Super Admin', 'Moderator']:
        return redirect(url_for('login'))

    qr_code_raw = request.json.get('qr_data')
    if not qr_code_raw:
        flash('Invalid QR Code!', 'error')
        return redirect(url_for('security_dashboard'))

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM bus_passes 
            WHERE qr_code = %s 
              AND status = 'Active' 
              AND expiry_date >= CURDATE()
        """, (qr_code_raw,))
        count = cursor.fetchone()[0]

        if count > 0:
            flash(' QR Code Verified Successfully!', 'success')
        else:
            flash('Invalid or Expired QR Code!', 'error')

        cursor.close()
    except Exception as e:
        app.logger.error(f"QR Code Verification Error: {e}")
        flash('An error occurred during verification.', 'error')

    return redirect(url_for('security_dashboard'))

def insert_user(register_number, full_name, email, password,student_type):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    if register_number.startswith("STU"):
        table = "students"
    elif register_number.startswith("ADM"):
        table = "admins"
    elif register_number.startswith("SEC"):
        table = "security"
    else:
        return "Invalid register number format!!"

    query = f"INSERT INTO {table} (register_number, full_name, email, password,student_type) VALUES (%s, %s, %s, %s,%s)"
    values = (register_number, full_name, email, hashed_password,student_type)
    
    try:
        cursor.execute(query, values)
        db.commit()
        return f"User registered in {table} table"
    except mysql.connector.Error as e:
        return str(e)


@app.route('/newuser', methods=['GET'])
def newuser():
    return render_template("newuser.html")
@app.route('/register',methods=['POST'])
def register():
        register_no = request.form.get("regno")
        full_name = request.form.get("fullname")
        email = request.form.get("email")
        student_type = request.form.get("sttype")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        print(f"Received: {register_no}, {full_name}, {email},{student_type},{password},{confirm_password}")

        if not all([register_no, full_name, email, password,confirm_password,student_type]):
            print("Error: Missing fields")
            return render_template("newuser.html", error="All fields are required!!")
        if password!=confirm_password:
            return render_template("newuser.html", error="Passwords do not match!!")

        result = insert_user(register_no, full_name, email, password,student_type)
        print(f"DB Response: {result}") 

        if "User registered" in result:
            return render_template("register.html", message=result)
        else:
            return render_template("newuser.html",error=result)

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("login route called!!")
    print(f"Request Args: {request.args}")

    # ✅ Preserve role from URL parameter
    role = request.args.get("role", "student")
    print(f"Role: {role}")

    if request.method == "POST":
        register_number = request.form.get("register_number")
        password = request.form.get("password")
        print(f"Register Number: {repr(register_number)}")
        print(f"Password: {repr(password)}")

        if not register_number or not password:
            return render_template("login.html", error="All fields are required", role=role)

        # ✅ Admin login check based on role
        if role == "admin" and register_number.startswith("ADM"):
            table = "admins"
            query = "SELECT password, role FROM admins WHERE admin_id = %s"
        elif role == "student" and register_number.startswith("STU"):
            table = "students"
            query = "SELECT password, student_type, status FROM students WHERE register_number = %s"
        elif role == "security" and register_number.startswith("SEC"):
            table = "security"
            query = "SELECT password FROM security WHERE register_number = %s"
        else:
            return render_template("login.html", error="Invalid registration number format!!", role=role)

        cursor.execute(query, (register_number,))
        result = cursor.fetchone()

        if result is None:
            return render_template("login.html", error="User not found", role=role)

        hashed_password = result[0]
        extra_field = result[1] if len(result) > 1 else None

        if bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
            session["user"] = register_number

            # ✅ Handle student and admin login routing
            if table == "students":
                student_type, status = extra_field, result[2]
                if status.lower() != "enabled":
                    return render_template("login.html", error="Access Denied! Contact Admins.", role=role)

                if student_type == "Day Scholar":
                    return redirect(url_for("dayscholar"))
                elif student_type == "Hosteller":
                    return redirect(url_for("hosteller"))

            elif table == "admins":
                admin_role = extra_field
                session["admin_role"] = admin_role
                if admin_role == "Super Admin":
                    return redirect(url_for("superadmin"))
                elif admin_role == "Moderator":
                    return redirect(url_for("moderator"))

            elif table == "security":
                return redirect(url_for("security_dashboard"))
        else:
            return render_template("login.html", error="Invalid password!", role=role)

    return render_template("login.html", role=role)

# Route: Proceed to Payment (Dayscholar)
@app.route('/proceed_to_payment_dayscholar', methods=['POST'])
def proceed_to_payment_dayscholar():
    if "user" not in session:
        return redirect(url_for("login"))

    register_number = session["user"]
    cursor.execute("SELECT full_name, email FROM students WHERE register_number = %s", (register_number,))
    student = cursor.fetchone()

    if not student:
        flash("Student details not found.", "error")
        return redirect(url_for("dayscholar"))

    full_name, email = student

    selected_destination = request.form.get("destination")
    selected_drop_off_index = request.form.get("drop_off_location")
    selected_duration = request.form.get("duration")

    if not selected_destination or not selected_drop_off_index or not selected_duration:
        flash("Please select all required options.", "error")
        return redirect(url_for("dayscholar"))

    cursor.execute("SELECT drop_off_locations, fare_per_day FROM bus_info WHERE bus_destination = %s", (selected_destination,))
    fare_info = cursor.fetchone()

    if not fare_info:
        flash("Fare details not found.", "error")
        return redirect(url_for("dayscholar"))

    drop_off_locations = [loc.strip() for loc in fare_info[0].strip('{}').split(',')]
    fare_per_day = [int(f.strip()) for f in fare_info[1].strip('{}').split(',')]

    try:
        drop_off_index = int(selected_drop_off_index)
        drop_off_name = drop_off_locations[drop_off_index]
        total_fare = fare_per_day[drop_off_index] * (90 if selected_duration == "3" else 180)
    except (ValueError, IndexError):
        flash("Invalid drop-off selection.", "error")
        return redirect(url_for("dayscholar"))

    session["full_name"] = full_name
    session["email"] = email
    session["bus_name"] = selected_destination
    session["drop_off"] = drop_off_name
    session["total_amount"] = total_fare

    return redirect(url_for("payment"))


@app.route('/moderator')
def moderator():
    if "user" not in session or session.get("admin_role") != "Moderator":
        return redirect(url_for("login"))
    return render_template("moderator.html",student=None)

@app.route('/add_moderator', methods=['POST'])
def add_moderator():
    if "user" not in session or session.get("admin_role") != "Super Admin":
        return redirect(url_for("login"))
    admin_id = request.form.get("admin_id")
    full_name = request.form.get("full_name")
    email = request.form.get("email")
    password = request.form.get("password")
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        query = "INSERT INTO admins (admin_id, full_name, email, password, role) VALUES (%s, %s, %s, %s, 'Moderator')"
        cursor.execute(query, (admin_id, full_name, email, hashed_password))
        db.commit()
        flash("Moderator added successfully!", "success")
    except mysql.connector.Error as e:
        flash(f"Error adding moderator: {e}", "error")
    return redirect(url_for("superadmin"))
@app.route('/delete_moderator', methods=['POST'])
def delete_moderator():
    if "user" not in session or session.get("admin_role") != "Super Admin":
        return redirect(url_for("login"))

    admin_id = request.form.get("admin_id")

    try:
        cursor.execute("SELECT * FROM admins WHERE admin_id = %s AND role = 'Moderator'", (admin_id,))
        moderator = cursor.fetchone()

        if not moderator:
            flash("Error: Moderator not found!", "error")
        else:
            cursor.execute("DELETE FROM admins WHERE admin_id = %s", (admin_id,))
            db.commit()
            flash("Moderator deleted successfully!", "success")
            return redirect(url_for("superadmin"))
    except mysql.connector.Error as e:
        flash(f"Error deleting moderator: {e}", "error")
    return redirect(url_for("superadmin"))

@app.route('/view_student', methods=['POST'])
def view_student():
    if "user" not in session or session.get("admin_role") != "Moderator":
        return redirect(url_for("login"))

    register_number = request.form.get("register_number")

    try:
        cursor.execute("SELECT register_number, full_name, email, status FROM students WHERE register_number = %s", (register_number,))
        student = cursor.fetchone()

        if not student:
            flash("Error: Student not found!", "error")
            return redirect(url_for("moderator"))

    except mysql.connector.Error as e:
        flash(f"Error retrieving student: {e}", "error")
        return redirect(url_for("moderator"))

    return render_template("moderator.html", student=student)
@app.route('/update_student_status', methods=['POST'])
def update_student_status():
    if "user" not in session or session.get("admin_role") != "Moderator":
        return redirect(url_for("login"))

    register_number = request.form.get("register_number")
    status = request.form.get("status")

    try:
        cursor.execute("SELECT * FROM students WHERE register_number = %s", (register_number,))
        student = cursor.fetchone()

        if not student:
            flash("Error: Student not found!", "error")
        else:
            new_status = "Enabled" if status == "Enable" else "Disabled"
            cursor.execute("UPDATE students SET status = %s WHERE register_number = %s", (new_status, register_number))
            db.commit()
            flash(f"Student account {status}d successfully!", "success")

    except mysql.connector.Error as e:
        flash(f"Error updating student status: {e}", "error")

    return redirect(url_for("moderator"))

@app.route('/superadmin')
def superadmin():
    if "user" not in session or "admin_role" not in session:
        return redirect(url_for("login"))
    cursor.execute("SELECT admin_id, full_name, email, role FROM admins")
    admins = cursor.fetchall()
    return render_template("superadmin.html", admins=admins)

@app.route('/security_dashboard')
def security_dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("security_dashboard.html")

@app.route('/dayscholar')
def dayscholar():
    if "user" not in session:
        return redirect(url_for("login"))
    try:
        cursor.execute("SELECT bus_destination, drop_off_locations, fare_per_day FROM bus_info")
        buses = cursor.fetchall()
        bus_data = {}
        for destination, locations, fares in buses:
            locations_list = locations.strip('{}').split(',')
            fares_list = [int(f) for f in fares.strip('{}').split(',')]
            bus_data[destination] = {
                "locations": locations_list,
                "fares": fares_list
            }
        return render_template("dayscholar.html", bus_data=bus_data)
    except mysql.connector.Error as e:
        flash(f"Error retrieving bus information: {e}", "error")
        return render_template("dayscholar.html", bus_data={})

@app.route('/get_bus_info')
def get_bus_info():
    if "user" not in session:
        return jsonify({"error": "Unauthorized access"}), 401
    try:
        cursor.execute("SELECT bus_destination, drop_off_locations, fare_per_day FROM bus_info")
        buses = cursor.fetchall()
        bus_data = {}
        for destination, locations, fares in buses:
            # Convert string representations to lists
            locations_list = [loc.strip() for loc in locations.strip('{}').split(',')]
            fares_list = [int(f.strip()) for f in fares.strip('{}').split(',')]
            bus_data[destination] = {
                "locations": locations_list,
                "fares": fares_list
            }
        return jsonify(bus_data)
    except Exception as e:
        app.logger.error(f"Error fetching bus info: {e}")
        return jsonify({"error": str(e)}), 500
    

@app.route('/proceed_to_payment_hosteller', methods=['POST'])
def proceed_to_payment_hosteller():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 403  # ✅ Always return JSON

    selected_bus_id = request.form.get("selected_bus")
    reach_date = request.form.get("reach_date")

    if not selected_bus_id:
        return jsonify({"error": "Bus ID is missing"}), 400  # ✅ Always return JSON
    if not reach_date:
        return jsonify({"error": "Please enter your expected arrival date."}), 400  

    try:
        # Update available seats atomically
        cursor.execute("""
            UPDATE bus_info 
            SET available_seats = available_seats - 1 
            WHERE bus_id = %s AND available_seats > 0
        """, (selected_bus_id,))
        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"error": "No available seats left"}), 409  # ✅ Always return JSON

        # Retrieve updated seat count
        cursor.execute("SELECT available_seats FROM bus_info WHERE bus_id = %s", (selected_bus_id,))
        updated_seats = cursor.fetchone()[0]

        cursor.execute("SELECT bus_destination FROM bus_info WHERE bus_id = %s", (selected_bus_id,))
        bus_info = cursor.fetchone()
        bus_name = bus_info[0] if bus_info else "Unknown"  # ✅ Store bus name

        # ✅ Fetch student details
        register_number = session["user"]
        cursor.execute("SELECT full_name, email, student_type FROM students WHERE register_number = %s", (register_number,))
        student = cursor.fetchone()

        if not student:
            return jsonify({"error": "Student details not found"}), 404  # ✅ Always return JSON

        full_name, email, student_type = student

        # ✅ Store required session data
        session["full_name"] = full_name
        session["email"] = email
        session["student_type"] = student_type
        session["reach_date"] = reach_date
        session["bus_name"] = bus_name 
        session["total_amount"] = 150  # ✅ Fixed amount for hosteller

        return jsonify({
            "updated_seats": updated_seats,
            "message": "Proceeding to payment"
        })  # ✅ Always return JSON

    except mysql.connector.Error as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({"error": f"Database error: {e}"}), 500  # ✅ Always return JSON

    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return jsonify({"error": f"Unexpected error: {e}"}), 500  # ✅ Always return JSON

@app.route('/hosteller')
def hosteller():
    if "user" not in session:
        return redirect(url_for("login"))
    try:
        cursor.execute("SELECT bus_id, bus_destination, total_seats, available_seats FROM bus_info")
        buses = cursor.fetchall()
    except mysql.connector.Error as e:
        flash(f"Error retrieving bus information: {e}", "error")
        buses = []
    return render_template("hosteller.html", buses=buses)

@app.route('/security_qr_scanner')
def security_qr_scanner():
    return render_template("security_qr_scanner.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
@app.route('/')
def home():
    return render_template('index.html')
if __name__ == '__main__':
    app.run(debug=True,port=8000)
