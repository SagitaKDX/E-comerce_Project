# E-Commerce Project

A comprehensive e-commerce platform with custom admin dashboard, extensive product management, package customization, user management, and real-time chat support built with Django.

## Features

- **Custom Admin Dashboard**: Modern, responsive design with Bootstrap 5
- **Product Management**: Complete CRUD operations for products with stock tracking
- **Order Processing**: Order status tracking and customer management
- **Package Management**: Product bundles with customization options
- **Live Chat**: Real-time WebSocket-based customer support
- **User Management**: User accounts, profiles, and address management
- **Loyalty System**: Customer loyalty tiers and rewards

## Technology Stack

- **Backend**: Django 4.2+
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Database**: SQLite (development), MySQL/PostgreSQL (production)
- **Real-time**: Django Channels with WebSockets
- **Authentication**: Django auth with social login

## Getting Started

### Prerequisites
- Python 3.8+
- pip
- Virtual environment
- Redis server (for WebSockets)

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/SagitaKDX/E-comerce_Project.git
   cd E-comerce_Project
   ```

2. Set up virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables
   ```bash
   # Create .env file based on .env.example
   cp .env.example .env
   # Edit .env with your settings
   ```

5. Run migrations
   ```bash
   python manage.py migrate
   ```

6. Create superuser
   ```bash
   python manage.py createsuperuser
   ```

7. Start the server
   ```bash
   python manage.py runserver
   ```

8. For WebSocket support (chat feature), run
   ```bash
   python run_daphne.py  # In a separate terminal
   ```

## Project Structure

```
E-comerce_Project/
├── custom_admin/            # Custom admin dashboard app
├── store/                   # Main store functionality
├── livechat/                # Real-time chat functionality
├── templates/               # Global templates
├── static/                  # Static files
├── media/                   # User uploaded files
└── ecommerce_project/       # Project settings
```

## Contact

Lê Thanh Minh - [GitHub Profile](https://github.com/SagitaKDX)
