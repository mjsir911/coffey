#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

from pdfrw import PdfReader, PdfWriter
from pdfrw.objects.pdfstring import PdfString
from pdfrw.objects.pdfdict import PdfDict
from pdfrw.objects.pdfarray import PdfArray

from pdfrw.objects.pdfdict import PdfDict
from pdfrw.objects.pdfname import PdfName


def make_js_action(js):
    action = PdfDict()
    action.S = PdfName.JavaScript
    action.JS = js
    return action


def append_js_to_pdf(file_name):
    pdf_writer = PdfWriter()
    pdf_reader = PdfReader(file_name)
    try:
        js = open(sys.argv[1]).read()
    except:
        # js = "this.getField('residency_duration_ratio').value = (event.value / 365).toString().split('.')[1];"
        # js = "this.getField('residency_duration_ratio').value = 1"
        js = "app.alert('hi')"
    for page_index in pdf_reader.pages:
        page = page_index
        page.Type = PdfName.Page
        try:
            print(page.Annots)
            for field in page.Annots:
                field.update(PdfDict(AA=PdfDict(V=make_js_action(js))))
        except:
            pass
        # page.AA = PdfDict()
        # page.AA.O = make_js_action(js)
        pdf_writer.addpage(page)

    pdf_writer.write('test.pdf')


if __name__ == "__main__":
    # javascript_added = append_js_to_pdf("/home/msirabella/Downloads/forms.pdf")
    javascript_added = append_js_to_pdf("out.pdf")
    # javascript_added = append_js_to_pdf("/home/msirabella/Downloads/forms.pdf")
