import os
import sys
import time
import threading
import requests
import ssl
import argparse
import psutil
import torch
import torch.nn as nn
import torch.optim as optim
import io, gzip, base64, gc, random, traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
from dotenv import load_dotenv
from model import BrainTumorCNN

# 1. LOAD CONFIGURATION
load_dotenv()
HOSPITAL_NAME = os.getenv("HOSPITAL_NAME")
# Use the Tailscale hostname we configured in the certificates
SERVER_URL = os.getenv("SERVER_URL", "https://laptop-3hb2ene1:5000") 

# Pathing (Unified)
CERT_PATH = f"certs/{HOSPITAL_NAME}.crt"
KEY_PATH = f"certs/{HOSPITAL_NAME}.key"
CA_PATH = "certs/server_ca.crt"

app = Flask(__name__)
CORS(app)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Global state for training
client_loader = None
CHUNK_SIZE = 500_000 

# --- BACKGROUND HEARTBEAT ---

def start_heartbeat():
    """Tells the server Hospital B is online and sends resource stats."""
    print(f"🛰️ Heartbeat started for {HOSPITAL_NAME}...")
    while True:
        try:
            # interval=1 is critical for Linux/Fedora to get a non-zero reading
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            
            response = requests.post(
                f"{SERVER_URL}/check-in",
                json={
                    "hospital": HOSPITAL_NAME, 
                    "cpu": cpu, 
                    "ram": ram
                },
                cert=(CERT_PATH, KEY_PATH),
                verify=CA_PATH,
                timeout=5
            )
            
            if response.status_code == 200:
                # Optional: uncomment for local debugging
                # print(f"✅ Heartbeat sent: CPU {cpu}%") 
                pass
            else:
                print(f"⚠️ Server rejected heartbeat: {response.status_code}")

        except requests.exceptions.SSLError as e:
            print(f"🔐 Heartbeat SSL Error: Check if server_ca.crt matches the server's cert.")
        except Exception as e:
            print(f"🛰️ Heartbeat failed to connect: {e}")
            
        time.sleep(15) # Check in every 15 seconds for the dashboard
def add_differential_privacy_noise(weights, noise_level=0.01):
    """Adds Gaussian Noise to weights to protect patient privacy (DP)."""
    noisy_weights = {}
    for key, tensor in weights.items():
        noise = torch.randn_like(tensor) * noise_level
        noisy_weights[key] = tensor + noise
    return noisy_weights

def decode_weights_chunks(chunks):
    b64 = ''.join(chunks)
    compressed = base64.b64decode(b64)
    buffer = io.BytesIO(gzip.decompress(compressed))
    state_dict = torch.load(buffer, map_location=device)
    return state_dict

def encode_weights_chunks(model_state):
    buffer = io.BytesIO()
    torch.save(model_state, buffer, _use_new_zipfile_serialization=False)
    compressed = gzip.compress(buffer.getvalue())
    b64 = base64.b64encode(compressed).decode('utf-8')
    return [b64[i:i+CHUNK_SIZE] for i in range(0, len(b64), CHUNK_SIZE)]

# --- BACKGROUND HEARTBEAT (The Missing Link) ---

@app.route('/train', methods=['POST'])
def train_model():
    global client_loader
    if client_loader is None:
        return jsonify({'error': 'Data loader not initialized'}), 500

    try:
        data = request.json
        weights = decode_weights_chunks(data['weights_chunks'])
        
        # Initialize and Train
        model = BrainTumorCNN().to(device)
        model.load_state_dict(weights, strict=False)
        model.train()

        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=0.001)

        # Local training loop (2 epochs)
        for _ in range(2):
            for imgs, labels in client_loader:
                imgs, labels = imgs.to(device), labels.to(device)
                optimizer.zero_grad()
                outputs = model(imgs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

        # 🔐 APPLY PRIVACY PROTECTION
        clean_weights = model.state_dict()
        protected_weights = add_differential_privacy_noise(clean_weights, noise_level=0.01)

        # Encode the NOISY weights to send back
        encoded_chunks = encode_weights_chunks(protected_weights)

        # Cleanup
        del model, weights, clean_weights, protected_weights
        torch.cuda.empty_cache()
        gc.collect()

        return jsonify({'weights_chunks': encoded_chunks, 'status': 'success'})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def verify_node_status():
    """The 'Kill Switch': Checks if the Admin has approved this node."""
    print(f"🔒 Verifying mTLS identity with {SERVER_URL}...")
    try:
        response = requests.get(
            f"{SERVER_URL}/verify-node/{HOSPITAL_NAME}", 
            cert=(CERT_PATH, KEY_PATH),
            verify=CA_PATH,
            timeout=10
        )
        if response.status_code != 200:
            print("❌ NODE REVOKED: This node is not authorized to join the federation.")
            sys.exit(1)
        print("✅ Node Verified.")
    except Exception as e:
        print(f"❌ CONNECTION ERROR: Could not reach central server. {e}")
        sys.exit(1)

# --- BOOT LOGIC ---

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--data-path', type=str, required=True)
    args = parser.parse_args()

    # 1. Load Data
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])
    ])
    dataset = datasets.ImageFolder(root=args.data_path, transform=transform)
    client_loader = DataLoader(dataset, batch_size=16, shuffle=True)

    # 2. Security Check (Kill Switch)
    verify_node_status()

    # 3. Start Heartbeat Thread
    threading.Thread(target=start_heartbeat, daemon=True).start()

    # 4. Prepare SSL Context for Flask
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(CA_PATH)
    context.load_cert_chain(certfile=CERT_PATH, keyfile=KEY_PATH)

    print(f"🏥 Hospital {HOSPITAL_NAME} online at https://0.0.0.0:{args.port}")
    app.run(host='0.0.0.0', port=args.port, ssl_context=context, debug=False)