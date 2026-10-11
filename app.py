from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_dance.contrib.google import make_google_blueprint, google
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import random
import uuid
import os
import razorpay  # പുതിയ Razorpay ഇമ്പോർട്ട്

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # Only for testing in localhost

app = Flask(__name__)
app.secret_key = 'brinshell_super_secret_key'

UPLOAD_FOLDER = 'static/videos'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- DATABASE CONFIGURATION ---
import os
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'brinshell.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- EMAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'adiyychalakkal5@gmail.com'  
app.config['MAIL_PASSWORD'] = 'jpolnonwbztapirv'         
mail = Mail(app)

# --- GOOGLE OAUTH SETUP ---
GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"

google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=["profile", "email"],
    redirect_to="google_login"
)
app.register_blueprint(google_bp, url_prefix="/login")

# --- RAZORPAY SETUP ---
RAZORPAY_KEY_ID = "rzp_test_your_key_id_here" # നിങ്ങളുടെ യഥാർത്ഥ Key ID ഇവിടെ നൽകുക
RAZORPAY_KEY_SECRET = "your_key_secret_here"  # നിങ്ങളുടെ യഥാർത്ഥ Key Secret ഇവിടെ നൽകുക
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

PLAN_PRICES = {
    'pro': 49900,      # ₹499
    'plus': 89900,     # ₹899
    'premium': 149900  # ₹1499
}

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True) 
    plan = db.Column(db.String(20), default='none') # പേയ്‌മെൻ്റ് കഴിയുമ്പോൾ മാത്രം പ്ലാൻ ആക്റ്റീവ് ആക്കാൻ
    plan_expiry = db.Column(db.DateTime)
    session_token = db.Column(db.String(100))
    otp = db.Column(db.String(6))
    current_video_order = db.Column(db.Integer, default=1) 
    auth_provider = db.Column(db.String(20), default='email')
    profile_name = db.Column(db.String(100), default="Student")

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    video_url = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(20), nullable=False) 
    section = db.Column(db.String(100), nullable=False, default="Module 1") 
    order_num = db.Column(db.Integer, nullable=False) 

class CommunityMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    admin_reply = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='adiyychalakkal5@gmail.com').first():
        hashed_pw = generate_password_hash('admin123')
        admin = User(email='adiyychalakkal5@gmail.com', password=hashed_pw, plan='admin', plan_expiry=datetime.now() + timedelta(days=3650))
        db.session.add(admin)
        db.session.commit()

# --- HELPER FUNCTION ---
def check_auth():
    if 'user_email' not in session: return False
    user = User.query.filter_by(email=session['user_email']).first()
    if not user or user.session_token != session.get('device_token'): return False
    
    # യൂസറെ അഡ്മിൻ സസ്പെൻഡ് ചെയ്തിട്ടുണ്ടെങ്കിൽ ലോഗിൻ അനുവദിക്കില്ല
    if user.plan == 'suspended': return False 
    
    if user.email != 'adiyychalakkal5@gmail.com' and user.plan != 'none' and datetime.now() > user.plan_expiry: return False
    return user

# --- MAIN ROUTES ---
@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/pay/<plan>')
def pay(plan): 
    # പുതിയ യൂസർ ആണെങ്കിൽ ആദ്യം രജിസ്റ്റർ ചെയ്യാൻ പോകുന്നു
    session['selected_plan'] = plan 
    return redirect(url_for('auth', plan=plan))

