#!/usr/bin/env python
"""
Run Django development server with Daphne for WebSocket support.
This script replaces the standard runserver command with Daphne,
which can properly handle WebSocket connections.
"""

import os
import sys
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce_project.settings')
django.setup()

# Import after Django setup
from daphne.cli import CommandLineInterface

if __name__ == "__main__":
    print("\n=== Starting Daphne Development Server with WebSocket Support ===\n")
    print("WebSocket connections will be available at ws://localhost:8000/ws/...")
    print("Press Ctrl+C to stop the server\n")
    
    # Automatically collect static files
    from django.core.management import call_command
    call_command('collectstatic', '--no-input')
    
    # Run the Daphne server
    sys.argv = ["daphne", "-p", "8000", "-b", "0.0.0.0", "ecommerce_project.asgi:application"]
    CommandLineInterface().run(sys.argv[1:]) 