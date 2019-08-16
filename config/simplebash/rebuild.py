#!/usr/bin/env python3
from pathlib import Path
import subprocess
import os
PROJECT_NAME = os.environ['PROJECT_NAME']
print(PROJECT_NAME)
CURRENT_DIR = Path(__file__).parent
subprocess.check_call([
    'docker',
    'build',
    '--no-cache',
    '--tag',
    '{}_simplebash'.format(PROJECT_NAME),
    '.',
], cwd=str(CURRENT_DIR))
subprocess.check_call([
    'docker-compose',
    '-f',
    'docker-compose.yml',
    'build',
    'simplebash',
], cwd=CURRENT_DIR)
