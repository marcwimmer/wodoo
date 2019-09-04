# install the apport exception handler if available
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

try:
    import apport_python_hook
except ImportError:
    pass
else:
    apport_python_hook.install()
