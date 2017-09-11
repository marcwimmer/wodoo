from datetime import datetime
import module_tools

module_tools.is_module_listed_in_install_file_or_in_dependency_tree('partner_academic_title')
from pudb import set_trace
set_trace()
module_tools.is_module_listed_in_install_file_or_in_dependency_tree('cpb_crm')





#-----------------------------------------
from pudb import set_trace
set_trace()

S = datetime.now()
manifests = list(module_tools.get_all_manifests())

print datetime.now() - S
print len(manifests)

for m in [x for x in manifests if 'cpb_crm' in x]:
    tree = module_tools.get_module_dependency_tree(m, manifests)
    flat_tree = module_tools.get_module_flat_dependency_tree(m, manifests)
    from pudb import set_trace
    set_trace()
