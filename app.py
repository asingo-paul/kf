from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
# Secret key
app.secret_key = os.getenv("SECRET_KEY")

# MySQL configurations
app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD")
app.config['MYSQL_DB'] = os.getenv("MYSQL_DB")
app.config['MYSQL_CURSORCLASS'] = os.getenv("MYSQL_CURSORCLASS")

mysql = MySQL(app)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND is_active = TRUE", (username,))
        user = cur.fetchone()
        cur.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = f"{user['first_name']} {user['last_name']}"
            session['role'] = user['role']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        first_name = request.form['firstName']
        last_name = request.form['lastName']
        email = request.form['email']
        phone = request.form['phone']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirmPassword']
        security_question = request.form['securityQuestion']
        security_answer = request.form['securityAnswer']
        role = request.form['userRole']
        organization = request.form.get('organization', '')
        
        # Validate passwords match
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        # Check if username or email already exists
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
        existing_user = cur.fetchone()
        
        if existing_user:
            flash('Username or email already exists', 'danger')
            cur.close()
            return render_template('register.html')
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Insert new user
        try:
            cur.execute("""
                INSERT INTO users (first_name, last_name, email, phone, username, password_hash, 
                security_question, security_answer, role, organization)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, email, phone, username, hashed_password, 
                 security_question, security_answer, role, organization))
            
            mysql.connection.commit()
            flash('Registration successful! Please log in.', 'success')
            cur.close()
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            flash('Registration failed. Please try again.', 'danger')
            cur.close()
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    cur = mysql.connection.cursor()
    
    # Get total beneficiaries
    cur.execute("SELECT COUNT(*) as count FROM beneficiaries WHERE status = 'active'")
    beneficiaries = cur.fetchone()['count']
    
    # Get total funds
    cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM funds")
    total_funds = cur.fetchone()['total']
    
    # Get total expenditures
    cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM expenses")
    total_expenditures = cur.fetchone()['total']
    
    # Get recent distributions
    cur.execute("""
        SELECT d.distribution_date, d.location, d.beneficiary_count, 
               GROUP_CONCAT(CONCAT(fi.name, ' (', di.quantity, ' ', fi.unit, ')') SEPARATOR ', ') as food_items
        FROM distributions d
        LEFT JOIN distribution_items di ON d.id = di.distribution_id
        LEFT JOIN food_items fi ON di.food_item_id = fi.id
        GROUP BY d.id
        ORDER BY d.distribution_date DESC
        LIMIT 5
    """)
    recent_distributions = cur.fetchall()
    
    cur.close()
    
    return render_template('dashboard.html', 
                         beneficiaries=beneficiaries,
                         total_funds=total_funds,
                         total_expenditures=total_expenditures,
                         recent_distributions=recent_distributions)

@app.route('/beneficiaries')
@login_required
def beneficiaries():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT b.*, 
               CONCAT(b.first_name, ' ', b.last_name) as full_name,
               u.first_name as registered_by_first, u.last_name as registered_by_last
        FROM beneficiaries b
        LEFT JOIN users u ON b.registered_by = u.id
        ORDER BY b.created_at DESC
    """)
    beneficiaries_list = cur.fetchall()
    cur.close()
    
    return render_template('beneficiaries.html', beneficiaries=beneficiaries_list)

