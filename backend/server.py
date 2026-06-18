import torch
from dotenv import load_dotenv
load_dotenv()
import ssl
import gzip
import base64
import datetime
import threading
import requests
import random
import gc
import io
import jwt
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from model import BrainTumorCNN
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
import os
import numpy as np
import hashlib
import json
import time
import mysql.connector
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from PIL import Image
import os
import json
import smtplib
from email.mime.text import MIMEText
import random
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import subprocess
import os
from flask import request
import zipfile
from email.utils import formataddr
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import urllib3
import logging
import os # Just ensuring this is imported if it isn't already at the top
from sklearn.metrics import precision_recall_fscore_support, accuracy_score, classification_report
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET', 'fallback-secret-key')

# 🤫 SILENCE THE FLASK/WERKZEUG SPAM 🤫
# This stops Flask from printing every single HTTP request, only printing actual crashes.
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),  
    'database': os.getenv('DB_NAME', 'fl_audit_db')
}

print("\n--- DEBUG: DATABASE CONFIG ---")
print(f"Host: {DB_CONFIG['host']}")
print(f"User: {DB_CONFIG['user']}")
print(f"Database: {DB_CONFIG['database']}")
print("------------------------------\n")
'''HOSPITAL_CREDENTIALS = {
    "admin": {"password": "admin_password", "role": "ADMIN"},
    "hospital_a": {"password": "password123", "role": "HOSPITAL"},
    "hospital_b": {"password": "password456", "role": "HOSPITAL"}
}
'''

client_config_str = os.getenv("CLIENT_CONFIG", "{}")
CLIENT_CONFIG = json.loads(client_config_str)



REQUIRED_CLIENTS = ["hospital_a", "hospital_b"]
CLIENTS_PER_ROUND = 2
CHUNK_SIZE = 500_000  
SERVER_TEST_PATH = "./data/Test"  
SERVER_VALIDATION_PATH = "./data/Test"  #Testing
 
# --- GLOBAL STATE ---
training_state = {
    "status": "Idle",
    "current_round": 0,
    "total_rounds": 10,
    "accuracy_history": [],
    "loss_history": [],
    "distance_history": [],
    "precision_history": [],  # <-- NEW
    "recall_history": [],     # <-- NEW
    "f1_history": []
}
connected_clients = {}
detailed_logs = []  
global_model = BrainTumorCNN()
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
DEVICE = device

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET', 'fallback-secret-key')
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def get_user_from_db(username):
    """Fetches a user record from MySQL."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) 
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        print(f"❌ Database User Error: {e}")
        return None
class Block:
    def __init__(self, index, timestamp, client_id, update_hash, status, previous_hash):
        self.index = index
        self.timestamp = timestamp
        self.client_id = client_id
        self.update_hash = update_hash
        self.status = status 
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "client_id": self.client_id,
            "update_hash": self.update_hash,
            "status": self.status,
            "previous_hash": self.previous_hash
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()




class AuditChain:
    def __init__(self):
        self.chain = []
        self.load_chain_from_db()

    def load_chain_from_db(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM audit_ledger ORDER BY block_index ASC")
            rows = cursor.fetchall()
            
            if not rows:
                self.create_genesis_block()
            else:
                print(f"🔄 Loading {len(rows)} blocks from MySQL...")
                for row in rows:
                    block = Block(
                        row['block_index'], row['timestamp'], row['client_id'],
                        row['update_hash'], row['status'], row['previous_hash']
                    )
                    block.hash = row['current_hash'] 
                    self.chain.append(block)
            conn.close()
        except Exception as e:
            print(f"❌ Database Error: {e}")
            self.create_genesis_block()

    def create_genesis_block(self):
        genesis = Block(0, time.time(), "GENESIS", "0", "INIT", "0")
        self.save_block_to_db(genesis)
        self.chain.append(genesis)

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, client_id, weights_dict, status):
        weights_str = str(weights_dict.keys())
        weight_hash = hashlib.sha256(weights_str.encode()).hexdigest()
        prev_block = self.get_latest_block()
        new_block = Block(len(self.chain), time.time(), client_id, weight_hash, status, prev_block.hash)
        
        if self.save_block_to_db(new_block):
            self.chain.append(new_block)
            print(f"🔗 BLOCKCHAIN: Added Block #{new_block.index} to MySQL | Status: {status}")

    def save_block_to_db(self, block):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = """INSERT INTO audit_ledger 
                     (block_index, timestamp, client_id, update_hash, status, previous_hash, current_hash) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            val = (block.index, block.timestamp, block.client_id, 
                   block.update_hash, block.status, block.previous_hash, block.hash)
            cursor.execute(sql, val)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Failed to save block to DB: {e}")
            return False

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            prev = self.chain[i-1]
            if current.hash != current.calculate_hash(): return False
            if current.previous_hash != prev.hash: return False
        return True
    def refresh_chain(self):
        """Forces a reload from MySQL to Memory."""
        print("🔄 Force Refreshing Blockchain from Database...")
        self.chain = [] 
        self.load_chain_from_db()

audit_ledger = AuditChain()


