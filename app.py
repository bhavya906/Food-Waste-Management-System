from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
from bson import ObjectId
import pytz
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
import pandas as pd

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Admin credentials (you should move these to a secure configuration file in production)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # Use a strong password in production

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "kr4785543@gmail.com"  # Replace with your email
SMTP_PASSWORD = "qhuzwfrdagfyqemk"      # Replace with your app password

def send_email(to_email, subject, body):
    try:
        # Create message
        message = MIMEMultipart()
        message["From"] = SMTP_USERNAME
        message["To"] = to_email
        message["Subject"] = subject
        
        # Add body to email
        message.attach(MIMEText(body, "plain"))
        
        # Create SMTP session
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
            
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# MongoDB connection
client = MongoClient('mongodb+srv://kr4785543:1234567890@cluster0.220yz.mongodb.net/')
db = client['food_management']

# Collections
hotels = db.hotels
organizations = db.organizations
volunteers = db.volunteers
donations = db.donations
delivery_requests = db.delivery_requests
donation_requests = db.donation_requests

# Landing page route
@app.route('/')
def landing():
    return render_template('landing.html')

# Registration routes
@app.route('/register/hotel', methods=['GET', 'POST'])
def hotel_register():
    if request.method == 'POST':
        hotel_data = {
            'hotel_name': request.form['hotel_name'],
            'email': request.form['email'],
            'password': generate_password_hash(request.form['password']),
            'address': request.form['address'],
            'phone': request.form['phone'],
            'created_at': datetime.now(),
            'status': False  # Added status field
        }
        
        if hotels.find_one({'email': hotel_data['email']}):
            flash('Email already registered')
            return redirect(url_for('hotel_register'))
        
        result = hotels.insert_one(hotel_data)
        if result.inserted_id:
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        
    return render_template('hotel_register.html')

@app.route('/register/organization', methods=['GET', 'POST'])
def org_register():
    if request.method == 'POST':
        org_data = {
            'org_name': request.form['org_name'],
            'email': request.form['email'],
            'password': generate_password_hash(request.form['password']),
            'address': request.form['address'],
            'phone': request.form['phone'],
            'org_type': request.form['org_type'],
            'created_at': datetime.now(),
            'status': False  # Added status field
        }
        
        if organizations.find_one({'email': org_data['email']}):
            flash('Email already registered')
            return redirect(url_for('org_register'))
        
        organizations.insert_one(org_data)
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('org_register.html')