# --- GOOGLE LOGIN ---
@app.route("/google-login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))
        
    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok: return "Failed to fetch user info from Google."
        
    google_info = resp.json()
    email = google_info["email"]
    
    user = User.query.filter_by(email=email).first()
    plan = session.get('selected_plan', 'pro')
    
    if not user:
        user = User(email=email, plan='none', auth_provider='google')
        db.session.add(user)
    
    new_token = str(uuid.uuid4())
    user.session_token = new_token
    db.session.commit()
    
    session['user_email'] = email
    session['device_token'] = new_token
    
    if email == 'adiyychalakkal5@gmail.com':
        return redirect(url_for('admin'))
        
    # ലോഗിൻ ചെയ്ത ശേഷം പേയ്‌മെൻ്റ് കഴിഞ്ഞിട്ടില്ലെങ്കിൽ checkout ലേക്ക് പോകും
    if user.plan == 'none' and plan:
        return redirect(url_for('checkout', plan=plan))
        
    return redirect(url_for('dashboard'))

# --- EMAIL AUTH & HTML OTP ROUTES ---
@app.route('/auth', methods=['GET', 'POST'])
def auth():
    plan = request.args.get('plan')
    if request.method == 'POST':
        email = request.form.get('email')
        action = request.form.get('action')
        user = User.query.filter_by(email=email).first()
        
        if action == 'send_otp':
            if user: 
                return render_template('auth.html', error="Email already registered!", plan=plan, otp_sent=False)
            
            password = request.form.get('password')
            hashed_pw = generate_password_hash(password)
            otp = str(random.randint(100000, 999999))
            
            new_user = User(email=email, password=hashed_pw, plan='none')
            new_user.otp = otp
            db.session.add(new_user)
            db.session.commit()
            
            try:
                msg = Message('Verify Your Email Address - BRIN SHELL', sender=app.config['MAIL_USERNAME'], recipients=[email])
                
                # Clean, Razorpay-style Corporate Email Template
                msg.html = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f5f7; margin: 0; padding: 0; min-height: 100vh;">
                    
                    <!-- Dark Teal Header (Like Razorpay Blue Header) -->
                    <div style="background-color: #0b5e5a; padding: 30px 20px 60px 20px; text-align: center;">
                        <h1 style="margin: 0; color: #ffffff; font-size: 22px; font-weight: 900; letter-spacing: 1px;">
                            brain<span style="color: #facc15;">e</span>ll
                        </h1>
                    </div>

                    <!-- White Content Card -->
                    <div style="max-width: 480px; margin: -40px auto 40px auto; background-color: #ffffff; padding: 40px 30px; border-radius: 4px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center;">
                        
                        <!-- Icon -->
                        <div style="margin-bottom: 20px;">
                            <img src="https://ui-avatars.com/api/?name=BS&background=0b5e5a&color=fff&rounded=true&size=50" alt="Icon" style="width: 50px; height: 50px;">
                        </div>

                        <h2 style="color: #111827; font-size: 20px; margin-top: 0; margin-bottom: 25px; font-weight: 500;">
                            Verify Your Email Address
                        </h2>

                        <hr style="border: none; border-top: 1px solid #e5e7eb; margin-bottom: 25px;">

                        <p style="font-size: 14px; color: #374151; line-height: 1.6; margin-bottom: 35px;">
                            Verify your email to finish signing up for the {plan.title()} plan with BRIN SHELL. Use the following verification code:
                        </p>
                        
                        <!-- Large OTP Code -->
                        <h1 style="margin: 0; font-size: 38px; font-weight: 500; color: #0b5e5a; letter-spacing: 2px;">
                            {otp}
                        </h1>

                        <p style="font-size: 13px; color: #6b7280; margin-top: 35px; margin-bottom: 0;">
                            The verification code is valid for 10 minutes.
                        </p>
                    </div>

                    <!-- Footer Text -->
                    <div style="text-align: center; padding-bottom: 40px; padding-left: 20px; padding-right: 20px;">
                        <p style="font-size: 11px; color: #9ca3af; margin: 0; line-height: 1.5;">
                            For any further queries or clarifications, feel free to reach out to us by replying to this email.
                        </p>
                    </div>
                </div>
                """
                #mail.send(msg)
                print(f"OTP is: {otp}")
                print(f"✅ HTML Email successfully sent to {email}")
            except Exception as e:
                print(e)
                return render_template('auth.html', error="Failed to send email. Check your internet settings.", plan=plan, otp_sent=False)

            return render_template('auth.html', email=email, otp_sent=True, plan=plan)
            
        elif action == 'verify_otp':
            entered_otp = request.form.get('otp')
            email_hidden = request.form.get('email')
            user = User.query.filter_by(email=email_hidden).first()
            if user and user.otp == entered_otp:
                new_token = str(uuid.uuid4())
                user.session_token = new_token
                user.otp = None 
                db.session.commit()
                session['user_email'] = email_hidden
                session['device_token'] = new_token
                
                return redirect(url_for('checkout', plan=plan))
            
            return render_template('auth.html', error="Invalid OTP! Please try again.", email=email_hidden, plan=plan, otp_sent=True)
            
    return render_template('auth.html', plan=plan, otp_sent=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        action = request.form.get('action')
        user = User.query.filter_by(email=email).first()
        
        if action == 'send_otp':
            password = request.form.get('password')
            if not user or not user.password or not check_password_hash(user.password, password): 
                return render_template('login.html', error="Invalid Email or Password.", otp_sent=False)
            
            otp = str(random.randint(100000, 999999))
            user.otp = otp
            db.session.commit()
            
            try:
                msg = Message('Your Secure Login Code - BRIN SHELL', sender=app.config['MAIL_USERNAME'], recipients=[email])
                
                # Clean, Razorpay-style Corporate Email Template
                msg.html = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f5f7; margin: 0; padding: 0; min-height: 100vh;">
                    
                    <!-- Dark Teal Header -->
                    <div style="background-color: #0b5e5a; padding: 30px 20px 60px 20px; text-align: center;">
                        <h1 style="margin: 0; color: #ffffff; font-size: 22px; font-weight: 900; letter-spacing: 1px;">
                            brain<span style="color: #facc15;">e</span>ll
                        </h1>
                    </div>

                    <!-- White Content Card -->
                    <div style="max-width: 480px; margin: -40px auto 40px auto; background-color: #ffffff; padding: 40px 30px; border-radius: 4px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center;">
                        
                        <div style="margin-bottom: 20px;">
                            <img src="https://ui-avatars.com/api/?name=BS&background=0b5e5a&color=fff&rounded=true&size=50" alt="Icon" style="width: 50px; height: 50px;">
                        </div>

                        <h2 style="color: #111827; font-size: 20px; margin-top: 0; margin-bottom: 25px; font-weight: 500;">
                            Secure Login Request
                        </h2>

                        <hr style="border: none; border-top: 1px solid #e5e7eb; margin-bottom: 25px;">

                        <p style="font-size: 14px; color: #374151; line-height: 1.6; margin-bottom: 35px;">
                            We received a request to log into your BRIN SHELL account. Use the following verification code to proceed:
                        </p>
                        
                        <!-- Large OTP Code -->
                        <h1 style="margin: 0; font-size: 38px; font-weight: 500; color: #0b5e5a; letter-spacing: 2px;">
                            {otp}
                        </h1>

                        <p style="font-size: 13px; color: #6b7280; margin-top: 35px; margin-bottom: 0;">
                            If you did not request this code, you can safely ignore this email.
                        </p>
                    </div>

                    <!-- Footer Text -->
                    <div style="text-align: center; padding-bottom: 40px; padding-left: 20px; padding-right: 20px;">
                        <p style="font-size: 11px; color: #9ca3af; margin: 0; line-height: 1.5;">
                            For any further queries or clarifications, feel free to reach out to us by replying to this email.
                        </p>
                    </div>
                </div>
                """
                mail.send(msg)
                print(f"✅ HTML Email successfully sent to {email}")
            except Exception as e:
                print(e)
                return render_template('login.html', error="Failed to send email.", otp_sent=False)

            return render_template('login.html', email=email, otp_sent=True)
            
        elif action == 'verify_otp':
            entered_otp = request.form.get('otp')
            email_hidden = request.form.get('email')
            user = User.query.filter_by(email=email_hidden).first()
            if user and user.otp == entered_otp:
                new_token = str(uuid.uuid4())
                user.session_token = new_token
                user.otp = None 
                db.session.commit()
                session['user_email'] = email_hidden
                session['device_token'] = new_token
                if email_hidden == 'adiyychalakkal5@gmail.com': return redirect(url_for('admin'))
                
                # Check if user needs to pay
                if user.plan == 'none':
                    plan_from_session = session.get('selected_plan', 'pro')
                    return redirect(url_for('checkout', plan=plan_from_session))
                    
                return redirect(url_for('dashboard'))
            
            return render_template('login.html', error="Invalid OTP! Please try again.", email=email_hidden, otp_sent=True)
            
    return render_template('login.html', otp_sent=False)

# --- DUMMY CHECKOUT ROUTES (ഫോൺ ഇല്ലാത്തതുകൊണ്ട് താൽക്കാലികമായി ഉപയോഗിക്കാൻ) ---
@app.route('/checkout/<plan>')
def checkout(plan):
    user = check_auth()
    if not user: 
        session['selected_plan'] = plan
        return redirect(url_for('login'))
        
    if plan not in PLAN_PRICES: return "Invalid Plan"
        
    amount = PLAN_PRICES[plan]
    
    # Razorpay API ഒഴിവാക്കി ഒരു ഡമ്മി ഓർഡർ ഉണ്ടാക്കുന്നു
    class DummyOrder:
        pass
    order = DummyOrder()
    order.amount = amount
    order.id = "order_dummy_12345"
    
    return render_template('checkout.html', order=order, plan=plan, user=user)

@app.route('/payment_success', methods=['POST'])
def payment_success():
    user = check_auth()
    if not user: return redirect(url_for('login'))
    
    plan = request.form.get('plan')
    
    # തൽക്കാലം Razorpay Signature Verification ഒഴിവാക്കുന്നു
    # പെയ്മെൻ്റ് വിജയിച്ചതായി കണക്കാക്കി ഡാറ്റാബേസ് അപ്ഡേറ്റ് ചെയ്യുന്നു
    user.plan = plan
    user.plan_expiry = datetime.now() + timedelta(days=30)
    db.session.commit()
    
    return redirect(url_for('dashboard'))

# --- DASHBOARD & PORTAL LOGIC ---
@app.route('/dashboard')
def dashboard():
    user = check_auth()
    if not user: return redirect(url_for('login'))
    if user.plan == 'none': return redirect(url_for('checkout', plan='pro'))
    
    if user.plan == 'pro': return redirect(url_for('pro_page'))
    elif user.plan == 'plus': return redirect(url_for('plus_page'))
    elif user.plan == 'premium': return redirect(url_for('premium_page'))
    elif user.plan == 'admin': return redirect(url_for('admin'))
    return "Invalid Plan"

@app.route('/portal/<plan>')
def class_portal(plan):
    user = check_auth()
    if not user or user.plan != plan: return redirect(url_for('login'))
    
    requested_order = request.args.get('v', type=int, default=user.current_video_order)
    if requested_order > user.current_video_order: requested_order = user.current_video_order
    
    videos = Video.query.filter_by(category=plan).order_by(Video.order_num).all()
    
    total_videos = len(videos)
    progress_percentage = 0
    if total_videos > 0:
        progress_percentage = int(((user.current_video_order - 1) / total_videos) * 100)
    
    sections = {}
    for v in videos:
        if v.section not in sections: sections[v.section] = []
        sections[v.section].append(v)
        
    active_video = Video.query.filter_by(category=plan, order_num=requested_order).first()
    if not active_video and videos: active_video = videos[0]
    
    messages = CommunityMessage.query.order_by(CommunityMessage.timestamp.desc()).all()
    
    return render_template('portal.html', videos=videos, sections=sections, active_video=active_video, user=user, plan=plan, progress=progress_percentage, messages=messages)

@app.route('/pro')
def pro_page(): return redirect(url_for('class_portal', plan='pro'))
@app.route('/plus')
def plus_page(): return redirect(url_for('class_portal', plan='plus'))
@app.route('/premium')
def premium_page(): return redirect(url_for('class_portal', plan='premium'))

@app.route('/complete_video', methods=['POST'])
def complete_video():
    user = check_auth()
    if not user: return redirect(url_for('login'))
    current_order = int(request.form.get('current_order'))
    plan = user.plan
    next_video = Video.query.filter_by(category=plan, order_num=current_order + 1).first()
    if next_video and user.current_video_order == current_order:
        user.current_video_order += 1
        db.session.commit()
        return redirect(url_for('class_portal', plan=plan, v=user.current_video_order))
    return redirect(url_for('class_portal', plan=plan, v=current_order))

@app.route('/post_message', methods=['POST'])
def post_message():
    user = check_auth()
    if not user: return redirect(url_for('login'))
    content = request.form.get('content')
    if content:
        new_msg = CommunityMessage(user_email=user.email, content=content)
        db.session.add(new_msg)
        db.session.commit()
    return redirect(request.referrer)

# --- SECURED ADMIN PORTAL ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('user_email') != 'adiyychalakkal5@gmail.com': return "Access Denied!"
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # 1. Video Upload
        if action == 'upload_video':
            title = request.form.get('title')
            category = request.form.get('category')
            section = request.form.get('section')
            order_num = request.form.get('order_num')
            video_file = request.files.get('video_file')
            
            if video_file and video_file.filename != '':
                filename = secure_filename(video_file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                video_file.save(file_path)
                
                new_video = Video(title=title, video_url=unique_filename, category=category, section=section, order_num=int(order_num))
                db.session.add(new_video)
                db.session.commit()
                
        # 2. Reply to User Doubt
        elif action == 'reply_doubt':
            message_id = request.form.get('message_id')
            reply_text = request.form.get('reply_text')
            msg = CommunityMessage.query.get(message_id)
            if msg:
                msg.admin_reply = reply_text
                db.session.commit()
                
        # 3. Suspend (Block) User
        elif action == 'suspend_user':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                user.plan = 'suspended'
                db.session.commit()
                
        # 4. Activate / Update User Plan
        elif action == 'activate_user':
            user_id = request.form.get('user_id')
            new_plan = request.form.get('new_plan')
            user = User.query.get(user_id)
            if user:
                user.plan = new_plan
                user.plan_expiry = datetime.now() + timedelta(days=30)
                db.session.commit()
                
        return redirect(url_for('admin'))
        
    videos = Video.query.order_by(Video.category, Video.order_num).all()
    users = User.query.filter(User.email != 'adiyychalakkal5@gmail.com').all()
    messages = CommunityMessage.query.order_by(CommunityMessage.timestamp.desc()).all()

    total_revenue = 0
    for u in users:
        if u.plan == 'pro':
            total_revenue += 499
        elif u.plan == 'plus':
            total_revenue += 899
        elif u.plan == 'premium':
            total_revenue += 1499

    return render_template('admin.html', videos=videos, users=users, messages=messages, total_revenue=total_revenue)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)