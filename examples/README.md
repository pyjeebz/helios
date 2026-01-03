# Helios Examples

This directory contains demo environments and examples for testing and demonstrating Helios capabilities.

> **Note**: These are NOT part of the core Helios product. They are for internal testing and customer demos only.

## Contents

### demo-environment/

A complete test environment with:

- **kubernetes/saleor/** - Demo e-commerce application (Saleor)
- **kubernetes/locust/** - Load testing infrastructure
- **loadtest/** - Locust test scripts and configurations
- **data/** - Sample data generated from load tests

## Usage

### Deploy Demo Environment

```bash
# Deploy Saleor demo app
kubectl apply -k examples/demo-environment/kubernetes/saleor/overlays/dev/

# Deploy Locust for load testing
kubectl apply -k examples/demo-environment/kubernetes/locust/
```

### Run Load Tests

```bash
# Port-forward Locust UI
kubectl port-forward svc/locust-master 8089:8089 -n locust

# Open http://localhost:8089
```

## Purpose

| Component | Purpose |
|-----------|---------|
| **Saleor** | Generates realistic e-commerce traffic patterns |
| **Locust** | Creates controlled load for testing predictions |
| **Data** | Training data for ML model development |

## What Ships to Customers

Customers receive only the **core Helios product**:

```
helios/
├── ml/                      # ✅ Core ML pipeline
│   ├── inference/           # ✅ Prediction API
│   ├── cost_intelligence/   # ✅ Cost analysis
│   └── models/              # ✅ ML models
│
└── infra/kubernetes/
    ├── helios-inference/    # ✅ Deploy to customers
    ├── helios-cost/         # ✅ Deploy to customers
    └── keda/                # ✅ Scaling integration
```

The `examples/` directory stays internal for development and demos.
