#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path
import inspect
import os
from pathlib import Path
current_dir = Path(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))))
os.environ['PYTHONPATH'] = str(current_dir / 'wodoo')

from wodoo import cli
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe)?$', '', sys.argv[0])
    sys.exit(cli())