@app.route('/register/volunteer', methods=['GET', 'POST'])
def volunteer_register():
    if request.method == 'POST':
        volunteer_data = {
            'full_name': request.form['full_name'],
            'email': request.form['email'],
            'password': generate_password_hash(request.form['password']),
            'address': request.form['address'],  # Added address field
            'phone': request.form['phone'],
            'created_at': datetime.now(),
            'status': False  # Added status field
        }
        
        if volunteers.find_one({'email': volunteer_data['email']}):
            flash('Email already registered')
            return redirect(url_for('volunteer_register'))
        
        volunteers.insert_one(volunteer_data)
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('volunteer_register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        
        try:
            user = None
            if user_type == 'hotel':
                user = hotels.find_one({'email': email})
                dashboard = 'hotel_dashboard'
            elif user_type == 'organization':
                user = organizations.find_one({'email': email})
                dashboard = 'org_dashboard'
            elif user_type == 'volunteer':
                user = volunteers.find_one({'email': email})
                dashboard = 'volunteer_dashboard'
            
            if user and check_password_hash(user['password'], password):
                if not user.get('status', False):  # Check status
                    flash('Your account is pending approval')
                    return redirect(url_for('login'))
                    
                session['user_id'] = str(user['_id'])
                session['user_type'] = user_type
                session['email'] = user['email']
                print(f"Login successful for {user_type}: {email}")
                return redirect(url_for(dashboard))
            
            flash('Invalid email or password')
            
        except Exception as e:
            print(f"Login error: {e}")
            flash('An error occurred during login')
            
        return redirect(url_for('login'))
    
    return render_template('login.html')

# Dashboard routes
@app.route('/dashboard/hotel')
def hotel_dashboard():
    if 'user_id' not in session or session['user_type'] != 'hotel':
        return redirect(url_for('login'))
    
    try:
        hotel = hotels.find_one({'_id': ObjectId(session['user_id'])})
        if not hotel:
            session.clear()
            return redirect(url_for('login'))
        
        # Transform recent activities for better display
        recent_activities = []
        recent_requests = donation_requests.find(
            {'hotel_id': session['user_id']}
        ).sort('requested_at', -1).limit(5)
        
        for request in recent_requests:
            activity = {
                'timestamp': request['requested_at'],
                'description': f"Request from {request.get('org_name', 'Unknown')} for {request.get('quantity', 0)} servings of {request.get('food_type', 'food')}",
                'status': request['status'],
                'status_class': request['status'].lower()
            }
            recent_activities.append(activity)
        
        return render_template('hotel_dashboard.html',
                             hotel_name=hotel['hotel_name'],
                             recent_activities=recent_activities)
                             
    except Exception as e:
        print(f"Dashboard error: {e}")
        flash('Error loading dashboard')
        return redirect(url_for('login'))

def get_nearby_places(org_city):
    try:
        # Read the CSV file
        df = pd.read_csv('AP_Places_Nearby.csv')
        
        # Find the row for the organization's city
        city_row = df[df['Place'].str.lower() == org_city.lower()]
        
        if not city_row.empty:
            # Get nearby places as a list
            nearby_places = city_row.iloc[0]['Nearby Places'].split(', ')
            # Add the main city itself to the list
            nearby_places.append(city_row.iloc[0]['Place'])
            # Convert all places to lowercase for case-insensitive comparison
            return [place.lower().strip() for place in nearby_places]
    except Exception as e:
        print(f"Error reading nearby places: {e}")
        return []
    
    return []

@app.route('/dashboard/organization')
def org_dashboard():
    if 'user_id' not in session or session['user_type'] != 'organization':
        return redirect(url_for('login'))
    
    try:
        org = organizations.find_one({'_id': ObjectId(session['user_id'])})
        if not org:
            session.clear()
            return redirect(url_for('login'))
        
        # Get organization's city
        org_city = org.get('address', '').strip()
        nearby_places = get_nearby_places(org_city)
        
        # Get available donations
        all_available_donations = list(donations.find({'status': 'available'}))
        
        # Filter donations based on nearby places
        available_donations = []
        for donation in all_available_donations:
            hotel_city = donation.get('hotel_location', {}).get('address', '').split(',')[-1].strip().lower()
            if hotel_city in nearby_places:
                # Add distance information to donation
                donation['distance_info'] = 'Nearby location'
                available_donations.append(donation)
        
        # Sort donations by expiry time
        available_donations.sort(key=lambda x: x['expiry'])
        
        # Get organization's requests - handle both string and ObjectId formats
        my_requests = list(donation_requests.find({
            '$or': [
                {'org_id': str(session['user_id'])},
                {'org_id': ObjectId(session['user_id'])}
            ]
        }).sort('requested_at', -1))
        
        print(f"Found {len(available_donations)} nearby donations out of {len(all_available_donations)} total donations")
        
        return render_template('org_dashboard.html',
                             org_name=org['org_name'],
                             org_type=org['org_type'],
                             available_donations=available_donations,
                             my_requests=my_requests,
                             current_city=org_city,
                             nearby_places=nearby_places)
                             
    except Exception as e:
        print(f"Error in org dashboard: {e}")
        flash('Error loading dashboard')
        return redirect(url_for('login'))

@app.route('/dashboard/volunteer')
def volunteer_dashboard():
    if 'user_id' not in session or session['user_type'] != 'volunteer':
        return redirect(url_for('login'))
    
    try:
        # Debug prints
        print("==== STARTING VOLUNTEER DASHBOARD ====")
        
        volunteer = volunteers.find_one({'_id': ObjectId(session['user_id'])})
        if not volunteer:
            print("Volunteer not found!")
            session.clear()
            return redirect(url_for('login'))
            
        print(f"Volunteer found: {volunteer['full_name']}")

        # Get current time in Indian timezone
        india_tz = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(india_tz)
        naive_current_time_ist = current_time.replace(tzinfo=None)  # For naive comparison in IST
        
        print(f"Current time (IST): {current_time}")
        print(f"Current time (IST naive): {naive_current_time_ist}")
        
        # Calculate the time window (next 30 minutes)
        thirty_mins_later_ist = current_time + timedelta(minutes=30)
        naive_thirty_mins_later_ist = thirty_mins_later_ist.replace(tzinfo=None)  # For naive comparison in IST
        print(f"30 mins later (IST): {thirty_mins_later_ist}")
        print(f"30 mins later (IST naive): {naive_thirty_mins_later_ist}")

        # CRITICAL DEBUG: First check what's in the database overall
        print("Checking all donations in the database:")
        all_donations = list(donations.find())
        print(f"Total donations in database: {len(all_donations)}")
        for d in all_donations:
            print(f"ID: {d['_id']}, Type: {d['food_type']}, Status: {d['status']}, Expiry: {d['expiry']}")
        
        # Check only available donations
        print("\nChecking available donations:")
        available_donations = list(donations.find({'status': 'available'}))
        print(f"Available donations: {len(available_donations)}")
        for d in available_donations:
            print(f"ID: {d['_id']}, Type: {d['food_type']}, Expiry: {d['expiry']}")
        
        # Find urgent donations - available items expiring within 30 minutes
        urgent_donations = []
        
        for donation in available_donations:
            expiry = donation['expiry']
            print(f"Processing donation: {donation['_id']}, Type: {donation['food_type']}, Expiry: {expiry}, Type: {type(expiry)}")
            
            # Is expiry a datetime object?
            if isinstance(expiry, datetime):
                # Assume the naive datetime in the database is already in IST
                # Compare directly with our naive IST times
                print(f"  IST comparison: {naive_current_time_ist} <= {expiry} <= {naive_thirty_mins_later_ist}")
                if naive_current_time_ist <= expiry <= naive_thirty_mins_later_ist:
                    # Calculate minutes until expiry
                    time_diff = expiry - naive_current_time_ist
                    minutes_left = time_diff.total_seconds() / 60
                    donation['minutes_until_expiry'] = minutes_left
                    
                    # Add to urgent donations
                    urgent_donations.append(donation)
                    print(f"  ADDED AS URGENT: Minutes left: {minutes_left}")
                else:
                    print(f"  NOT URGENT: Outside time window")
            else:
                print(f"  WARNING: Expiry is not a datetime object! Type: {type(expiry)}")
        
        # Sort by most urgent first
        urgent_donations.sort(key=lambda x: x.get('minutes_until_expiry', float('inf')))
        
        print(f"Urgent donations found: {len(urgent_donations)}")
        for d in urgent_donations:
            # All times are already in IST, so we don't need to convert for display
            print(f"ID: {d['_id']}, Type: {d['food_type']}, Expiry: {d['expiry']}, Minutes left: {d.get('minutes_until_expiry')}")
            
        print("\nRendering template with volunteer name and urgent donations")
        print(f"Volunteer name: {volunteer['full_name']}")
        print(f"Number of urgent donations: {len(urgent_donations)}")
        
        return render_template('volunteer_dashboard.html',
                              volunteer_name=volunteer['full_name'],
                              urgent_donations=urgent_donations,
                              current_time=current_time)
                             
    except Exception as e:
        print(f"ERROR in volunteer dashboard: {e}")
        import traceback
        print(traceback.format_exc())
        flash('Error loading dashboard')
        return redirect(url_for('login'))

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route('/add_donation', methods=['POST'])
def add_donation():
    if 'user_id' not in session or session['user_type'] != 'hotel':
        return redirect(url_for('login'))
    
    try:
        # Get hotel details including address
        hotel = hotels.find_one({'_id': ObjectId(session['user_id'])})
        if not hotel:
            flash('Hotel details not found')
            return redirect(url_for('hotel_dashboard'))

        ist = pytz.timezone('Asia/Kolkata')
        donation_data = {
            'hotel_id': session['user_id'],
            'hotel_name': hotel['hotel_name'],
            'food_type': request.form['food_type'],
            'quantity': int(request.form['quantity']),
            'expiry': datetime.strptime(request.form['expiry'], '%Y-%m-%dT%H:%M'),
            'status': 'available',
            'created_at': datetime.now(),
            # Adding hotel location details
            'hotel_location': {
                'address': hotel['address'],
                'phone': hotel['phone'],
                'coordinates': hotel.get('coordinates', None),  # If you have coordinates stored
            },
            # Adding pickup details
            'pickup_details': {
                'address': hotel['address'],
                'contact_person': hotel.get('contact_person', hotel['hotel_name']),
                'phone': hotel['phone'],
                'instructions': request.form.get('pickup_instructions', '')
            }
        }
        
        donations.insert_one(donation_data)
        flash('Donation added successfully!')
    except Exception as e:
        print(f"Error adding donation: {e}")
        flash('Error adding donation. Please try again.')
    
    return redirect(url_for('hotel_dashboard'))

@app.route('/view_donations')
def view_donations():
    if 'user_id' not in session or session['user_type'] != 'hotel':
        return redirect(url_for('login'))
    
    hotel_donations = list(donations.find({'hotel_id': session['user_id']}))
    return render_template('view_donations.html', donations=hotel_donations)

@app.route('/request_donation', methods=['POST'])
def request_donation():
    if 'user_id' not in session or session['user_type'] != 'organization':
        return redirect(url_for('login'))
    
    try:
        donation_id = request.form['donation_id']
        donation = donations.find_one({'_id': ObjectId(donation_id)})
        org = organizations.find_one({'_id': ObjectId(session['user_id'])})
        
        if not donation or donation['status'] != 'available':
            flash('This donation is no longer available.')
            return redirect(url_for('org_dashboard'))
        
        # Get hotel details for phone number
        hotel = hotels.find_one({'_id': ObjectId(donation['hotel_id'])})
        
        request_data = {
            'donation_id': str(donation_id),
            'food_type': donation['food_type'],
            'quantity': donation['quantity'],
            'hotel_id': donation['hotel_id'],
            'hotel_name': donation['hotel_name'],
            'hotel_phone': hotel['phone'] if hotel else 'Not available',
            'org_id': str(session['user_id']),
            'org_name': org['org_name'],
            'org_phone': org['phone'],
            'status': 'pending',
            'requested_at': datetime.now()
        }
        
        donation_requests.insert_one(request_data)
        donations.update_one(
            {'_id': ObjectId(donation_id)},
            {'$set': {'status': 'pending'}}
        )
        
        flash('Request sent successfully!')
    except Exception as e:
        print(f"Error in request_donation: {e}")
        flash('Error sending request. Please try again.')
    
    return redirect(url_for('org_dashboard'))

@app.route('/handle_request/<request_id>/<action>', methods=['POST'])
def handle_request(request_id, action):
    if 'user_id' not in session or session['user_type'] != 'hotel':
        return redirect(url_for('login'))
    
    try:
        # First try to find in organization requests
        request_obj = donation_requests.find_one({'_id': ObjectId(request_id)})
        request_type = 'organization'
        
        # If not found in organization requests, try volunteer requests
        if not request_obj:
            request_obj = delivery_requests.find_one({'_id': ObjectId(request_id)})
            request_type = 'delivery'
            
        if not request_obj or request_obj['hotel_id'] != str(session['user_id']):
            flash('Invalid request')
            return redirect(url_for('hotel_dashboard'))
        
        new_status = 'accepted' if action == 'accept' else 'rejected'
        
        # Update request status based on type
        if request_type == 'organization':
            # Update organization request status
            donation_requests.update_one(
                {'_id': ObjectId(request_id)},
                {'$set': {
                    'status': new_status,
                    'updated_at': datetime.now()
                }}
            )
        else:
            # Update volunteer delivery request status
            delivery_requests.update_one(
                {'_id': ObjectId(request_id)},
                {'$set': {
                    'status': new_status,
                    'updated_at': datetime.now()
                }}
            )
        
        # Update donation status
        if request_type == 'organization':
            donations.update_one(
                {'_id': ObjectId(request_obj['donation_id'])},
                {'$set': {'status': new_status}}
            )
        else:
            donations.update_one(
                {'_id': ObjectId(request_obj['donation_id'])},
                {'$set': {
                    'delivery_status': new_status,
                    'status': 'in_delivery' if new_status == 'accepted' else 'available'
                }}
            )
        
        flash(f'Request {new_status} successfully!')
    except Exception as e:
        print(f"Error handling request: {e}")
        flash('Error processing request')
    
    # Get the donation_id for redirect
    try:
        donation_id = request_obj['donation_id']
        if isinstance(donation_id, str):
            donation_id = ObjectId(donation_id)
        return redirect(url_for('donation_requests_view', donation_id=donation_id))
    except:
        return redirect(url_for('hotel_all_requests'))

@app.route('/hotel/donations')
def hotel_donations():
    if 'user_id' not in session or session['user_type'] != 'hotel':
        return redirect(url_for('login'))
    
    try:
        hotel = hotels.find_one({'_id': ObjectId(session['user_id'])})
        if not hotel:
            return redirect(url_for('login'))
        
        # Get all donations with request counts (both organization and volunteer requests)
        pipeline = [
            {
                '$match': {
                    'hotel_id': str(session['user_id'])
                }
            },
            {
                '$lookup': {
                    'from': 'donation_requests',
                    'let': { 'donation_id': { '$toString': '$_id' } },
                    'pipeline': [
                        {
                            '$match': {
                                '$expr': {
                                    '$or': [
                                        { '$eq': ['$donation_id', '$$donation_id'] },
                                        { '$eq': ['$donation_id', { '$toObjectId': '$$donation_id' }] }
                                    ]
                                }
                            }
                        }
                    ],
                    'as': 'org_requests'
                }
            },
            {
                '$lookup': {
                    'from': 'delivery_requests',
                    'let': { 'donation_id': { '$toString': '$_id' } },
                    'pipeline': [
                        {
                            '$match': {
                                '$expr': { '$eq': ['$donation_id', '$$donation_id'] }
                            }
                        }
                    ],
                    'as': 'volunteer_requests'
                }
            },
            {
                '$addFields': {
                    'request_count': {
                        '$add': [
                            { '$size': '$org_requests' },
                            { '$size': '$volunteer_requests' }
                        ]
                    }
                }
            }
        ]
        
        donations_list = list(donations.aggregate(pipeline))
        print(f"Found {len(donations_list)} donations with request counts")
        
        return render_template('hotel_donations.html',
                             hotel_name=hotel['hotel_name'],
                             donations=donations_list)
                             
    except Exception as e:
        print(f"Error in hotel_donations: {e}")
        flash('Error loading donations')
        return redirect(url_for('hotel_dashboard'))

@app.route('/hotel/donation/<donation_id>/requests')
def donation_requests_view(donation_id):
    if 'user_id' not in session or session['user_type'] != 'hotel':
        return redirect(url_for('login'))
    
    try:
        # Convert donation_id to ObjectId
        donation = donations.find_one({'_id': ObjectId(donation_id)})
        if not donation:
            flash('Donation not found')
            return redirect(url_for('hotel_donations'))
            
        if donation['hotel_id'] != str(session['user_id']):
            flash('Unauthorized access')
            return redirect(url_for('hotel_donations'))
        
        # Get organization requests
        org_requests = list(donation_requests.find({
            '$or': [
                {'donation_id': str(donation_id)},
                {'donation_id': ObjectId(donation_id)}
            ]
        }))
        
        # Add type field to distinguish organization requests
        for req in org_requests:
            req['type'] = 'organization'
        
        # Get volunteer delivery requests
        volunteer_requests = list(delivery_requests.find({
            'donation_id': str(donation_id)
        }))
        
        # Combine and sort all requests by requested_at
        all_requests = org_requests + volunteer_requests
        all_requests.sort(key=lambda x: x['requested_at'], reverse=True)
        
        print(f"Found {len(all_requests)} total requests for donation {donation_id}")
        
        return render_template('donation_requests.html',
                             hotel_name=donation['hotel_name'],
                             donation=donation,
                             requests=all_requests)
                             
    except Exception as e:
        print(f"Error in donation_requests_view: {e}")
        flash('Error loading requests')
        return redirect(url_for('hotel_donations'))

@app.route('/hotel/requests')
def hotel_requests():
    if 'user_id' not in session or session['user_type'] != 'hotel':
        return redirect(url_for('login'))
    
    try:
        # Get all requests for all donations from this hotel
        pipeline = [
            {'$match': {'hotel_id': session['user_id']}},
            {'$lookup': {
                'from': 'donations',
                'localField': 'donation_id',
                'foreignField': '_id',
                'as': 'donation'
            }},
            {'$unwind': '$donation'}
        ]
        requests_list = list(donation_requests.aggregate(pipeline))
        
        return render_template('hotel_all_requests.html',
                             requests=requests_list)
    except Exception as e:
        flash('Error loading requests')
        return redirect(url_for('hotel_dashboard'))

@app.route('/hotel/all-requests')
def hotel_all_requests():
    if 'user_id' not in session or session['user_type'] != 'hotel':
        return redirect(url_for('login'))
    
    try:
        hotel = hotels.find_one({'_id': ObjectId(session['user_id'])})
        if not hotel:
            return redirect(url_for('login'))
        
        # Get organization requests
        org_requests = list(donation_requests.find({
            'hotel_id': str(session['user_id'])
        }).sort('requested_at', -1))
        
        # Add type field to distinguish organization requests
        for req in org_requests:
            req['type'] = 'organization'
        
        # Get volunteer delivery requests
        volunteer_requests = list(delivery_requests.find({
            'hotel_id': str(session['user_id'])
        }).sort('requested_at', -1))
        
        # Combine and sort all requests by requested_at
        all_requests = org_requests + volunteer_requests
        all_requests.sort(key=lambda x: x['requested_at'], reverse=True)
        
        print(f"Found {len(all_requests)} total requests")
        
        return render_template('hotel_all_requests.html',
                             hotel_name=hotel['hotel_name'],
                             requests=all_requests)
                             
    except Exception as e:
        print(f"Error loading all requests: {e}")
        flash('Error loading requests')
        return redirect(url_for('hotel_dashboard'))

@app.route('/accept_delivery/<donation_id>', methods=['POST'])
def accept_delivery(donation_id):
    if 'user_id' not in session or session['user_type'] != 'volunteer':
        return redirect(url_for('login'))
    
    try:
        # Get the volunteer details
        volunteer = volunteers.find_one({'_id': ObjectId(session['user_id'])})
        if not volunteer:
            flash('Volunteer not found')
            return redirect(url_for('volunteer_dashboard'))
            
        # Get the donation details
        donation = donations.find_one({'_id': ObjectId(donation_id)})
        if not donation:
            flash('Donation not found')
            return redirect(url_for('volunteer_dashboard'))
            
        # Get hotel details for phone number
        hotel = hotels.find_one({'_id': ObjectId(donation['hotel_id'])})
            
        # Create a delivery request
        delivery_request = {
            'donation_id': str(donation_id),
            'food_type': donation['food_type'],
            'quantity': donation['quantity'],
            'hotel_id': donation['hotel_id'],
            'hotel_name': donation['hotel_name'],
            'hotel_phone': hotel['phone'] if hotel else 'Not available',
            'volunteer_id': str(session['user_id']),
            'volunteer_name': volunteer['full_name'],
            'volunteer_phone': volunteer['phone'],
            'status': 'pending',
            'type': 'delivery',  # To distinguish from organization requests
            'requested_at': datetime.now()
        }
        
        # Insert the delivery request
        delivery_requests.insert_one(delivery_request)
        
        # Update donation status to indicate a pending delivery request
        donations.update_one(
            {'_id': ObjectId(donation_id)},
            {'$set': {
                'delivery_status': 'pending',
                'volunteer_id': session['user_id'],
                'volunteer_name': volunteer['full_name'],
                'volunteer_phone': volunteer['phone']
            }}
        )
        
        flash('Delivery request created successfully!')
    except Exception as e:
        print(f"Error accepting delivery: {e}")
        flash('Error accepting delivery. Please try again.')
    
    return redirect(url_for('volunteer_dashboard'))

@app.route('/volunteer/requests')
def volunteer_requests():
    if 'user_id' not in session or session['user_type'] != 'volunteer':
        return redirect(url_for('login'))
    
    try:
        volunteer = volunteers.find_one({'_id': ObjectId(session['user_id'])})
        if not volunteer:
            return redirect(url_for('login'))
        
        # Get all delivery requests by this volunteer
        pipeline = [
            {
                '$match': {
                    'volunteer_id': str(session['user_id'])
                }
            },
            {
                '$lookup': {
                    'from': 'donations',
                    'let': { 'donation_id': { '$toObjectId': '$donation_id' } },
                    'pipeline': [
                        {
                            '$match': {
                                '$expr': { '$eq': ['$_id', '$$donation_id'] }
                            }
                        }
                    ],
                    'as': 'donation_details'
                }
            },
            {
                '$unwind': '$donation_details'
            },
            {
                '$sort': { 'requested_at': -1 }
            }
        ]
        
        requests_list = list(delivery_requests.aggregate(pipeline))
        print(f"Found {len(requests_list)} delivery requests for volunteer {volunteer['full_name']}")
        
        return render_template('volunteer_requests.html',
                             volunteer_name=volunteer['full_name'],
                             requests=requests_list)
                             
    except Exception as e:
        print(f"Error in volunteer_requests: {e}")
        flash('Error loading requests')
        return redirect(url_for('volunteer_dashboard'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials')
            return redirect(url_for('admin_login'))
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    try:
        # Fetch all entities
        all_hotels = list(hotels.find())
        all_organizations = list(organizations.find())
        all_volunteers = list(volunteers.find())
        
        # Calculate statistics
        stats = {
            'hotels': {
                'total': len(all_hotels),
                'pending': len([h for h in all_hotels if not h.get('status', False)]),
                'approved': len([h for h in all_hotels if h.get('status', False)])
            },
            'organizations': {
                'total': len(all_organizations),
                'pending': len([o for o in all_organizations if not o.get('status', False)]),
                'approved': len([o for o in all_organizations if o.get('status', False)])
            },
            'volunteers': {
                'total': len(all_volunteers),
                'pending': len([v for v in all_volunteers if not v.get('status', False)]),
                'approved': len([v for v in all_volunteers if v.get('status', False)])
            }
        }
        
        return render_template('admin_dashboard.html',
                             datetime=datetime,
                             hotels=all_hotels,
                             organizations=all_organizations,
                             volunteers=all_volunteers,
                             stats=stats)
                             
    except Exception as e:
        print(f"Admin dashboard error: {e}")
        flash('Error loading admin dashboard')
        return redirect(url_for('admin_login'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('landing'))

@app.route('/admin/hotel/<hotel_id>/approve', methods=['POST'])
@admin_required
def approve_hotel(hotel_id):
    try:
        hotels.update_one(
            {'_id': ObjectId(hotel_id)},
            {'$set': {'status': True}}
        )
        return jsonify({'success': True, 'message': 'Hotel approved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/hotel/<hotel_id>/reject', methods=['POST'])
@admin_required
def reject_hotel(hotel_id):
    try:
        hotels.delete_one({'_id': ObjectId(hotel_id)})
        return jsonify({'success': True, 'message': 'Hotel rejected successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/hotel/<hotel_id>/deactivate', methods=['POST'])
@admin_required
def deactivate_hotel(hotel_id):
    try:
        hotels.update_one(
            {'_id': ObjectId(hotel_id)},
            {'$set': {'status': False}}
        )
        return jsonify({'success': True, 'message': 'Hotel deactivated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/<entity_type>/<entity_id>/approve', methods=['POST'])
@admin_required
def approve_entity(entity_type, entity_id):
    try:
        # Map entity types to their collections
        collections = {
            'hotel': hotels,
            'organization': organizations,
            'volunteer': volunteers
        }
        
        if entity_type not in collections:
            return jsonify({
                'success': False,
                'message': 'Invalid entity type'
            }), 400
            
        collection = collections[entity_type]
            
        # Validate ObjectId
        if not ObjectId.is_valid(entity_id):
            return jsonify({
                'success': False,
                'message': 'Invalid ID format'
            }), 400

        # Update the entity status
        result = collection.update_one(
            {'_id': ObjectId(entity_id)},
            {
                '$set': {
                    'status': True,
                    'approved_at': datetime.now()
                }
            }
        )
        
        if result.matched_count == 0:
            return jsonify({
                'success': False,
                'message': f'{entity_type.capitalize()} not found'
            }), 404
            
        if result.modified_count == 0:
            return jsonify({
                'success': False,
                'message': f'{entity_type.capitalize()} already approved'
            }), 400
            
        return jsonify({
            'success': True,
            'message': f'{entity_type.capitalize()} approved successfully'
        })
            
    except Exception as e:
        print(f"Error in approve_entity: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/admin/<entity_type>/<entity_id>/reject', methods=['POST'])
@admin_required
def reject_entity(entity_type, entity_id):
    try:
        collections = {
            'hotel': hotels,
            'organization': organizations,
            'volunteer': volunteers
        }
        
        if entity_type not in collections:
            return jsonify({
                'success': False,
                'message': 'Invalid entity type'
            }), 400

        collection = collections[entity_type]

        if not ObjectId.is_valid(entity_id):
            return jsonify({
                'success': False,
                'message': 'Invalid ID format'
            }), 400

        result = collection.delete_one({'_id': ObjectId(entity_id)})
        
        if result.deleted_count == 0:
            return jsonify({
                'success': False,
                'message': f'{entity_type.capitalize()} not found'
            }), 404

        return jsonify({
            'success': True,
            'message': f'{entity_type.capitalize()} rejected successfully'
        })
            
    except Exception as e:
        print(f"Error in reject_entity: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/admin/<entity_type>/<entity_id>/deactivate', methods=['POST'])
@admin_required
def deactivate_entity(entity_type, entity_id):
    try:
        collections = {
            'hotel': hotels,
            'organization': organizations,
            'volunteer': volunteers
        }
        
        if entity_type not in collections:
            return jsonify({
                'success': False,
                'message': 'Invalid entity type'
            }), 400

        collection = collections[entity_type]

        if not ObjectId.is_valid(entity_id):
            return jsonify({
                'success': False,
                'message': 'Invalid ID format'
            }), 400

        result = collection.update_one(
            {'_id': ObjectId(entity_id)},
            {
                '$set': {
                    'status': False,
                    'deactivated_at': datetime.now()
                }
            }
        )
        
        if result.matched_count == 0:
            return jsonify({
                'success': False,
                'message': f'{entity_type.capitalize()} not found'
            }), 404

        return jsonify({
            'success': True,
            'message': f'{entity_type.capitalize()} deactivated successfully'
        })
            
    except Exception as e:
        print(f"Error in deactivate_entity: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/send_donation_request_otp/<request_id>', methods=['POST'])
def send_donation_request_otp(request_id):
    if 'user_id' not in session or session['user_type'] != 'hotel':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        # Find the donation request
        request_obj = donation_requests.find_one({'_id': ObjectId(request_id)})
        if not request_obj:
            return jsonify({'success': False, 'message': 'Request not found'}), 404

        # Find the organization
        org = organizations.find_one({'_id': ObjectId(request_obj['org_id'])})
        print(org)
        if not org:
            return jsonify({'success': False, 'message': 'Organization not found'}), 404

        # Generate OTP
        otp = generate_otp()
        
        # Store OTP in the request document
        donation_requests.update_one(
            {'_id': ObjectId(request_id)},
            {
                '$set': {
                    'verification_otp': otp,
                    'otp_expires_at': datetime.now() + timedelta(minutes=10)  # OTP expires in 10 minutes
                }
            }
        )

        # Send OTP via email
        email_subject = "Food Donation Request - OTP Verification"
        email_body = f"""
        Hello {org['org_name']},

        Your OTP for verifying the food donation request is: {otp}

        This OTP will expire in 10 minutes.

        If you didn't request this OTP, please ignore this email.

        Best regards,
        Food Donation Management System
        """

        if send_email(org['email'], email_subject, email_body):
            return jsonify({
                'success': True,
                'message': 'OTP sent successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to send OTP email'
            }), 500

    except Exception as e:
        print(f"Error sending OTP: {e}")
        return jsonify({
            'success': False,
            'message': 'Error processing request'
        }), 500

@app.route('/verify_donation_request_otp/<request_id>', methods=['POST'])
def verify_donation_request_otp(request_id):
    if 'user_id' not in session or session['user_type'] != 'hotel':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        otp = request.form.get('otp')
        if not otp:
            return jsonify({
                'success': False,
                'message': 'OTP is required'
            }), 400

        # Find the request and verify OTP
        request_obj = donation_requests.find_one({
            '_id': ObjectId(request_id),
            'verification_otp': otp,
            'otp_expires_at': {'$gt': datetime.now()}
        })

        if not request_obj:
            return jsonify({
                'success': False,
                'message': 'Invalid or expired OTP'
            }), 400

        # Update donation request status to accepted
        donation_requests.update_one(
            {'_id': ObjectId(request_id)},
            {
                '$set': {
                    'status': 'accepted',
                    'updated_at': datetime.now()
                },
                '$unset': {
                    'verification_otp': "",
                    'otp_expires_at': ""
                }
            }
        )

        # Update the donation status
        donations.update_one(
            {'_id': ObjectId(request_obj['donation_id'])},
            {
                '$set': {
                    'status': 'accepted',
                    'updated_at': datetime.now()
                }
            }
        )

        return jsonify({
            'success': True,
            'message': 'OTP verified and request accepted successfully'
        })

    except Exception as e:
        print(f"Error verifying OTP: {e}")
        return jsonify({
            'success': False,
            'message': 'Error processing request'
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
