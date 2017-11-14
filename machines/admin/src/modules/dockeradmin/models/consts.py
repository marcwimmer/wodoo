import os
import re
DEPLOY_BRANCH = os.environ['DEPLOY_BRANCH']
MASTER_BRANCH = os.environ['MASTER_BRANCH']
ADMIN_BRANCHES_REGEX = os.environ['ADMIN_BRANCHES_REGEX'] or []

if ADMIN_BRANCHES_REGEX:
    a = []
    for x in ADMIN_BRANCHES_REGEX.split(";"):
        a.append(re.compile(x))
    ADMIN_BRANCHES_REGEX = a