def generate_hospital_mtls_certs(username):
    os.makedirs("client_certs", exist_ok=True)
    
    client_key = f"client_certs/{username}.key"
    client_csr = f"client_certs/{username}.csr"
    client_crt = f"client_certs/{username}.crt"
    client_conf = f"client_certs/{username}.conf"

    # 1. Create a single config file for BOTH identity and usage
    # Inside server.py -> generate_hospital_mtls_certs
    with open(client_conf, "w") as f:
        f.write(f"""
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = {username}
O = A3K
OU = GEC SKP 22-26 CSE

[v3_req]
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth, serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = {username}
DNS.2 = *.tailca8536.ts.net
DNS.3 = laptop-3hb2ene1
IP.1 = 127.0.0.1
IP.2 = 100.80.113.9
""")

    try:
        # 2. Generate Private Key
        subprocess.run(["openssl", "genrsa", "-out", client_key, "2048"], check=True, capture_output=True)
        
        # 3. Generate CSR using the config file (-config is the key here!)
        subprocess.run([
            "openssl", "req", "-new", "-key", client_key, 
            "-out", client_csr, 
            "-config", client_conf
        ], check=True, capture_output=True)
        
        # 4. Sign CSR with CA, explicitly pulling the extensions from the config
        subprocess.run([
            "openssl", "x509", "-req", "-in", client_csr, 
            "-CA", "certs/server_ca.crt", 
            "-CAkey", "certs/server_ca.key", 
            "-CAcreateserial", 
            "-out", client_crt, 
            "-days", "365", "-sha256",
            "-extensions", "v3_req",
            "-extfile", client_conf
        ], check=True, capture_output=True)
        
        # Cleanup config file
        os.remove(client_conf)
        
        print(f"🔐 Successfully generated mTLS certificates for {username}")
        return client_key, client_crt
        
    except subprocess.CalledProcessError as e:
        print(f"❌ OpenSSL Error generating certs for {username}: {e.stderr.decode()}")
        return None, None

def verify_mtls_certificate():
    """Extracts the identity (username) from the provided mTLS certificate."""
    # This works because you have context.verify_mode = ssl.CERT_OPTIONAL/REQUIRED
    cert = request.environ.get('peercert')
    
    if not cert:
        return None 

    try:
        # Subject is returned as a tuple of tuples: ((('commonName', 'hospital_a'),),)
        subject = dict(x[0] for x in cert.get('subject', []))
        return subject.get('commonName')
    except Exception as e:
        print(f"⚠️ mTLS extraction error: {e}")
        return None


def get_test_loader(path):
    if not os.path.exists(path): return None
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])
    ])
    dataset = datasets.ImageFolder(root=path, transform=transform)
    return DataLoader(dataset, batch_size=16, shuffle=False, num_workers=0)

test_loader = get_test_loader(SERVER_TEST_PATH)

def get_validation_loader():
    if not os.path.exists(SERVER_VALIDATION_PATH): return None
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])
    ])
    dataset = datasets.ImageFolder(root=SERVER_VALIDATION_PATH, transform=transform)
    return DataLoader(dataset, batch_size=16, shuffle=False)
def evaluate_model(model, loader):
    if not loader: return 0.0, 0.0, 0.0, 0.0, ""
    model.eval()
    model.to(device)
    
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for imgs, labels in loader:
            imgs, labels = imgs.to(device), labels.to(device)
            outputs = model(imgs)
            _, predicted = torch.max(outputs.data, 1)
            
            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            
    acc = accuracy_score(all_labels, all_preds) * 100
    precision, recall, f1, _ = precision_recall_fscore_support(
        all_labels, all_preds, average='macro', zero_division=0
    )

    # --- NEW: Generate the text report ---
    # target_names should match your classes: ['glioma', 'meningioma', 'notumor', 'pituitary']
    target_names = ['glioma', 'meningioma', 'notumor', 'pituitary']
    report = classification_report(all_labels, all_preds, target_names=target_names, digits=2)
    
    return acc, precision * 100, recall * 100, f1 * 100, report

def validate_update(client_weights):
    loader = get_validation_loader()
    if not loader: return 100.0
    temp_model = BrainTumorCNN()
    try:
        temp_model.load_state_dict(client_weights)
    except:
        return 100.0
    
    temp_model.eval()
    temp_model.to(device)
    correct, total = 0, 0
    
    with torch.no_grad():
        for imgs, labels in loader:
            imgs, labels = imgs.to(device), labels.to(device)
            # Binary Mapping: 2 (No Tumor) -> 0, Others -> 1
            binary_targets = torch.where(labels == 2, 0, 1)
            outputs = temp_model(imgs)
            _, raw_preds = torch.max(outputs.data, 1)
            
            if outputs.shape[1] == 4:
                binary_preds = torch.where(raw_preds == 2, 0, 1)
            else:
                binary_preds = raw_preds
                
            total += binary_targets.size(0)
            correct += (binary_preds == binary_targets).sum().item()
            
    return (correct / total) * 100 if total > 0 else 0

