from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import secrets

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '1234'
app.config['MYSQL_DB'] = 'hospital_management'
app.config['SECRET_KEY'] = 'hospital_management_secret_key'  # Fixed secret key instead of random

mysql = MySQL(app)

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        cur = mysql.connection.cursor()
        try:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            
            print(f"Login attempt for email: {email}")  # Add logging
            print(f"User found: {user is not None}")    # Add logging
            
            if user:
                # Check if password matches the stored hash
                if check_password_hash(user[3], password):
                    # Update last login time
                    cur.execute("UPDATE users SET last_login = %s WHERE id = %s", 
                              (datetime.now(), user[0]))
                    
                    # Set session
                    session['user_id'] = user[0]
                    session['email'] = user[2]
                    session['name'] = user[1]
                    
                    mysql.connection.commit()
                    
                    return jsonify({
                        'success': True,
                        'redirect': url_for('dashboard')
                    })
                else:
                    print("Password verification failed")  # Add logging
            
            return jsonify({
                'success': False,
                'message': 'Invalid email or password'
            })
                
        except Exception as e:
            print(f"Login error: {str(e)}")  # Add logging
            return jsonify({
                'success': False,
                'message': str(e)
            })
        finally:
            cur.close()
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        
        # Generate password hash
        hashed_password = generate_password_hash(password)
        
        cur = mysql.connection.cursor()
        try:
            # First check if email already exists
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            existing_user = cur.fetchone()
            
            if existing_user:
                return jsonify({
                    'success': False,
                    'message': 'Email already registered'
                })
            
            # If email doesn't exist, create new user
            cur.execute("""
                INSERT INTO users (full_name, email, password, created_at)
                VALUES (%s, %s, %s, %s)
            """, (name, email, hashed_password, datetime.now()))
            mysql.connection.commit()
            
            # Get the newly created user
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            
            if user:
                # Set session
                session['user_id'] = user[0]
                session['email'] = user[2]
                session['name'] = user[1]
                
                return jsonify({
                    'success': True,
                    'redirect': url_for('dashboard')
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to create user'
                })
                
        except Exception as e:
            print(f"Signup error: {str(e)}")  # Add logging
            return jsonify({
                'success': False,
                'message': f'An error occurred during registration: {str(e)}'
            })
        finally:
            cur.close()
    
    return render_template('login.html')

@app.route('/appointment')
def appointment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('user_dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('user_dashboard.html')

@app.route('/contact', methods=['POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO contact_queries (name, email, message, submitted_at)
                VALUES (%s, %s, %s, %s)
            """, (name, email, message, datetime.now()))
            mysql.connection.commit()
            return jsonify({'success': True, 'message': 'Query submitted successfully!'})
        except Exception as e:
            return jsonify({'success': False, 'message': 'An error occurred.'})
        finally:
            cur.close()


# Email configuration
EMAIL_ADDRESS = "nivasreddybobby20@gmail.com"
EMAIL_PASSWORD = "fqkd zuvp bdbq ihkh"

def send_confirmation_email(recipient_email, appointment_details):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient_email
    msg['Subject'] = "Appointment Confirmation"
    
    body = f"""
    Dear {appointment_details['name']},

    Your appointment has been successfully booked!

    Details:
    Date: {appointment_details['date']}
    Time: {appointment_details['time']}

    Please arrive 10 minutes before your scheduled time.
    If you need to reschedule, please contact us at least 24 hours in advance.

    Best regards,
    Hospital Management Team
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {str(e)}")
        return False

@app.route('/book-appointment', methods=['POST'])
def book_appointment():
    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'message': 'Please log in to book an appointment'
        })
        
    try:
        data = request.json
        
        # Validate appointment time is in the future
        appointment_datetime = datetime.strptime(
            f"{data['date']} {data['time']}", 
            "%Y-%m-%d %H:%M"
        )
        
        if appointment_datetime < datetime.now():
            return jsonify({
                'success': False,
                'message': 'Please select a future date and time'
            })
        
        # Insert appointment into database
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO appointments 
            (patient_name, email, appointment_date, appointment_time, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            data['name'],
            data['email'],
            data['date'],
            data['time'],
            'scheduled'
        ))
        
        mysql.connection.commit()
        
        # Send confirmation email
        if send_confirmation_email(data['email'], data):
            return jsonify({
                'success': True,
                'message': 'Appointment booked successfully'
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Appointment booked successfully, but email confirmation failed'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })
    finally:
        cur.close()


if __name__ == '__main__':
    app.run(debug=True)