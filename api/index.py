from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_dance.contrib.google import make_google_blueprint, google
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import uuid
import os
import razorpay
import cloudinary
import cloudinary.uploader

# Vercel-ന്റെ Read-Only എറർ പൂർണ്ണമായും മാറ്റാൻ instance_path ഇവിടെ നൽകുന്നു
app = Flask(__name__, instance_path='/tmp')

app.secret_key = os.getenv('SECRET_KEY', 'brinshell_super_secret_key')

# Vercel-ൽ ലോഗിൻ സെഷൻ നഷ്ടപ്പെടാതിരിക്കാൻ ഇത് നിർബന്ധമാണ്
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# --- CLOUDINARY CONFIGURATION ---
cloudinary.config(
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key = os.getenv('CLOUDINARY_API_KEY'),
    api_secret = os.getenv('CLOUDINARY_API_SECRET')
)

# --- DATABASE CONFIGURATION ---
db_url = os.getenv('DATABASE_URL')
if not db_url:
    db_url = 'sqlite:////tmp/brinshell.db'
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- EMAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'adiyychalakkal5@gmail.com')  
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'jpolnonwbztapirv')         
mail = Mail(app)

# --- GOOGLE OAUTH SETUP ---
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', 'YOUR_GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', 'YOUR_GOOGLE_CLIENT_SECRET')

google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=["profile", "email"],
    redirect_to="google_login"
)
app.register_blueprint(google_bp, url_prefix="/login")

# --- RAZORPAY SETUP ---
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_your_key_id_here') 
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'your_key_secret_here')  
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

PLAN_PRICES = {
    'pro': 49900,      
    'plus': 89900,     
    'premium': 149900  
}

def build_otp_email(otp, heading, intro):
    digits = ''.join(
        f'<td style="padding:0 4px;"><div style="width:44px;height:56px;line-height:56px;'
        f'text-align:center;font-size:28px;font-weight:700;color:#111827;background:#f3f4f6;'
        f'border:1px solid #e5e7eb;border-radius:10px;font-family:Segoe UI,Roboto,Arial,sans-serif;">{d}</div></td>'
        for d in otp
    )
    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f4f5f7;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:32px 12px;">
    <tr><td align="center">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">
        <tr>
          <td align="center" style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:28px 20px;">
            <div style="font-family:Segoe UI,Roboto,Arial,sans-serif;font-size:22px;font-weight:800;letter-spacing:3px;color:#ffffff;">BRIN SHELL</div>
          </td>
        </tr>
        <tr>
          <td style="padding:32px 28px 8px;font-family:Segoe UI,Roboto,Arial,sans-serif;">
            <h2 style="margin:0 0 10px;font-size:20px;color:#111827;">{heading}</h2>
            <p style="margin:0;font-size:15px;line-height:1.6;color:#4b5563;">{intro}</p>
          </td>
        </tr>
        <tr>
          <td align="center" style="padding:24px 28px;">
            <!-- ഈ ഒറ്റ ബോക്സ് കാരണം ഡബിൾ ക്ലിക്ക് ചെയ്താൽ കോഡ് എളുപ്പത്തിൽ കോപ്പി ചെയ്യാം -->
            <div style="display:inline-block;padding:16px 32px;font-size:36px;font-weight:700;letter-spacing:8px;color:#111827;background:#f3f4f6;border:2px dashed #cbd5e1;border-radius:12px;font-family:Segoe UI,Roboto,Arial,sans-serif;cursor:pointer;">
              {otp}
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:0 28px 28px;font-family:Segoe UI,Roboto,Arial,sans-serif;">
            <p style="margin:0;font-size:13px;line-height:1.6;color:#6b7280;text-align:center;">
              Ee code ninte security-kku vendi aanu. Aarodum share cheyyaruthu.<br>
              Ee request nee cheythathalla enkil, ee email ignore cheyyam.
            </p>
          </td>
        </tr>
        <tr>
          <td align="center" style="background:#f9fafb;padding:16px;border-top:1px solid #eef0f3;font-family:Segoe UI,Roboto,Arial,sans-serif;font-size:12px;color:#9ca3af;">
            &copy; BRIN SHELL. All rights reserved.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True) 
    plan = db.Column(db.String(20), default='none')
    plan_expiry = db.Column(db.DateTime)
    session_token = db.Column(db.String(100))
    otp = db.Column(db.String(6))
    current_video_order = db.Column(db.Integer, default=1) 
    auth_provider = db.Column(db.String(20), default='email')
    profile_name = db.Column(db.String(100), default="Student")
    profile_photo = db.Column(db.String(500), nullable=True)

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
    if user.plan == 'suspended': return False 
    if user.email != 'adiyychalakkal5@gmail.com' and user.plan != 'none' and datetime.now() > user.plan_expiry: return False
    return user

