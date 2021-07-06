import tempfile
import base64
from pathlib import Path
from odoo import _, api, fields, models, SUPERUSER_ID
import tempfile
from pathlib import Path
from odoo import _, api, fields, models, SUPERUSER_ID
from io import BufferedReader, BytesIO
from odoo.tools import convert_xml_import, convert_csv_import

from odoo.exceptions import UserError, RedirectWarning, ValidationError

class DataLoader(models.AbstractModel):
    _name = 'robot.data.loader'

    @api.model
    def put_file(self, filecontent, dest_path):
        content = base64.b64decode(filecontent)
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(exist_ok=True, parents=True)
        dest_path.write_bytes(content)
        return True

    @api.model
    def load_data(self, content, file_type, module_name, filename):
        """Does basically the same like what at update happens when installing a module and 
        loads the xml and csv files.

        Args:
            content ([string]): filecontent
            file_type (string): csv or xml
            module_name (string): faked module name
            filename (string): 

        """

        filepath = Path(tempfile.mkstemp(suffix=file_type)[1])
        filepath.write_text(content)
        try:
            if file_type == '.xml':
                with open(filepath, 'rb') as file:
                    convert_xml_import(
                        self.env.cr,
                        module_name,
                        file,
                        idref={},
                        noupdate=False,
                    )
            elif file_type == '.csv':
                convert_csv_import(
                    cr=self.env.cr,
                    module=module_name,
                    fname=Path(filename).name,
                    csvcontent=content.encode('utf-8')
                )
        finally:
            filepath.unlink()

        return True