# E-Commerce Project

A comprehensive e-commerce platform built with Django, featuring a custom admin dashboard, extensive product management, package customization, user management, and real-time chat support.
[Demo video](https://youtu.be/pD7XV6CDzqE)
## 📋 Table of Contents
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running the WebSocket Server](#running-the-websocket-server-daphne)
  - [Accessing the Application](#accessing-the-application)
- [Project Structure](#project-structure)
- [Module Descriptions](#module-descriptions)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)
- [Deployment Notes](#deployment-notes)
- [Contact](#contact)

## 🌟 Features

- **Custom Admin Dashboard**
  - Modern, responsive design built with Bootstrap 5
  - Real-time analytics and reporting
  - Role-based access control

- **Product Management**
  - Complete CRUD operations for products
  - Inventory and stock tracking
  - Category organization
  - Image management

- **Order Processing**
  - Order status tracking and management
  - Customer order history
  - Payment integration

- **Package Management**
  - Product bundling with discounts
  - Customizable packages
  - Package-specific pricing

- **Live Chat Support**
  - Real-time customer support
  - WebSocket-based communication
  - Chat history and analytics

- **User Management**
  - User accounts and profiles
  - Address management
  - Order history
  - Social authentication

- **Loyalty System**
  - Customer tier management
  - Rewards and vouchers
  - Anniversary benefits

## 🛠️ Technology Stack

- **Backend**: Django 4.2+
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Database**: MySQL (production), SQLite (development)
- **Real-time**: Django Channels, Daphne, WebSockets
- **Authentication**: Django auth, Social auth (Google)
- **Task Queue**: Celery with Redis
- **Other Tools**: Redis (for WebSockets and caching)

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- pip
- Virtual environment
- Redis server (for WebSockets and Celery)
- MySQL database (or SQLite for development)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/SagitaKDX/E-comerce_Project.git
   cd E-comerce_Project
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Database setup**
   - **Option 1**: MySQL (recommended for production)
     - Create a MySQL database named `ecommerce_db`
     - Ensure credentials in `settings.py` match your MySQL setup
   
   - **Option 2**: SQLite (simpler for development)
     - Modify `settings.py` to use SQLite:
       ```python
       DATABASES = {
           "default": {
               "ENGINE": "django.db.backends.sqlite3",
               "NAME": BASE_DIR / "db.sqlite3",
           }
       }
       ```

5. **Configure environment variables**
   ```bash
   # Create .env file with the following variables
   DEBUG=True
   SECRET_KEY=your-secret-key-here
   EMAIL_HOST_USER=your.email@example.com
   EMAIL_HOST_PASSWORD=your-app-password
   SOCIAL_AUTH_GOOGLE_OAUTH2_KEY=your-google-oauth2-client-id
   SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET=your-google-oauth2-client-secret
   ```

6. **Run migrations**
   ```bash
   python manage.py migrate
   ```

7. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

8. **Start the Django development server**
   ```bash
   python manage.py runserver
   ```

### Running the WebSocket Server (Daphne)

For the live chat functionality to work properly, you need to run the Daphne ASGI server in a separate terminal:

```bash
daphne -b 0.0.0.0 -p 8001 ecommerce_project.asgi:application
```

This will start the WebSocket server on all interfaces (0.0.0.0) at port 8001.

### Accessing the Application

- **Main store**: http://localhost:8000/
- **Admin dashboard**: http://localhost:8000/custom-admin/
- **Django admin**: http://localhost:8000/admin/

## 📁 Project Structure

```
E-comerce_Project/
├── custom_admin/            # Custom admin dashboard app
│   ├── templates/           # Admin dashboard templates
│   ├── views/               # Admin view functions
│   └── forms/               # Admin forms
├── store/                   # Main store functionality
│   ├── models.py            # Database models
│   ├── views.py             # Store views
│   └── templates/           # Store templates
├── livechat/                # Real-time chat functionality
│   ├── consumers.py         # WebSocket consumers
│   └── templates/           # Chat templates
├── templates/               # Global templates
├── static/                  # Static files (CSS, JS, images)
├── media/                   # User uploaded files
└── ecommerce_project/       # Project settings
    ├── settings.py          # Project settings
    ├── urls.py              # Main URL routing
    └── asgi.py              # ASGI configuration
```

## 📚 Module Descriptions

### Custom Admin
The custom admin dashboard provides an intuitive interface for store administrators to manage products, orders, customers, and more. It includes analytics, reporting, and specialized tools for each function.

### Store
The store module handles the customer-facing side of the e-commerce platform, including product listings, shopping cart, checkout process, and user accounts.

### LiveChat
The live chat module enables real-time communication between customers and support staff using WebSockets technology.

## 🔌 API Documentation

### REST API Endpoints

- `/api/products/` - Product listing and details
- `/api/categories/` - Category listing and details
- `/api/orders/` - Order management (authenticated users only)
- `/api/cart/` - Shopping cart operations

### WebSocket Endpoints

- `/ws/chat/{session_id}/` - Live chat WebSocket connection

## 🔧 Troubleshooting

### WebSocket Connection Issues

If you experience issues with the live chat functionality:

1. Make sure the Daphne server is running on port 8001
2. Verify Redis is running (if configured to use Redis)
3. Clear your browser cache or try using incognito mode
4. Check browser console for WebSocket connection errors

### Database Issues

If you encounter database errors:

1. Verify your database credentials in settings.py
2. Check that your MySQL server is running
3. Try using SQLite for simpler development setup

### Common Issues

- **Static files not loading**: Run `python manage.py collectstatic`
- **Migrations errors**: Try `python manage.py makemigrations` before migrating
- **Redis connection errors**: Ensure Redis server is running

## 🌐 Deployment Notes

### Production Settings

For production deployment:

1. Set `DEBUG=False` in your environment
2. Use a production database (MySQL/PostgreSQL)
3. Configure proper email settings
4. Set up a reverse proxy (Nginx/Apache) in front of Daphne
5. Use a process manager (Supervisor/Systemd) for Daphne and Celery

### Deployment Platforms

The project can be deployed on:
- AWS
- DigitalOcean
- Heroku
- PythonAnywhere
- Any VPS or dedicated server

## 📧 Contact

Lê Thanh Minh - [GitHub Profile](https://github.com/SagitaKDX)
