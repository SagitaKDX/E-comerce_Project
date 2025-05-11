# Custom Admin Dashboard for E-Shop

This is a custom admin dashboard for the E-Shop Django application. It provides a user-friendly interface for managing products, categories, users, orders, and viewing analytics.

## Features

- **Dashboard Overview**: Quick stats and charts showing key metrics
- **Product Management**: Add, edit, delete, and view products
- **Category Management**: Add, edit, delete, and view categories
- **User Management**: Add, edit, delete, and view users
- **Order Management**: View and update order statuses
- **Analytics**: View sales charts, product popularity, and other metrics

## Installation

1. Make sure the `custom_admin` app is added to `INSTALLED_APPS` in `settings.py`
2. Run migrations: `python manage.py migrate`
3. Collect static files: `python manage.py collectstatic`
4. Access the dashboard at `/custom-admin/`

## Usage

- Login with admin credentials
- Navigate through the sidebar to access different sections
- Use the search and filter options to find specific items
- View detailed information by clicking on items
- Use the analytics section to gain insights into sales and performance

## Dependencies

- Bootstrap 5
- Font Awesome
- Chart.js
- ApexCharts (for advanced visualizations)

## Notes

This custom admin dashboard is designed to complement or replace the default Django admin interface for a more user-friendly experience.