# --- MAIN ROUTES ---
@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/pay/<plan>')
def pay(plan): 
    session['selected_plan'] = plan 
    return redirect(url_for('auth', plan=plan))

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
        
    if user.plan == 'none' and plan:
        return redirect(url_for('checkout', plan=plan))
        
    return redirect(url_for('dashboard'))

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    plan = request.args.get('plan')
    if request.method == 'POST':
        action = request.form.get('action', '').strip()
        email = request.form.get('email', '').strip()
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
                msg.body = f"Your verification code is: {otp}"
                msg.html = build_otp_email(
                    otp,
                    "Verify your email",
                    "Welcome to BRIN SHELL! Account create cheyyan ee code verification page-il enter cheyyuka."
                )
                mail.send(msg)
            except Exception as e:
                print(e)
                return render_template('auth.html', error="Failed to send email.", plan=plan, otp_sent=False)
            return render_template('auth.html', email=email, otp_sent=True, plan=plan)
            
        elif action == 'verify_otp':
            entered_otp = request.form.get('otp', '').strip()
            email_hidden = request.form.get('email', '').strip()
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
        action = request.form.get('action', '').strip()
        email = request.form.get('email', '').strip()
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
                msg.body = f"Your verification code is: {otp}"
                msg.html = build_otp_email(
                    otp,
                    "Your login code",
                    "Login cheyyan ee code use cheyyuka."
                )
                mail.send(msg)
            except Exception as e:
                print(e)
                return render_template('login.html', error="Failed to send email.", otp_sent=False)
            return render_template('login.html', email=email, otp_sent=True)
            
        elif action == 'verify_otp':
            entered_otp = request.form.get('otp', '').strip()
            email_hidden = request.form.get('email', '').strip()
            user = User.query.filter_by(email=email_hidden).first()
            
            if user and user.otp == entered_otp:
                new_token = str(uuid.uuid4())
                user.session_token = new_token
                user.otp = None 
                db.session.commit()
                session['user_email'] = email_hidden
                session['device_token'] = new_token
                if email_hidden == 'adiyychalakkal5@gmail.com': return redirect(url_for('admin'))
                
                if user.plan == 'none':
                    plan_from_session = session.get('selected_plan', 'pro')
                    return redirect(url_for('checkout', plan=plan_from_session))
                    
                return redirect(url_for('dashboard'))
            
            return render_template('login.html', error="Invalid OTP! Please try again.", email=email_hidden, otp_sent=True)
            
    return render_template('login.html', otp_sent=False)

@app.route('/checkout/<plan>')
def checkout(plan):
    user = check_auth()
    if not user: 
        session['selected_plan'] = plan
        return redirect(url_for('login'))
        
    if plan not in PLAN_PRICES: return "Invalid Plan"
        
    amount = PLAN_PRICES[plan]
    
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
    user.plan = plan
    user.plan_expiry = datetime.now() + timedelta(days=30)
    db.session.commit()
    
    return redirect(url_for('dashboard'))

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
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user = check_auth()
    if not user: return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('profile_name')
        password = request.form.get('password')
        photo = request.files.get('profile_photo')
        
        if name:
            user.profile_name = name
            
        if password:
            user.password = generate_password_hash(password)
            
        if photo and photo.filename != '':
            try:
                # Cloudinary-ലേക്ക് പ്രൊഫൈൽ ഫോട്ടോ അപ്‌ലോഡ് ചെയ്യുന്നു
                upload_result = cloudinary.uploader.upload(
                    photo, 
                    folder="brinshell_profiles"
                )
                user.profile_photo = upload_result.get('secure_url')
            except Exception as e:
                print(f"Error uploading photo: {e}")
                
        db.session.commit()
        return redirect(url_for('profile'))
        
    return render_template('profile.html', user=user)
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('user_email') != 'adiyychalakkal5@gmail.com': return "Access Denied!"
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'upload_video':
            title = request.form.get('title')
            category = request.form.get('category')
            section = request.form.get('section')
            order_num = request.form.get('order_num')
            video_file = request.files.get('video_file')
            
            if video_file and video_file.filename != '':
                try:
                    upload_result = cloudinary.uploader.upload(
                        video_file, 
                        resource_type="video", 
                        folder="brinshell_videos"
                    )
                    cloud_video_url = upload_result.get('secure_url')
                    new_video = Video(title=title, video_url=cloud_video_url, category=category, section=section, order_num=int(order_num))
                    db.session.add(new_video)
                    db.session.commit()
                except Exception as e:
                    print(f"Error uploading to Cloudinary: {e}")
                
        elif action == 'reply_doubt':
            message_id = request.form.get('message_id')
            reply_text = request.form.get('reply_text')
            msg = CommunityMessage.query.get(message_id)
            if msg:
                msg.admin_reply = reply_text
                db.session.commit()
                
        elif action == 'suspend_user':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                user.plan = 'suspended'
                db.session.commit()
                
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