@app.route('/add_beneficiary', methods=['POST'])
@login_required
def add_beneficiary():
    if request.method == 'POST':
        first_name = request.form['firstName']
        last_name = request.form['lastName']
        national_id = request.form['nationalId']
        dob = request.form['dob']
        gender = request.form['gender']
        household_size = request.form['householdSize']
        vulnerability = request.form['vulnerability']
        location = request.form['location']
        
        # Generate beneficiary ID
        beneficiary_id = f"B{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO beneficiaries (beneficiary_id, first_name, last_name, national_id, 
                date_of_birth, gender, household_size, vulnerability_level, location, registered_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (beneficiary_id, first_name, last_name, national_id, dob, gender, 
                 household_size, vulnerability, location, session['user_id']))
            
            mysql.connection.commit()
            flash('Beneficiary added successfully!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash('Error adding beneficiary: ' + str(e), 'danger')
        finally:
            cur.close()
        
        return redirect(url_for('beneficiaries'))

@app.route('/funds')
@login_required
def funds():
    cur = mysql.connection.cursor()
    
    # Get funds
    cur.execute("""
        SELECT f.*, d.name as donor_name, u.first_name as recorded_by_first, u.last_name as recorded_by_last
        FROM funds f
        JOIN donors d ON f.donor_id = d.id
        JOIN users u ON f.recorded_by = u.id
        ORDER BY f.received_date DESC
    """)
    funds_list = cur.fetchall()
    
    # Get expenses
    cur.execute("""
        SELECT e.*, ec.name as category_name, u.first_name as recorded_by_first, u.last_name as recorded_by_last
        FROM expenses e
        JOIN expense_categories ec ON e.category_id = ec.id
        JOIN users u ON e.recorded_by = u.id
        ORDER BY e.expense_date DESC
    """)
    expenses_list = cur.fetchall()
    
    # Get total stats
    cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM funds")
    total_funds = cur.fetchone()['total']
    
    cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM expenses")
    total_expenses = cur.fetchone()['total']
    
    remaining_balance = total_funds - total_expenses
    
    cur.close()
    
    return render_template('funds.html', 
                         funds=funds_list, 
                         expenses=expenses_list,
                         total_funds=total_funds,
                         total_expenses=total_expenses,
                         remaining_balance=remaining_balance)

@app.route('/add_fund', methods=['POST'])
@login_required
def add_fund():
    if request.method == 'POST':
        donor_name = request.form['donor']
        amount = request.form['amount']
        received_date = request.form['receivedDate']
        purpose = request.form['purpose']
        reference = request.form['reference']
        notes = request.form.get('notes', '')
        
        cur = mysql.connection.cursor()
        
        try:
            # Check if donor exists, if not create
            cur.execute("SELECT id FROM donors WHERE name = %s", (donor_name,))
            donor = cur.fetchone()
            
            if not donor:
                cur.execute("INSERT INTO donors (name) VALUES (%s)", (donor_name,))
                donor_id = cur.lastrowid
            else:
                donor_id = donor['id']
            
            # Add fund entry
            cur.execute("""
                INSERT INTO funds (reference_number, donor_id, amount, received_date, purpose, notes, recorded_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (reference, donor_id, amount, received_date, purpose, notes, session['user_id']))
            
            mysql.connection.commit()
            flash('Fund entry added successfully!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash('Error adding fund entry: ' + str(e), 'danger')
        finally:
            cur.close()
        
        return redirect(url_for('funds'))

@app.route('/distributions')
@login_required
def distributions():
    cur = mysql.connection.cursor()
    
    # Get distributions
    cur.execute("""
        SELECT d.*, 
               CONCAT(u.first_name, ' ', u.last_name) as conducted_by_name,
               COUNT(di.id) as item_count,
               SUM(di.quantity) as total_quantity
        FROM distributions d
        JOIN users u ON d.conducted_by = u.id
        LEFT JOIN distribution_items di ON d.id = di.distribution_id
        GROUP BY d.id
        ORDER BY d.distribution_date DESC
    """)
    distributions_list = cur.fetchall()
    
    # Get stats
    cur.execute("SELECT COUNT(*) as count FROM distributions WHERE distribution_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)")
    monthly_distributions = cur.fetchone()['count']
    
    cur.execute("""
        SELECT SUM(beneficiary_count) as total 
        FROM distributions 
        WHERE distribution_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
    """)
    monthly_beneficiaries = cur.fetchone()['total'] or 0
    
    cur.execute("""
        SELECT SUM(di.quantity) as total 
        FROM distribution_items di
        JOIN distributions d ON di.distribution_id = d.id
        WHERE d.distribution_date >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
    """)
    monthly_food = cur.fetchone()['total'] or 0
    
    cur.close()
    
    return render_template('distributions.html', 
                         distributions=distributions_list,
                         monthly_distributions=monthly_distributions,
                         monthly_beneficiaries=monthly_beneficiaries,
                         monthly_food=monthly_food)

@app.route('/add_distribution', methods=['POST'])
@login_required
def add_distribution():
    if request.method == 'POST':
        distribution_date = request.form['distributionDate']
        location = request.form['location']
        beneficiary_count = request.form['beneficiaryCount']
        food_items = request.form['foodItems']  # This would need parsing
        quantity = request.form['quantity']
        unit = request.form['unit']
        notes = request.form.get('notes', '')
        
        # In a real implementation, you would parse the food items and quantities
        # and add them to the distribution_items table
        
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO distributions (distribution_date, location, beneficiary_count, notes, conducted_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (distribution_date, location, beneficiary_count, notes, session['user_id']))
            
            # For simplicity, we're just adding one food item here
            # In a real implementation, you would loop through all food items
            distribution_id = cur.lastrowid
            
            # Find food item ID
            cur.execute("SELECT id FROM food_items WHERE unit = %s LIMIT 1", (unit,))
            food_item = cur.fetchone()
            
            if food_item:
                cur.execute("""
                    INSERT INTO distribution_items (distribution_id, food_item_id, quantity)
                    VALUES (%s, %s, %s)
                """, (distribution_id, food_item['id'], quantity))
            
            mysql.connection.commit()
            flash('Distribution recorded successfully!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash('Error recording distribution: ' + str(e), 'danger')
        finally:
            cur.close()
        
        return redirect(url_for('distributions'))
@app.route('/reports')
@login_required
def reports():
    cur = mysql.connection.cursor()

    # Get total funds
    cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM funds")
    row = cur.fetchone()
    total_funds = row['total'] if row else 0

    # Get financial data for charts
    cur.execute("""
        SELECT DATE_FORMAT(received_date, '%Y-%m') as month, 
               SUM(amount) as funds_received
        FROM funds 
        WHERE received_date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(received_date, '%Y-%m')
        ORDER BY month
    """)
    funds_data = cur.fetchall()

    cur.execute("""
        SELECT DATE_FORMAT(expense_date, '%Y-%m') as month, 
               SUM(amount) as expenses
        FROM expenses 
        WHERE expense_date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(expense_date, '%Y-%m')
        ORDER BY month
    """)
    expenses_data = cur.fetchall()

    # Get beneficiaries by location
    cur.execute("""
        SELECT location, COUNT(*) as count 
        FROM beneficiaries 
        WHERE status = 'active'
        GROUP BY location
    """)
    location_data = cur.fetchall()

    # Get expense categories
    cur.execute("""
        SELECT ec.name, COALESCE(SUM(e.amount), 0) as total
        FROM expense_categories ec
        LEFT JOIN expenses e ON ec.id = e.category_id
        GROUP BY ec.id, ec.name
    """)
    expense_categories = cur.fetchall()

    # Get distribution trends
    cur.execute("""
        SELECT DATE_FORMAT(distribution_date, '%Y-%m') as month, 
               SUM(beneficiary_count) as beneficiaries_served
        FROM distributions 
        WHERE distribution_date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(distribution_date, '%Y-%m')
        ORDER BY month
    """)
    distribution_trends = cur.fetchall()

    cur.close()

    return render_template(
        'reports.html',
        total_funds=total_funds,
        funds_data=funds_data,
        expenses_data=expenses_data,
        location_data=location_data,
        expense_categories=expense_categories,
        distribution_trends=distribution_trends
    )

@app.route('/settings')
@login_required
def settings():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cur.fetchone()
    cur.close()
    
    return render_template('settings.html', user=user)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    if request.method == 'POST':
        first_name = request.form['firstName']
        last_name = request.form['lastName']
        email = request.form['email']
        phone = request.form['phone']
        
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                UPDATE users 
                SET first_name = %s, last_name = %s, email = %s, phone = %s
                WHERE id = %s
            """, (first_name, last_name, email, phone, session['user_id']))
            
            mysql.connection.commit()
            session['full_name'] = f"{first_name} {last_name}"
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash('Error updating profile: ' + str(e), 'danger')
        finally:
            cur.close()
        
        return redirect(url_for('settings'))


@app.route('/add_expense', methods=['POST'])
def add_expense():
    category = request.form['category']
    amount = request.form['expenseAmount']
    date = request.form['expenseDate']
    description = request.form['description']
    location = request.form['location']
    notes = request.form.get('expenseNotes')

    

    flash("Expense added successfully!", "success")
    return redirect(url_for('funds'))




@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)