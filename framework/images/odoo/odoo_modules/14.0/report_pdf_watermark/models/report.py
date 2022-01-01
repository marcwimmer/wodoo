import tempfile
try:
    import pdftotext
except:
    pass
from bs4 import BeautifulSoup
import time
import os
from pathlib import Path
from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.tools.pdf import merge_pdf
from odoo.exceptions import UserError, RedirectWarning, ValidationError
from io import BytesIO
import logging
import base64
from PyPDF2 import PdfFileWriter, PdfFileReader  # pylint: disable=W0404
from PyPDF2.utils import PdfReadError  # pylint: disable=W0404
logger = logging.getLogger(__file__)

class Report(models.Model):
    _inherit = 'ir.actions.report'

    background_report = fields.Many2one("ir.actions.report", string="Background Image")
    background_report_page2n = fields.Many2one("ir.actions.report", string="Background Image start page 2")
    article_add_css_klasses = fields.Char("Add this css classes to article element")

    def _run_wkhtmltopdf(self, bodies, header=None, footer=None,
                         landscape=False, specific_paperformat_args=None,
                         set_viewport_size=False):

        if self.article_add_css_klasses:
            bodies2 = []
            for body in bodies:
                bs = BeautifulSoup(body, 'html.parser')
                vars = {}
                for x in bs.find_all('div', attrs={'class': 'article'}):
                    k = x['class']
                    k += [self.article_add_css_klasses]
                    x['class'] = k
                    for ipage, page in enumerate(x.find_all('div', attrs={'class': 'page'})):
                        if not ipage:
                            k = page['class']
                            k += ['first']
                            page['class'] = k
                bodies2.append(str(bs).encode('utf-8'))
            bodies = bodies2

        if not self.background_report:
            result = super(Report, self)._run_wkhtmltopdf(
                bodies, header=header, footer=footer, landscape=landscape,
                specific_paperformat_args=specific_paperformat_args,
                set_viewport_size=set_viewport_size)
            return result

        pdfs = []
        vars_per_body = []
        restart_pages_at = []

        for body in bodies:
            bs = BeautifulSoup(body, 'html.parser')
            vars = {}
            for x in bs.find_all('span', attrs={'class': 'report-var'}):
                vars[x['id']] = x.text.strip()
            for x in bs.find_all(attrs={'class': 'report-restart-page-numbers'}):
                pass
            vars_per_body.append(vars)
            print(vars)
            del vars

            footer, header = "", ""
            pdf_body = super(Report, self)._run_wkhtmltopdf(
                bodies, header=header, footer=footer, landscape=landscape,
                specific_paperformat_args=specific_paperformat_args,
                set_viewport_size=set_viewport_size)

            pages = []
            reader = PdfFileReader(BytesIO(pdf_body))
            total_pages = reader.numPages
            vars = None
            pdftext = pdftotext.PDF(BytesIO(pdf_body))

            reset_page_at = None
            for ipage, page in enumerate(pdftext):
                if "__page_reset__" in page:
                    reset_page_at = ipage + 1

            page_counter = 1
            if reset_page_at:
                effective_total_pages = total_pages - (reset_page_at or 0) + 1
            else:
                effective_total_pages = total_pages

            for ipage in range(total_pages):
                page = reader.getPage(ipage)
                if not self.background_report_page2n or ipage == 0:
                    background_report = self.background_report
                else:
                    background_report = self.background_report_page2n

                if ipage + 1 == reset_page_at and reset_page_at:
                    page_counter = 1

                vars = vars_per_body[ipage] if ipage < len(vars_per_body) else (vars or {})
                vars.update(dict(
                    company=self.env.user.company_id,
                    total_pages=effective_total_pages,
                    page_num=page_counter
                ))

                background_pdf, format = super(Report, background_report).with_context(**vars).render(self.env.user.company_id, data={})
                # pdf_watermark = PdfFileReader(BytesIO(background_pdf))

                file1 = Path(tempfile.mktemp(suffix='.pdf'))
                file_stamp = Path(tempfile.mktemp(suffix=".pdf"))
                output = PdfFileWriter()
                output.addPage(page)
                with file1.open('wb') as f:
                    output.write(f)
                file_stamp.write_bytes(background_pdf)
                file_out = Path(tempfile.mktemp(suffix=".pdf"))
                os.system("pdftk '{file1}' stamp '{file_stamp}' output '{file_out}'".format(**locals()))
                pages.append(file_out.read_bytes())
                page_counter += 1
            pdf_content = merge_pdf(pages)
            pdfs.append(pdf_content)

        merged_pdf = merge_pdf(pdfs)
        return merged_pdf
