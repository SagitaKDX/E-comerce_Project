import os
import sys
import subprocess
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Runs the Daphne ASGI server for both HTTP and WebSocket on port 8000'

    def add_arguments(self, parser):
        parser.add_argument(
            '--port',
            default='8000',
            help='Port for Daphne server'
        )
        parser.add_argument(
            '--host',
            default='0.0.0.0',
            help='Host for Daphne server'
        )

    def handle(self, *args, **options):
        port = options['port']
        host = options['host']

        self.stdout.write(self.style.SUCCESS(
            f'Starting Daphne ASGI server at {host}:{port}'
        ))
        
        # Prepare the daphne command
        cmd = [
            sys.executable, '-m', 'daphne',
            '-b', host,
            '-p', port,
            '--verbosity', '2',
            '--access-log', '-',
            'ecommerce_project.asgi:application'
        ]

        # Execute the daphne command in the foreground
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f'Daphne server failed: {e}'))
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS('Daphne server stopped')) 