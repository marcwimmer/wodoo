import os
import tempfile
import time
import shutil

class Interface():
    def getSphinxSource(self):
        return 'hallo'

class ModuleDataDocumentation(Interface):
    pass

class ModuleConfigurationDocumentation(Interface):
    pass

class ModuleDocumentation(Interface):
    def __init__(self, path_module):

    pass

class CustomsDocumentation(Interface):
    pass


if __name__ == '__main__':
    doc = CustomsDocumentation()
    sphinx = doc.getSphinxSource()

    filename = tempfile.mktemp(suffix='.txt')
    with open(filename, 'w') as f:
        f.write(sphinx)
    os.system('terminator -x vim {}'.format(filename))
    print filename