def encode_weights_chunks(model):
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer, _use_new_zipfile_serialization=False)
    compressed = gzip.compress(buffer.getvalue())
    buffer.close()
    b64 = base64.b64encode(compressed).decode('utf-8')
    return [b64[i:i+CHUNK_SIZE] for i in range(0, len(b64), CHUNK_SIZE)]

def decode_weights_chunks(chunks):
    b64 = ''.join(chunks)
    compressed = base64.b64decode(b64)
    buffer = io.BytesIO(gzip.decompress(compressed))
    state_dict = torch.load(buffer, map_location='cpu')
    buffer.close()
    return state_dict

def aggregate_securely(global_model, client_data_list, ledger, threshold_std=1.5):
    print("\n>>> 🛡️ RUNNING DYNAMIC SECURITY AGGREGATION...")
    global_flat = torch.cat([p.view(-1) for p in global_model.parameters()])
    
    round_log = {
        "round": training_state['current_round'],
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        "clients": []
    }

    client_metrics = []
    print("📊 Analyzing client performance...")
    
    for client_data in client_data_list:
        client_id = client_data['id']
        weights = client_data['weights']
        
        client_flat_list = [weights[k].view(-1) for k in weights]
        client_flat = torch.cat(client_flat_list)
        dist = torch.norm(client_flat - global_flat).item()
        
        val_acc = validate_update(weights)
        
        client_metrics.append({'id': client_id, 'weights': weights, 'dist': dist, 'acc': val_acc})
        print(f"   -> {client_id}: Dist={dist:.1f} | Acc={val_acc:.2f}%")

    scores = [m['acc'] for m in client_metrics]
    best_score = max(scores) if scores else 0.0
    DYNAMIC_THRESHOLD = max(60.0, best_score - 15.0)

    round_log["best_score"] = round(best_score, 2)
    round_log["threshold"] = round(DYNAMIC_THRESHOLD, 2)
    print(f"🌟 Best Score: {best_score:.2f}% | 🛡️ Threshold: {DYNAMIC_THRESHOLD:.2f}%")

    accepted_weights = []
    accepted_distances = [] # 👈 NEW: Track distances safely

    for m in client_metrics:
        client_id = m['id']
        weights = m['weights']
        dist = m['dist']
        acc = m['acc']
        
        status = "ACCEPTED"
        reason = "Valid Update"

        if dist > 500.0:
            status = "REJECTED"
            reason = f"Gradient Explosion (Dist {dist:.1f})"
            print(f"⚠️ Client {client_id} REJECTED! ({reason})")
            ledger.add_block(client_id, weights, "REJECTED_HUGE_GRADIENT")
        elif acc < DYNAMIC_THRESHOLD:
            status = "REJECTED"
            reason = f"Low Accuracy ({acc:.1f}% < {DYNAMIC_THRESHOLD:.1f}%)"
            print(f"⚠️ Client {client_id} REJECTED! ({reason})")
            ledger.add_block(client_id, weights, "REJECTED_BAD_MODEL")
        else:
            print(f"✅ Client {client_id} Accepted.")
            ledger.add_block(client_id, weights, "ACCEPTED")
            accepted_weights.append(weights)
            accepted_distances.append(dist) # 👈 Track accepted distance

        # Add to Round Log
        round_log["clients"].append({
            "client_id": client_id,
            "distance": round(dist, 2),
            "accuracy": round(acc, 2),
            "status": status,
            "reason": reason
        })

    detailed_logs.append(round_log)

    # 👈 NEW: Calculate history perfectly AFTER the loop finishes
    if accepted_distances:
        avg_dist = sum(accepted_distances) / len(accepted_distances)
        training_state["distance_history"].append(avg_dist)
    else:
        training_state["distance_history"].append(0.0)

    if not accepted_weights:
        print("CRITICAL: All clients rejected! Keeping previous model.")
        return global_model.state_dict()

    # Aggregate
    avg_weights = {}
    for key in accepted_weights[0].keys():
        avg_weights[key] = torch.stack([w[key] for w in accepted_weights]).mean(dim=0)
        
    return avg_weights

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('x-access-token')
        if not token: return jsonify({'message': 'Token missing'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except: return jsonify({'message': 'Invalid token'}), 401
        return f(data, *args, **kwargs)
    return decorated









def send_otp_email(receiver_email, otp):
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    
    if not sender_email or not sender_password:
        print("⚠️ Email credentials not found in .env!")
        return False

    msg = MIMEText(f"Your verification code for the Federated Learning System is: {otp}\n\nThis code will expire in 10 minutes.")
    msg['Subject'] = 'FL System Login Verification'
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:
        server = smtplib.SMTP(os.getenv("SMTP_SERVER", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", 587)))
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False
    





def send_onboarding_email(receiver_email, username, client_crt_path, client_key_path):
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    
    msg = MIMEMultipart('mixed')
    msg['Subject'] = f"🚀 Federated Learning: Node Approved ({username})"
    msg['From'] = formataddr(('FL Central Admin', sender_email))
    msg['To'] = formataddr((username, receiver_email))

    # --- HTML Body ---
    # --- HTML Body ---
    # --- HTML Body ---
    html_content = f"""
    <html>
    <body style="font-family: 'Segoe UI', sans-serif; line-height: 1.6; color: #333; background-color: #f4f7f6; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 30px; border-radius: 10px; border-top: 8px solid #3498db; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h2 style="color: #2c3e50; text-align: center;">Welcome to the Federation</h2>
            <p>Hello <strong>{username}</strong>,</p>
            <p>Your node has been approved. Please extract the attached ZIP kit to join the global AI training network.</p>
            
            <h4 style="color: #2c3e50; border-bottom: 2px solid #eee;">🛠️ 1. Installation</h4>
            <p>Open your terminal or command prompt inside the extracted folder and install the required Python libraries by running:</p>
            <div style="background: #f1f2f6; border-left: 5px solid #3498db; padding: 10px; font-family: monospace;">
                pip install -r requirements.txt
            </div>

            <h4 style="color: #2c3e50; border-bottom: 2px solid #eee;">⚙️ 2. Configuration</h4>
            <p>Create a file named <strong><code>.env</code></strong> in the extracted folder and add the following lines so your node knows where to connect:</p>
            <div style="background: #2c3e50; color: #fff; padding: 10px; border-radius: 5px; font-family: monospace;">
                HOSPITAL_NAME={username}<br>
                SERVER_URL=https//:100.94.68.3:5000
            </div>

            <h4 style="color: #2c3e50; border-bottom: 2px solid #eee;">📂 3. File Structure</h4>
            <p>Before running the node, ensure your folder looks exactly like this. The PyTorch script requires the MRI images to be separated into these 4 specific class folders:</p>
            <div style="background: #fdfdfd; border: 1px solid #ddd; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre; line-height: 1.4; overflow-x: auto;">
📁 extracted_folder/
├── 📄 client.py
├── 📄 model.py
├── 📄 requirements.txt
├── 📄 .env                  <span style="color: #e74c3c;">&lt;-- (You create this)</span>
├── 📁 certs/
│   ├── 🔑 server.crt
│   ├── 🔑 {username}.crt
│   └── 🔑 {username}.key
└── 📁 data/
    └── 📁 Train/
        ├── 📁 glioma_tumor/     <span style="color: #e74c3c;">&lt;-- (Images go inside here)</span>
        ├── 📁 meningioma_tumor/
        ├── 📁 no_tumor/
        └── 📁 pituitary_tumor/
            </div>

            <h4 style="color: #2c3e50; border-bottom: 2px solid #eee;">🚀 4. Execution</h4>
            <p>Once your MRI dataset is placed in the correct subfolders, start your node using:</p>
            <div style="background: #f1f2f6; border-left: 5px solid #2ecc71; padding: 10px; font-family: monospace;">
                python client.py --port 5001 --data-path "./data/Train"
            </div>
            
            <p style="margin-top: 20px; font-size: 0.9em; color: #7f8c8d;">
                <em>Note: Your unique security certificates are included in the certs folder. Do not share your <code>.key</code> file with anyone.</em>
            </p>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(html_content, 'html'))

    # --- ZIP & ATTACHMENT LOGIC ---
    zip_filename = f"{username}_onboarding_kit.zip"
    
    # Strictly using your pre-created files
    files_to_zip = [
        'client.py', 
        'model.py', 
        'requirements.txt', 
        'certs/server.crt', 
        client_crt_path, 
        client_key_path
    ]
    
    try:
        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for file_path in files_to_zip:
                if os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    # Organize certs into a folder inside the zip, keep scripts in root
                    arcname = f"certs/{filename}" if filename.endswith(('.crt', '.key')) else filename
                    zipf.write(file_path, arcname)
                else:
                    print(f"⚠️ Warning: File {file_path} not found. Skipping...")
        
        with open(zip_filename, "rb") as f:
            part = MIMEBase('application', 'zip')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={zip_filename}')
            msg.attach(part)
            
    except Exception as e:
        print(f"❌ Error creating ZIP: {e}")
        return False

    # --- SENDING ---
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        
        # Only remove the temporary ZIP, leave your manual scripts intact
        if os.path.exists(zip_filename): 
            os.remove(zip_filename)
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False


    
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    if not username or not password or not email:
        return jsonify({'message': 'Missing fields'}), 400
    pepper = os.getenv("PASSWORD_PEPPER", "fallback_pepper_just_in_case")
    
    # 2. Combine the password and the pepper
    peppered_password = password + pepper
    
    # 3. Hash the combined string
    hashed_password = generate_password_hash(peppered_password)

    otp = str(random.randint(100000, 999999))
    expiry_time = datetime.datetime.now() + datetime.timedelta(minutes=10)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check if user already exists
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            # If they exist but never verified, overwrite their old abandoned attempt
            if existing_user['status'] == 'UNVERIFIED':
                sql = """UPDATE users 
                         SET password = %s, email = %s, otp = %s, otp_expiry = %s 
                         WHERE username = %s"""
                cursor.execute(sql, (hashed_password, email, otp, expiry_time, username))
            else:
                # If they are already an active/pending user, block the registration
                conn.close()
                return jsonify({'message': 'Username already exists'}), 400
        else:
            # Brand new user, insert them
            sql = """INSERT INTO users (username, password, email, role, status, otp, otp_expiry) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, (username, hashed_password, email, 'HOSPITAL', 'UNVERIFIED', otp, expiry_time))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Error: {e}")
        return jsonify({'message': 'Database error during registration.'}), 500

    # Send the email
    email_sent = send_otp_email(email, otp)
    if email_sent:
        return jsonify({'message': 'OTP sent to your email. Please verify to complete registration.', 'requires_otp': True})
    else:
        return jsonify({'message': 'Failed to send OTP email.'}), 500


@app.route('/verify-register-otp', methods=['POST'])
def verify_register_otp():
    data = request.json
    username = data.get('username')
    user_otp = data.get('otp')

    user_info = get_user_from_db(username)
    if not user_info:
        return jsonify({'message': 'User not found'}), 404

    # Check if OTP matches and is not expired
    if user_info.get('otp') == user_otp:
        if user_info.get('otp_expiry') and user_info.get('otp_expiry') > datetime.datetime.now():
            
            # Clear the OTP and set status to UNAUTHORIZED (waiting for admin approval)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET otp = NULL, otp_expiry = NULL, status = 'UNAUTHORIZED' WHERE username = %s", (username,))
            conn.commit()
            conn.close()

            return jsonify({'message': 'Email verified successfully! You can now log in.'})
        else:
            return jsonify({'message': 'OTP has expired. Please register again.'}), 401
            
    return jsonify({'message': 'Invalid OTP'}), 401


@app.route('/login', methods=['POST'])
def login():
    print("hai")
    auth = request.json
    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'message': 'Missing credentials'}), 400

    username = auth.get('username')
    password = auth.get('password')
    user_info = get_user_from_db(username)

    pepper = os.getenv("PASSWORD_PEPPER", "fallback_pepper_just_in_case")
    
    peppered_password = password + pepper

    if user_info and check_password_hash(user_info['password'], peppered_password):
        # Block login if they haven't verified their email yet
        if user_info.get('status') == 'UNVERIFIED':
            return jsonify({'message': 'Please verify your email before logging in.'}), 403

        # Issue standard JWT token immediately
        token = jwt.encode({
            'user': username,
            'role': user_info['role'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({'token': token, 'role': user_info['role'], 'status': user_info.get('status', 'UNAUTHORIZED')})
    
    return jsonify({'message': 'Invalid credentials'}), 403








@app.route('/request-access', methods=['POST'])
@token_required
def request_access(token_data):
    username = token_data['user']
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = 'PENDING' WHERE username = %s", (username,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Access request sent to Admin.", "status": "PENDING"})
    except Exception as e:
        return jsonify({"message": "Database error"}), 500

@app.route('/admin/pending-users', methods=['GET'])
@token_required
def get_pending_users(token_data):
    if token_data['role'] != 'ADMIN': return jsonify({'message': 'Access Denied'}), 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username, email, status FROM users WHERE role = 'HOSPITAL' AND status = 'PENDING'")
        users = cursor.fetchall()
        conn.close()
        return jsonify(users)
    except Exception as e:
        return jsonify({"message": "Database error"}), 500



@app.route('/admin/authorize-user', methods=['POST'])
@token_required
def authorize_user(token_data):
    if token_data['role'] != 'ADMIN': return jsonify({'message': 'Access Denied'}), 403
    
    data = request.json
    target_user = data.get('username')
    new_status = data.get('status') 
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Update the database status
        cursor.execute("UPDATE users SET status = %s WHERE username = %s", (new_status, target_user))
        
        # 2. If APPROVED, generate certs and send onboarding email
        if new_status == 'APPROVED':
            cursor.execute("SELECT email FROM users WHERE username = %s", (target_user,))
            user_record = cursor.fetchone()
            
            if user_record and user_record.get('email'):
                # 🛡️ GENERATE THE CERTS (This returns the two missing paths)
                key_path, crt_path = generate_hospital_mtls_certs(target_user)
                
                if key_path and crt_path:
                    print(f"📧 Sending onboarding kit to {user_record['email']}...")
                    # ✉️ SEND EMAIL (Passing the captured paths here)
                    send_onboarding_email(
                        receiver_email=user_record['email'], 
                        username=target_user, 
                        client_key_path=key_path, 
                        client_crt_path=crt_path
                    )
                else:
                    print("❌ Failed to generate certificates. Email not sent.")

        conn.commit()
        conn.close()
        return jsonify({"message": f"User {target_user} is now {new_status}."})

    except Exception as e:
        print(f"Authorize Error: {e}")
        return jsonify({"message": "Database error"}), 500

@app.route('/admin/users', methods=['GET'])
@token_required
def get_all_users(token_data):
    if token_data['role'] != 'ADMIN': return jsonify({'message': 'Access Denied'}), 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Fetch all HOSPITAL users regardless of their status
        cursor.execute("SELECT username, email, status FROM users WHERE role = 'HOSPITAL'")
        users = cursor.fetchall()
        conn.close()
        return jsonify(users)
    except Exception as e:
        return jsonify({"message": "Database error"}), 500


@app.route('/admin/delete-user/<username>', methods=['DELETE'])
@token_required
def delete_user(token_data, username):
    if token_data['role'] != 'ADMIN': return jsonify({'message': 'Access Denied'}), 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = %s AND role = 'HOSPITAL'", (username,))
        conn.commit()
        conn.close()
        
        # Remove from active connections if they are currently online
        if username in connected_clients:
            del connected_clients[username]
            
        return jsonify({"message": f"User {username} has been permanently deleted."})
    except Exception as e:
        return jsonify({"message": "Database error"}), 500





# --- Update your Global State at the top of server.py ---
# connected_clients = set()  <-- DELETE THIS

@app.route('/check-in', methods=['POST'])
def check_in():
    # 1. Identity Check (mTLS first, then JWT)
    user = verify_mtls_certificate()
    data = request.get_json(silent=True) or {}

    if not user:
        # Fallback for the Dashboard (JWT)
        user = data.get('hospital')
        if not user:
            token = request.headers.get('x-access-token')
            if token:
                try:
                    decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                    user = decoded['user']
                except: pass

    if not user:
        return jsonify({"message": "Identity verification failed"}), 401

    try:
        # 2. Extract Stats
        cpu_usage = data.get('cpu', 0)
        ram_usage = data.get('ram', 0)

        # 3. Update Global State
        connected_clients[user] = {
            "cpu": cpu_usage,
            "ram": ram_usage,
            "last_seen": datetime.datetime.now().strftime("%H:%M:%S")
        }

        # 🚨 THE FIX: Removed 'if float(cpu_usage) > 0'
        if cpu_usage and ram_usage:
            print(f"🏥 [NETWORK] {user} checked in! | CPU: {cpu_usage}% | RAM: {ram_usage}%", flush=True)
            
        # 4. Trigger Training if ready
        if len(connected_clients) >= CLIENTS_PER_ROUND and training_state["status"] == "WAITING_FOR_CLIENTS":
            print(f"🚀 Threshold met ({len(connected_clients)}/{CLIENTS_PER_ROUND})...", flush=True)
            threading.Thread(target=run_federated_training, daemon=True).start()
            
        return jsonify({"message": "Check-in successful."}), 200

    except Exception as e:
        print(f"❌ Check-in Crash: {str(e)}", flush=True)
        return jsonify({"message": "Internal Server Error"}), 500
    
CLIENTS_PER_ROUND = 2


@app.route('/start-training', methods=['POST'])
@token_required
def start_training_route(token_data):
    if token_data['role'] != 'ADMIN': return jsonify({"message": "Unauthorized"}), 403
    params = request.json or {}
    global CLIENTS_PER_ROUND
    
    # 1. Update the required count from params
    CLIENTS_PER_ROUND = int(params.get('clients_per_round', 2))
    
    # 2. Get the model choice from the request (defaults to 'latest' to preserve old behavior)
    model_choice = params.get('model_choice', 'latest') 
    
    training_state.update({
        "status": "WAITING_FOR_CLIENTS", 
        "current_round": 0, 
        "total_rounds": params.get('total_rounds', 10),
        "accuracy_history": [], 
        "loss_history": [],
        "distance_history": [],
        "distance_history": [],
        "precision_history": [],  # <-- NEW
        "recall_history": [],     # <-- NEW
        "f1_history": [],
        "selected_model": model_choice  # <-- Save the choice here so the thread can see it
    })
    detailed_logs.clear() 
    print(f"Admin initiated training. Minimum clients: {CLIENTS_PER_ROUND} | Model: {model_choice}")
    
    if len(connected_clients) >= CLIENTS_PER_ROUND:
        threading.Thread(target=run_federated_training).start()
        
    return jsonify({"message": f"Training initiated. Waiting for {CLIENTS_PER_ROUND} clients."})

@app.route('/training-status', methods=['GET'])
def training_status():
    status = training_state.copy()
    status['connected_clients'] = list(connected_clients)
    return jsonify(status)

@app.route('/admin/audit-log', methods=['GET'])
@token_required
def get_audit_log_json(token_data):
    if token_data['role'] != 'ADMIN': return jsonify({'message': 'Access Denied'}), 403
    logs = [{
        "index": b.index, "timestamp": datetime.datetime.fromtimestamp(b.timestamp).strftime('%H:%M:%S'),
        "client": b.client_id, "hash": b.hash, "short_hash": b.hash[:10]+"...",
        "status": b.status
    } for b in audit_ledger.chain]
    return jsonify(logs)

@app.route('/admin/verify-integrity', methods=['GET'])
@token_required
def verify_integrity(token_data):
    if token_data['role'] != 'ADMIN': return jsonify({'message': 'Access Denied'}), 403
    return jsonify({'status': 'SECURE', 'message': '✅ Integrity Verified'}) if audit_ledger.is_chain_valid() else jsonify({'status': 'COMPROMISED', 'message': '❌ CRITICAL: Tampering Detected!'})

@app.route('/admin/detailed-logs', methods=['GET'])
@token_required
def get_detailed_logs(token_data):
    if token_data['role'] != 'ADMIN': return jsonify({'message': 'Access Denied'}), 403
    return jsonify(detailed_logs)


@app.route('/predict', methods=['POST'])
@token_required
def predict_image(token_data):
    file = request.files.get('image')
    selected_model = request.form.get('version')  

    models_folder = "model"
    saved_models = []
    if os.path.exists(models_folder):
        for f in os.listdir(models_folder):
            if f.endswith(".pth"):
                saved_models.append({"filename": f})
    saved_models = sorted(saved_models, key=lambda x: x["filename"])  

    if not file:
        return jsonify({"model": saved_models})

    img = Image.open(file).convert('RGB')
    transform = transforms.Compose([
        transforms.Resize((224,224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
    ])
    img = transform(img).unsqueeze(0).to(device)
    print(selected_model,"hasnhiifs")
    if selected_model:
        model_path = os.path.join(models_folder, selected_model)
    elif saved_models:
        model_path = os.path.join(models_folder, saved_models[-1]['filename']) # Use latest
    else:
        return jsonify({'message': 'No trained models available'}), 400

    model = BrainTumorCNN()
    model.to(device)
    try:
        model.load_state_dict(torch.load(model_path, map_location=device))
    except:
        return jsonify({'message': 'Model loading failed'}), 500
        
    model.eval()

    with torch.no_grad():
        outputs = model(img)
        probs = torch.softmax(outputs, dim=1)
        conf, pred_idx = torch.max(probs, 1)

    classes = ['glioma_tumor','meningioma_tumor','no_tumor','pituitary_tumor']
    prediction = classes[pred_idx.item()]
    
    return jsonify({
        'prediction': prediction,
        'confidence': conf.item(),
        'model_used': os.path.basename(model_path),
        'available_models': saved_models
    })

@app.route('/explain', methods=['POST'])
def explain_prediction():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        file = request.files['image']
        img_bytes = file.read()
        pil_img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        input_tensor = transform(pil_img).unsqueeze(0).to(device)
        rgb_img = np.array(pil_img.resize((224, 224)))
        rgb_img = np.float32(rgb_img) / 255

        target_layers = [global_model.conv_layers[6]] 
        cam = GradCAM(model=global_model, target_layers=target_layers)
        grayscale_cam = cam(input_tensor=input_tensor, targets=None)[0, :]
        visualization = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)
        
        pil_viz = Image.fromarray(visualization)
        buff = io.BytesIO()
        pil_viz.save(buff, format="JPEG")
        img_str = base64.b64encode(buff.getvalue()).decode("utf-8")
        
        return jsonify({'status': 'success', 'xai_image': f"data:image/jpeg;base64,{img_str}"})

    except Exception as e:
        print(f"XAI Error: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/admin/refresh-chain', methods=['POST'])
@token_required
def refresh_chain_route(token_data):
    if token_data['role'] != 'ADMIN': 
        return jsonify({'message': 'Access Denied'}), 403

    try:
        audit_ledger.refresh_chain() 
        return jsonify({'message': '✅ Blockchain successfully reloaded from Database!'})
    except Exception as e:
        return jsonify({'message': f'Error refreshing: {str(e)}'}), 500
    
@app.route('/verify-node/<username>', methods=['GET'])
def verify_node(username):
    # This route allows clients to check if they are authorized before booting up
    user_info = get_user_from_db(username)
    
    if user_info and user_info.get('status') == 'APPROVED':
        return jsonify({"message": "Authorized"}), 200
    else:
        return jsonify({"message": "Revoked or Unauthorized"}), 403
@app.route('/che', methods=['GET'])
def che():
    return jsonify({"message": "Authorized"}), 200
def print_model_summary(model):
    # 1. Count trainable parameters (Weights/Biases)
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    # 2. Count total (Params + BatchNorm Buffers)
    all_params = sum(p.numel() for p in model.parameters()) + sum(b.numel() for b in model.buffers())
    
    # 3. Calculate the difference
    non_trainable_params = all_params - trainable_params
    
    # 4. Convert to MB (float32 = 4 bytes)
    total_size_mb = (all_params * 4) / (1024**2)
    trainable_size_mb = (trainable_params * 4) / (1024**2)
    non_trainable_size_mb = (non_trainable_params * 4) / (1024**2)

    # 5. Determine unit for non-trainable display
    if non_trainable_size_mb < 1:
        non_trainable_display = f"{(non_trainable_params * 4) / 1024:.2f} KB"
    else:
        non_trainable_display = f"{non_trainable_size_mb:.2f} MB"

    # 6. Print the summary
    print("\n" + "="*35)
    print("      MODEL ARCHITECTURE STATS")
    print("="*35)
    print(f"Total params:         {all_params:,} ({total_size_mb:.2f} MB)")
    print(f"Trainable params:     {trainable_params:,} ({trainable_size_mb:.2f} MB)")
    print(f"Non-trainable params: {non_trainable_params:,} ({non_trainable_display})")
    print("="*35 + "\n")

def run_federated_training():
    global training_state, global_model
    print("✅ Starting federated training...")
    
    if not audit_ledger.is_chain_valid():
        print("🛑 SECURITY LOCKDOWN: Cannot start training. Ledger is compromised!")
        return jsonify({
            "status": "COMPROMISED", 
            "message": "SECURITY LOCKDOWN: Blockchain integrity failed. Training halted to protect AI model."
        }), 403

    # --- NEW MODEL SELECTION LOGIC ---
    model_choice = training_state.get('selected_model', 'latest')
    
    if model_choice == "new":
        print("✨ Starting from scratch: Initializing a completely NEW global model.")
        global_model = BrainTumorCNN().to(device) # Wipes out old weights
    else:
        if os.path.exists("model"):
            saved_files = sorted([f for f in os.listdir("model") if f.endswith(".pth")])
            if saved_files:
                try:
                    file_to_load = saved_files[-1] # Default to the latest model
                    
                    # If the admin requested a specific file, check if it exists
                    if model_choice != 'latest' and model_choice in saved_files:
                        file_to_load = model_choice
                        
                    global_model.load_state_dict(torch.load(os.path.join("model", file_to_load), map_location=device))
                    print(f"🔄 Resumed from: {file_to_load}")
                except Exception as e:
                    print(f"❌ Failed to load {file_to_load}: {e}")
                    print("⚠️ Falling back to a completely new model.")
                    global_model = BrainTumorCNN().to(device)
    
    print_model_summary(global_model)

    training_state['status'] = 'TRAINING'
    os.makedirs("model", exist_ok=True)

    for r in range(training_state["total_rounds"]):
        training_state['current_round'] = r + 1
        print(f"\n--- Round {r+1} ---")

        if len(connected_clients) < CLIENTS_PER_ROUND: continue

        available_hospital_names = list(connected_clients.keys())
        if len(available_hospital_names) < CLIENTS_PER_ROUND:
            return # Not enough clients
        selected_clients = random.sample(available_hospital_names, CLIENTS_PER_ROUND)
        encoded_chunks = encode_weights_chunks(global_model)
        client_updates = []
        client_losses = []
        client_accuracies = []

        for client_user in selected_clients:
            client_url = CLIENT_CONFIG.get(client_user)
            try:
                # Inside run_federated_training

                print(f"📡 Sending model to {client_user}...")
                response = requests.post(
                    f"{client_url}/train", 
                    json={'weights_chunks': encoded_chunks}, 
                    timeout=1800,
                    cert=('certs/server.crt', 'certs/server.key'),
                    verify='certs/server_ca.crt' 
                )
                # Note: If you get a "Hostname mismatch" error, ensure the client_url 
                # matches the CN (Common Name) you gave the hospital during registration.
            
                if response.status_code == 200:
                    data = response.json()
                    weights = decode_weights_chunks(data['weights_chunks'])
                    client_updates.append({'id': client_user, 'weights': weights})
                    client_losses.append(data.get('loss', 0))
                    client_accuracies.append(data.get('accuracy', 0))
                    print(f"✅ Received update from {client_user}")
            except requests.exceptions.SSLError as e:
                print(f"🔐 SSL Verification Failed for {client_user}: {e}")
            except Exception as e:
                print(f"❌ Connection Failed to {client_user}: {e}")

        if not client_updates: continue

        safe_weights = aggregate_securely(global_model, client_updates, audit_ledger)
        global_model.load_state_dict(safe_weights)

        avg_loss = sum(client_losses) / len(client_losses)
        avg_acc = sum(client_accuracies) / len(client_accuracies)
        training_state["loss_history"].append(avg_loss)
        
        # Inside run_federated_training loop, after evaluate_model call:
        test_acc, test_prec, test_rec, test_f1, report = evaluate_model(global_model, test_loader)

        # Print the pretty table you requested
        print("\n--- Final Classification Report ---")
        print(report)
        print("-----------------------------------\n")

        # Save to global state as usual
        # ... etc
        # Save to global state
        training_state["accuracy_history"].append(test_acc)
        training_state["precision_history"].append(test_prec)
        training_state["recall_history"].append(test_rec)
        training_state["f1_history"].append(test_f1)
        
        print(f"🏁 Round {r+1} Complete | Acc: {test_acc:.2f}% | Prec: {test_prec:.2f}% | Rec: {test_rec:.2f}% | F1: {test_f1:.2f}%")

        torch.save(global_model.state_dict(), f"model/global_model_v{r+1}_acc_{test_acc:.2f}.pth")
        
        del client_updates
        torch.cuda.empty_cache()
        gc.collect()

    training_state['status'] = 'Completed'
    connected_clients.clear()
    print("🏥 Training Completed.")

if __name__ == '__main__':
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    
    # 1. Server's identity
    context.load_cert_chain(certfile='certs/server.crt', keyfile='certs/server.key')
    
    # 2. Tell the server to TRUST clients signed by this specific CA
    context.load_verify_locations(cafile='certs/server_ca.crt') 
    
    # 🚨 THE FIX: Change CERT_REQUIRED to CERT_OPTIONAL
    # This allows web browsers (without certs) to reach the JWT Login page!
    context.verify_mode = ssl.CERT_OPTIONAL 

    print("🛡️ Hybrid Security Active: mTLS for Nodes, JWT for Browsers.")
    app.run(host='0.0.0.0', port=5000, ssl_context=context)