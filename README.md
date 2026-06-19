# Privacy-Preserving Federated Learning for Brain Tumor Classification

## Overview

This project implements a secure Federated Learning (FL) framework for Brain Tumor Classification using MRI images. Multiple hospitals collaboratively train a shared deep learning model without sharing patient data, ensuring privacy, security, and regulatory compliance.

The system integrates Federated Learning, Differential Privacy, Mutual TLS (mTLS), Byzantine Fault Tolerance, Blockchain-Based Audit Logging, and Explainable AI (XAI) to create a secure healthcare AI ecosystem.

---

## Features

### Federated Learning

* Distributed model training across multiple hospitals
* Raw patient data never leaves local hospital servers
* Centralized model aggregation using Federated Averaging (FedAvg)

### Privacy Preservation

* Local Differential Privacy (LDP)
* Gaussian noise injection before transmitting model updates
* Protection against patient data leakage

### Secure Communication

* Mutual TLS (mTLS) authentication
* Client and server certificate verification
* Encrypted communication channels

### Byzantine Fault Tolerance

* Detection of malicious or abnormal model updates
* Gradient distance analysis
* Accuracy-based validation of client contributions

### Blockchain Audit Ledger

* Tamper-resistant logging of model updates
* Records accepted and rejected client contributions
* Ensures accountability and traceability

### Explainable AI (XAI)

* Grad-CAM visualization support
* Provides visual explanations for model predictions
* Improves transparency in medical diagnosis

### Hospital Management System

* Hospital registration
* OTP-based email verification
* Admin approval workflow
* Node authorization and revocation

### Monitoring Dashboard

* Real-time client connectivity tracking
* CPU and RAM utilization monitoring
* Training progress visualization

---

## System Architecture

```text
                    +------------------+
                    |     Frontend     |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    |  Central Server  |
                    |   (Aggregator)   |
                    +--------+---------+
                             |
         -----------------------------------------
         |                                       |
         v                                       v

 +----------------+                   +----------------+
 |   Hospital A   |                   |   Hospital B   |
 | Local Dataset  |                   | Local Dataset  |
 | Local Training |                   | Local Training |
 +-------+--------+                   +-------+--------+
         |                                    |
         +---------- Secure mTLS -------------+
```

---

## Technology Stack

### Backend

* Python
* Flask
* Flask-CORS

### Machine Learning

* PyTorch
* Torchvision

### Security

* Mutual TLS (mTLS)
* JWT Authentication
* Differential Privacy

### Database

* MySQL

### Explainable AI

* Grad-CAM

### Monitoring

* Psutil

---

## Dataset

Brain Tumor MRI Classification Dataset containing four classes:

* Glioma Tumor
* Meningioma Tumor
* Pituitary Tumor
* No Tumor

Dataset images are organized using the following structure:

```text
data/
└── Train/
    ├── glioma_tumor/
    ├── meningioma_tumor/
    ├── no_tumor/
    └── pituitary_tumor/
```

---

## Deep Learning Model

Custom CNN Architecture:

* 3 Convolutional Layers
* ReLU Activation
* Max Pooling
* Fully Connected Layers
* 4-Class Softmax Output

Input Size:

```text
224 × 224 × 3
```

Output Classes:

```text
Glioma
Meningioma
No Tumor
Pituitary
```

---

## Security Workflow

### Node Authentication

1. Hospital registers through portal.
2. OTP verification completed.
3. Admin reviews request.
4. Server generates mTLS certificates.
5. Certificates delivered securely.
6. Hospital joins federation.

### Secure Communication

```text
Hospital Certificate
        ⇅
      mTLS
        ⇅
Server Certificate
```

Both parties verify each other's identity before communication.

---

## Federated Learning Workflow

### Step 1

Server initializes global model.

### Step 2

Global model distributed to hospitals.

### Step 3

Hospitals perform local training.

### Step 4

Differential Privacy noise applied.

### Step 5

Model updates returned securely.

### Step 6

Server validates updates.

### Step 7

FedAvg aggregation performed.

### Step 8

Blockchain audit log updated.

### Step 9

Updated global model redistributed.

---

## Project Structure

```text
project/
│
├── server.py
├── client.py
├── model.py
├── requirements.txt
│
├── certs/
│   ├── server_ca.crt
│   ├── hospital_a.crt
│   ├── hospital_a.key
│   ├── hospital_b.crt
│   └── hospital_b.key
│
├── model/
│   └── saved_models/
│
├── data/
│   ├── Train/
│   └── Test/
│
└── frontend/
```

---

## Installation

### Clone Repository

```bash
git clone https://github.com/your-username/federated-learning-healthcare.git
cd federated-learning-healthcare
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Server Configuration

Create a `.env` file:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=fl_audit_db

FLASK_SECRET=your_secret_key

SMTP_EMAIL=your_email
SMTP_PASSWORD=your_password
```

Run Server:

```bash
python server.py
```

---

## Hospital Configuration

Create `.env`

```env
HOSPITAL_NAME=hospital_a
SERVER_URL=https://server-ip:5000
```

Run Client:

```bash
python client.py --port 5001 --data-path ./data/Train
```

Hospital B:

```bash
python client.py --port 5002 --data-path ./data/Train
```

---

## Security Features

| Feature              | Purpose                      |
| -------------------- | ---------------------------- |
| Federated Learning   | Data never leaves hospitals  |
| Differential Privacy | Prevents information leakage |
| mTLS                 | Mutual authentication        |
| JWT                  | User authentication          |
| Blockchain Ledger    | Audit trail                  |
| Byzantine Detection  | Rejects malicious updates    |
| OTP Verification     | Secure onboarding            |

---

## Future Enhancements

* Secure Aggregation
* Homomorphic Encryption
* Differential Privacy Budget Tracking
* Dynamic Client Selection
* Docker Deployment
* Kubernetes Support
* Multi-Hospital Scaling
* Production-Grade Certificate Management

---

## Authors

Final Year B.Tech Computer Science and Engineering Project

Government Engineering College Palakkad

### Team Members

* Krishnadev PV

---

## License

This project is developed for academic and research purposes.
