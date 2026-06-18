import os
import subprocess
import shutil

# --- PROJECT CONFIGURATION ---
TEAM_ORG = "A3K"
BATCH_UNIT = "GEC SKP 22-26 CSE"
ISSUER_NAME = "AKSHAY T S"

# Everything in your message, consolidated
# --- UPDATE THIS SECTION IN YOUR SCRIPT ---
SAN_LIST = [
    "laptop-3hb2ene1",                 # <--- Added specifically for your error
    "fedora",                          # Shorthand for your other node
    "laptop-3hb2ene1.tailca8536.ts.net",
    "fedora.tail917d49.ts.net",
    "100.94.68.3",
    "100.80.113.9",
    "100.80.113.8",
    "100.94.68.4",
    "localhost",
    "127.0.0.1"
]

def generate_certs():
    if os.path.exists("certs"):
        shutil.rmtree("certs")
    os.makedirs("certs", exist_ok=True)
    
    with open("certs/ca_ext.conf", "w") as f:
        f.write("[ v3_ca ]\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always,issuer\nbasicConstraints = critical,CA:TRUE\nkeyUsage = critical, digitalSignature, cRLSign, keyCertSign\n")

    # Build DNS and IP lists separately for the config file
    dns_entries = []
    ip_entries = []
    
    dns_count = 1
    ip_count = 1
    
    for entry in SAN_LIST:
        # Check if entry is an IP address
        if entry.replace('.', '').isdigit():
            ip_entries.append(f"IP.{ip_count} = {entry}")
            ip_count += 1
        else:
            dns_entries.append(f"DNS.{dns_count} = {entry}")
            dns_count += 1

    san_content = "\n".join(dns_entries + ip_entries)

    with open("certs/san.conf", "w") as f:
        f.write(f"""
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = Federated-Node-Network
O = {TEAM_ORG}
OU = {BATCH_UNIT}

[v3_req]
subjectAltName = @alt_names

[alt_names]
{san_content}
""")

    # --- EXECUTION ---
    print(f"👑 Generating Root CA...")
    subprocess.run(["openssl", "req", "-x509", "-new", "-nodes", "-keyout", "certs/server_ca.key", "-sha256", "-days", "3650", "-out", "certs/server_ca.crt", "-subj", f"/CN={ISSUER_NAME}/O={TEAM_ORG}/OU={BATCH_UNIT}", "-extensions", "v3_ca", "-config", "certs/ca_ext.conf"], check=True)

    print(f"🖥️ Generating Server Cert Request...")
    subprocess.run(["openssl", "req", "-new", "-nodes", "-keyout", "certs/server.key", "-out", "certs/server.csr", "-config", "certs/san.conf"], check=True)

    print("✍️ Signing Certificate for the whole network...")
    subprocess.run(["openssl", "x509", "-req", "-in", "certs/server.csr", "-CA", "certs/server_ca.crt", "-CAkey", "certs/server_ca.key", "-CAcreateserial", "-out", "certs/server.crt", "-days", "365", "-sha256", "-extensions", "v3_req", "-extfile", "certs/san.conf"], check=True)
    
    print("\n✅ Success! This certificate is now valid for all your listed IPs and Domains.")

if __name__ == "__main__":
    generate_certs()