from odoo import api
import os
from pathlib import Path
import time
import subprocess
import tempfile
from PIL import ImageFont
import xlsxwriter
from copy import deepcopy
from io import BytesIO
from datetime import datetime
from odoo import _, models

class ExcelMaker(models.AbstractModel):
    _name = 'excel.maker'

    background_colors = {
        0: '#EEEEEE',
        1: '#DDDDDD',
        2: '#AAAAAA',
        3: '#999999',
        4: '#666666',
        5: '#555555',
        6: '#444444',
        7: '#333333',
    }

    @api.model
    def auto_fit_columns(self, binary_stream_content):
        try:
            import uno
            import unohelper
            from com.sun.star.beans import PropertyValue
        except ModuleNotFoundError:
            return binary_stream_content
        filename = Path(tempfile.mktemp(suffix='.xlsx'))
        filename.write_bytes(binary_stream_content)

        def resize_spreadsheet_columns(controller, oSheet):
            controller.setActiveSheet(oSheet)
            columns = oSheet.getColumns()
            oSheet.getRows()[0].OptimalHeight = True
            columns.OptimalWidth = False
            for i in range(len(columns)):
                cell = oSheet.getCellByPosition(i, 0)
                if not cell.String:
                    break
                oColumn = columns.getByIndex(i)
                print(oColumn.Width)
                oColumn.OptimalWidth = True
                print(oColumn.Width)
                print("------------")
        # get the uno component context from the PyUNO runtime
        localContext = uno.getComponentContext()

        # create the UnoUrlResolver
        resolver = localContext.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", localContext)

        # connect to the running office
        ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext")
        smgr = ctx.ServiceManager

        # get the central desktop object
        desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)

        doc = desktop.loadComponentFromURL("file://{}".format(filename), "_blank", 0, ())

        # access the current writer document
        model = desktop.getCurrentComponent()
        controller = model.getCurrentController()

        sheets = model.getSheets().createEnumeration()
        for sheet in sheets:
            resize_spreadsheet_columns(controller, sheet)

        args = (PropertyValue('FilterName', 0, 'Calc MS Excel 2007 XML', 0),)
        filename.unlink()
        filename = tempfile.mktemp(suffix='.xlsx')
        doc.storeToURL("file://{}".format(filename), args)
        doc.dispose()

        filename = Path(filename)
        content = filename.read_bytes()
        filename.unlink()
        return content

    @api.model
    def get_workbook(self, constant_memory=False):
        output = BytesIO()
        wb = xlsxwriter.Workbook(output, {'constant_memory': constant_memory})
        default_styles = {}

        default_styles['bold'] = {'bold': 1}
        default_styles['0'] = {'num_format': u"#,##0.00;[RED]-#,##0.00"}
        default_styles['int'] = {'num_format': u"#,##0;[RED]-#,##0"}
        default_styles['%'] = {'num_format': '#,##.0"%";[RED]-#,##.0"%"'}
        default_styles['small_%'] = {'num_format': '#,##.000"%";[RED]-#,##.000"%"'}
        default_styles['default'] = {}
        default_styles['$'] = {'num_format': u"#,##0.00 [$€-407];[RED]-#,##0.00 [$€-407]"}

        styles = {}
        for i in range(len(self.background_colors)):  # all levels
            styles.setdefault(i, {})
            for k, v in default_styles.items():
                v = deepcopy(v)
                v['bg_color'] = self.background_colors[i]
                styles[i][k] = wb.add_format(v)
        for key in list(default_styles.keys()):
            default_styles[key] = wb.add_format(default_styles[key])

        def get_style(level, stylename):
            if level is None:
                return default_styles[stylename]
            if stylename in styles[level]:
                return styles[level][stylename]
            else:
                return styles[level]['default']
        wb.get_style = get_style

        return wb, output

    @api.model
    def get_default_styles(self, wb):
        styles = {}
        return styles

    @api.model
    def create_excel(self, env, data, internal_column_names=False):
        """
        :param data: {'sheet_name': {'records': [], 'columns', 'model': }}
        :param model: model object
        :param columns: column headings
        :param records: array of dict
        :returns:

        """
        assert isinstance(data, dict)
        wb, output = self.get_workbook()

        for sheet_name in data.keys():
            assert isinstance(sheet_name, str)
            data_sheet = data[sheet_name]
            records = data_sheet['records']
            columns = data_sheet.get('columns', [])
            if not columns and records:
                columns = sorted(records[0].keys())
            model = None
            try:
                model = data_sheet['model']
            except KeyError:
                try:
                    model = records._name
                except AttributeError:
                    pass
            if model:
                model = env[model]

            if len(sheet_name) > 31:
                sheet_name = sheet_name[:31]

            # remove invalid characters
            for c in "'\\[]:*?/":
                sheet_name = sheet_name.replace(c, "_")

            ws = wb.add_worksheet(sheet_name)
            default_style = {
                'font': u"LiberationSans-Regular",
                'font_size': 10,
            }
            lang = env['res.lang']._lang_get(env.user.lang)

            def _get_format(t):
                return {
                    'num_format': getattr(lang, 'excel_format_{}'.format(t))
                }
            number_format = _get_format('num')
            date_format = _get_format('date')

            def write_header(start_row):
                for j, col in enumerate(columns):
                    if isinstance(col, (tuple, list)):
                        if col[1]:
                            col = col[1]
                        else:
                            col = col[0]
                    style = wb.get_style(0, 'bold')
                    column_header = col
                    if model:
                        try:
                            getattr(model, '_name')
                        except Exception:
                            pass
                        else:
                            column = model._fields.get(col, col)

                            if internal_column_names:
                                column_header = col
                            else:
                                column_header = (column if isinstance(column, str) else column.string) or ''
                    ws.write(start_row, j, column_header, style)

                return start_row + 1

            def print_row(record, row_counter):

                for j, c in enumerate(columns):
                    forced_type = False
                    if isinstance(c, (tuple, list)):
                        if len(c) > 2:
                            forced_type = c[2]
                    if isinstance(c, (tuple, list)):
                        c = c[0]
                    v = record[c]
                    format = deepcopy(default_style)
                    try:

                        if isinstance(v, list):
                            if not v:
                                v = False

                        if isinstance(v, models.AbstractModel):
                            v = ','.join((x.name_get()[0][1] or '') for x in v)

                        if not forced_type and forced_type != "text":
                            if isinstance(v, str) and v.isdigit():
                                v = float(v)
                        elif forced_type in ["int", "integer", "money"]:
                            if isinstance(v, str) and v.isdigit():
                                v = int(v)

                        if isinstance(v, (tuple,)) and len(v) == 2:
                            v = v[1]

                        if v is False and forced_type != "boolean":
                            v = ""

                        if v is True:
                            v = _("Yes")

                        if v is False:
                            v = _("No")

                        if not forced_type:
                            try:
                                v = datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
                                format.update(date_format)
                            except (ValueError, TypeError):
                                try:
                                    v = datetime.strptime(v, "%Y-%m-%d")
                                    format.update(date_format)
                                except (ValueError, TypeError):
                                    pass
                            if isinstance(v, float):
                                format.update(number_format)
                        else:
                            if forced_type == 'money':
                                format.update(_get_format('money'))
                            else:
                                format.update(number_format)

                    except ValueError:
                        pass

                    # set any color?
                    try:
                        color = record["__color_{}".format(c)]
                    except KeyError:
                        color = None
                    if color:
                        format.update({"bg_color": color})
                    ws.write(row_counter, j, v, format)
                    if isinstance(v, float):
                        pass
                    elif not isinstance(v, str):
                        v = str(v)

                    format = wb.add_format(format)
                    ws.write(row_counter, j, v, format)

                row_counter += 1
                return row_counter

            row_counter = write_header(0)
            for _i, row in enumerate(records):
                row_counter = print_row(row, row_counter)

            # finalize
            ws.freeze_panes(1, 0)

        wb.close()
        output.seek(0)

        result = output.read()
        result = self.auto_fit_columns(result)

        return result
