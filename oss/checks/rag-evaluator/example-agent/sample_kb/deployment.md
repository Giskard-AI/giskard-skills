# Deployment Guide

Acme Analytics runs on **Google Cloud Platform (GCP)** only.

Production deploys use Cloud Run in `us-central1`. Staging uses `europe-west1`.

We do **not** support AWS or Azure deployments. Do not follow AWS-specific guides for this product.

CI/CD is GitHub Actions → Artifact Registry → Cloud Run.
