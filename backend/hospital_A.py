import os
import sys
import requests
import ssl
import argparse
from dotenv import load_dotenv

# Load the .env file that the hospital created
load_dotenv()

# Get the hospital's specific details from their .env file




import random
import torch
import torch.nn as nn
import torch.optim as optim
from flask import Flask, request, jsonify
from flask_cors import CORS
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
import io, gzip, base64, argparse, gc
from model import BrainTumorCNN
import traceback

from flask import request, jsonify
import os
import ssl  # <--- ADD THIS HERE
app = Flask(__name__)
CORS(app)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
client_loader = None
port = None
CHUNK_SIZE = 2_000_000  
HOSPITAL_NAME = os.getenv("HOSA")
SERVER_URL = os.getenv("SERVER_URL", "https://10.103.150.242:5000") # Notice HTTPS!



def get_dataloader(path):
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])
    ])
    dataset = datasets.ImageFolder(root=path, transform=transform)
    return DataLoader(dataset, batch_size=16, shuffle=True, num_workers=0)

def decode_weights_chunks(chunks):
    b64 = ''.join(chunks)
    compressed = base64.b64decode(b64)
    buffer = io.BytesIO(gzip.decompress(compressed))
    state_dict = torch.load(buffer, map_location=device)
    buffer.close()
    return state_dict

def encode_weights_chunks(model):
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer, _use_new_zipfile_serialization=False)
    compressed = gzip.compress(buffer.getvalue())
    buffer.close()
    b64 = base64.b64encode(compressed).decode('utf-8')
    return [b64[i:i+CHUNK_SIZE] for i in range(0, len(b64), CHUNK_SIZE)]


# In client.py

def add_differential_privacy_noise(weights, noise_level=0.01):
    """
    Adds Gaussian Noise to the model weights to protect patient privacy.
    noise_level (epsilon): Higher = More Privacy, but Lower Accuracy.
    """
    noisy_weights = {}
    print(f"🔐 Applying Differential Privacy (Noise: {noise_level})...")
    
    for key, tensor in weights.items():
        # 1. Generate Noise (same shape as the layer)
        noise = torch.randn_like(tensor) * noise_level
        
        # 2. Add Noise to the actual weights
        noisy_weights[key] = tensor + noise
        
    return noisy_weights

# --- INSIDE YOUR TRAINING LOOP ---
# ... after training finishes ...

# Original Code:
# return model.state_dict()

# NEW Code:





@app.route('/receive-global', methods=['POST'])
def receive_global():
    try:
        data = request.get_json()
        chunks = data.get('weights_chunks')
        filename = data.get('filename', 'global_model_received.pth')

        if not chunks:
            return jsonify({'message': 'No chunks provided'}), 400

        b64 = ''.join(chunks)
        compressed = base64.b64decode(b64)
        model_bytes = gzip.decompress(compressed)

        models_dir = "model"
        os.makedirs(models_dir, exist_ok=True)
        path = os.path.join(models_dir, filename)

        with open(path, 'wb') as f:
            f.write(model_bytes)

        try:
            state_dict = torch.load(io.BytesIO(model_bytes), map_location=device)
            local_model = BrainTumorCNN().to(device)
            local_model.load_state_dict(state_dict)
            del local_model, state_dict
        except Exception as load_err:
            print(f"Warning: model saved but loading failed: {load_err}")

        torch.cuda.empty_cache()
        return jsonify({'message': f'Model {filename} saved.'}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'message': f'Error receiving model: {e}'}), 500




