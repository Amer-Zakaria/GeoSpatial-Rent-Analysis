# 🗺️ GeoSpatial Rental Price Prediction

## 📌 Project Overview

This project aims to build an interactive web application that predicts rental prices for properties in Dubai based on geographic coordinates and property features.

Users can click anywhere on a map and receive an estimated rental price powered by a machine learning model.

---

## 🎯 Objectives

* Build an end-to-end machine learning system
* Create an interactive map-based user interface
* Develop a backend API for real-time predictions
* Ensure smooth integration between all components

---

## 🧠 System Workflow

1. User clicks on a location on the map
2. Frontend captures latitude and longitude
3. User optionally provides property details:

   * Bedrooms
   * Bathrooms
   * Property size
4. Frontend sends request to backend API
5. Backend processes input and runs ML model
6. Predicted rental price is returned and displayed

---

## 🏗️ Architecture Suggestion 

Frontend (React + Leaflet)
⬇
Backend API (FastAPI)
⬇
Machine Learning Model (Scikit-learn / XGBoost)

---

## 🔗 API Contract (IMPORTANT)

All components MUST follow this request/response format:

### 📥 Request

```json
{
  "lat": 25.2048,
  "lon": 55.2708,
  "bedrooms": 2,
  "bathrooms": 2,
  "size": 1200
}
```

### 📤 Response

```json
{
  "predicted_price": 85000
}
```

---

## 🧩 Tech Stack

### Frontend

* React
* TypeScript
* Leaflet.js

### Backend

* FastAPI (Python)

### Machine Learning

* Pandas
* Scikit-learn
* XGBoost

### Data

* Dubai Rental Market Dataset (Kaggle)

---

## 👥 Team Structure & Responsibilities

### 🔹 Data & ML
* Data cleaning and preprocessing
* Feature engineering
* Model training and evaluation
* Define required input features (API contract)


### 🔹 Backend
* API development using FastAPI
* Implement `/predict` endpoint
* Apply preprocessing pipeline
* Load and run trained model

### 🔹 Frontend

* Build interactive map interface
* Handle user input
* Call backend API
* Display predictions

---

## 📂 Project Structure (Planned)

```
project-root/
│
├── frontend/        # React application
├── backend/         # FastAPI server
├── ml/              # Model training & notebooks
├── data/            # Dataset (not committed if large)
├── docs/            # Reports and documentation
└── README.md
```

---

## 📈 Future Improvements

* Heatmap visualization of rental prices
* Prediction confidence range
* Advanced feature engineering (geospatial features)
* Model optimization
* Deployment (Vercel + Render)

---

## ⚠️ Notes

* Dataset coordinates may not be highly accurate
* Focus is on system design and integration, not just model accuracy
* Consistency between training and inference pipelines is critical

---