@app.route('/train', methods=['POST'])
def train_model():
    global client_loader
    if client_loader is None:
        return jsonify({'error': 'Data loader not initialized'}), 500

    try:
        
        data = request.json
        weights_chunks = data['weights_chunks']
        model_version = data.get('version', f'v{random.randint(1000,9999)}')
        weights = decode_weights_chunks(weights_chunks)

        model = BrainTumorCNN().to(device)
        model.load_state_dict(weights, strict=False)

        model.train()

        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=0.001)
        total_loss, correct, total = 0.0, 0, 0

        for _ in range(2):  # local epochs
            for imgs, labels in client_loader:
                imgs, labels = imgs.to(device), labels.to(device)
                optimizer.zero_grad()
                outputs = model(imgs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                total_loss += loss.item()
                _, predicted = torch.max(outputs.data, 1)
                correct += (predicted == labels).sum().item()
                total += labels.size(0)

        avg_loss = total_loss / max(1, len(client_loader) * 2)
        accuracy = (correct / total) * 100 if total > 0 else 0.0



        clean_weights = model.state_dict()
        
        # 2. Add noise to create protected weights
        # Adjust noise_level: 0.005 is subtle, 0.05 is strong privacy (but drops accuracy)
        protected_weights = add_differential_privacy_noise(clean_weights, noise_level=0.01)
        
        # 3. Load protected weights BACK into the model so we can encode them
        model.load_state_dict(protected_weights)

        # 4. Save the CLEAN model locally (for your records)
        # Note: We save clean_weights, but we SEND protected_weights
        torch.save(clean_weights, f"latest_model_{model_version}.pth")

        # 5. Encode the MODEL (which now holds the Noisy/Protected weights)
        encoded_chunks = encode_weights_chunks(model)





        del model, criterion, optimizer, imgs, labels, outputs, loss
        torch.cuda.empty_cache()
        gc.collect()

        print(f"✅ CLIENT (port {port}) finished training | Loss: {avg_loss:.4f} | Acc: {accuracy:.2f}%")
        return jsonify({'weights_chunks': encoded_chunks, 'loss': avg_loss, 'accuracy': accuracy})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e) or 'Unknown error', 'traceback': traceback.format_exc()}), 500
    



def verify_node_status():
    """Forces the client to check if it is still authorized by the Admin before booting."""
    print(f"🔒 Checking authorization for '{HOSPITAL_NAME}' with Central Server...")
    
    if not HOSPITAL_NAME:
        print("❌ CRITICAL: 'HOSPITAL_NAME' not found in .env file. Shutting down.")
        sys.exit(1)

    try:
        # Ping the server. Since the server requires mTLS, we must pass our certs in the request!
        cert_path = f"certs/{HOSPITAL_NAME}.crt"
        key_path = f"certs/{HOSPITAL_NAME}.key"
        ca_path = "certs/server_ca.crt"

        response = requests.get(
            f"{SERVER_URL}/verify-node/{HOSPITAL_NAME}", 
            cert=(cert_path, key_path), # Present our mTLS identity
            verify=ca_path,             # Verify the server's identity
            timeout=5
        )
        
        if response.status_code == 200:
            print("✅ Node Authorized. Booting up Client Server...")
        else:
            print("❌ CRITICAL: This node has been revoked or deleted by the Admin.")
            print("🛑 Shutting down immediately.")
            sys.exit(1) 
            
    except requests.exceptions.ConnectionError:
        print("⚠️ Cannot reach Central Server (Or mTLS certificates are invalid). Shutting down for security.")
        sys.exit(1)


# 👇 THIS MUST BE FLUSH LEFT (NO INDENTATION) 👇
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--data-path', type=str, required=True)
    args = parser.parse_args()

    port = args.port
    client_loader = get_dataloader(args.data_path)
    
    # Run the Kill Switch before starting Flask!
    verify_node_status()
    
    print(f"🏥 Client '{HOSPITAL_NAME}' started on port {port}, data: {args.data_path}")
    print("🔒 mTLS Strict Enforcement ACTIVE - Waiting for secure Central Server...")

    # 🚨 1. CREATE THE SECURE mTLS CONTEXT 🚨
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.verify_mode = ssl.CERT_REQUIRED
    
    # 🚨 2. LOAD CERTIFICATES DYNAMICALLY BASED ON .env NAME 🚨
    # Use the root CA sent in the email
    context.load_verify_locations('certs/server_ca.crt') 
    
    # Load this specific hospital's keys dynamically
    cert_file = f"certs/{HOSPITAL_NAME}.crt"
    key_file = f"certs/{HOSPITAL_NAME}.key"
    
    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        print(f"❌ CRITICAL: Certificates not found for {HOSPITAL_NAME}. Check your certs folder.")
        sys.exit(1)

    context.load_cert_chain(certfile=cert_file, keyfile=key_file)

    # 🚨 3. RUN FLASK WITH THE SECURE CONTEXT 🚨
    app.run(host='0.0.0.0', port=port, ssl_context=context, debug=False, use_reloader=False)