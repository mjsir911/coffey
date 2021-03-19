#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

from pdfrw import PdfReader, PdfWriter
from pdfrw.objects import *


from sys import argv

import postscript


r = PdfReader(argv[1] if len(argv) > 1 else 'dor-2020-inc-form-1-nrpy.pdf')


ZaDb = r.Root.AcroForm.DR.Font.ZaDb

moon_notes = IndirectPdfDict({
    PdfName('BBox'): [0, 0, 13, 13],
    PdfName('Resources'): PdfDict({
        PdfName('Font'): PdfDict({
            PdfName('ZaDb'): ZaDb
        }),
        PdfName('ProcSet'): [PdfName('PDF'), PdfName('Text')],
    }),
})
# Not sure how to get this...
moon_notes.stream = '/ZaDb 14 Tf 0 g  1 0 0 1 1  2.5  Tm (l) Tj ET Q'

moon_notes_off = IndirectPdfDict({
    PdfName('BBox'): [0, 0, 13, 13],
    PdfName('Resources'): PdfDict({
        PdfName('ProcSet'): [PdfName('PDF')],
    }),
})
moon_notes_off.stream = ''


def translate(d, objdict):
    if isinstance(d, postscript.Block):
        objname, = d
        return objdict.setdefault(d, IndirectPdfDict())
        # assert len(d) == 1
        # and d[0] == 'MoonNotes':
        # return moon_notes
    if isinstance(d, dict):
        return PdfDict({translate(k, objdict): translate(v, objdict) for k, v in d.items()})
    if isinstance(d, list):
        return [translate(item, objdict) for item in d]
    if isinstance(d, postscript.Name):
        return PdfName(d)
    if isinstance(d, bytearray):
        return d.decode()
    return d


class PdfmarkRunner(postscript.Runner):
    def __init__(self, *args):
        super().__init__(*args)
        self.annots = []
        self.page = 1

        self.objects = {'MoonNotes': moon_notes, 'MoonNotesOff': moon_notes_off}

    def pdfmark_OBJ(self):
        d = self.func_hex_3E3E()

    def pdfmark_PUT(self):
        ref, stuff = self.func_unmark()
        obj = self.objects.setdefault(ref, IndirectPdfDict())
        if isinstance(stuff, bytearray):
            obj.stream = stuff.decode()
        else:
            obj.update(translate(stuff, self.objects))

    def pdfmark_CLOSE(self):
        self.run(["cleartomark"])

    def pdfmark_ANN(self):
        annot = self.func_hex_3E3E()
        ref = annot.pop(postscript.Name('_objdef'), None)
        d = translate(annot, self.objects)

        if ref:
            if ref in self.objects:
                self.objects[ref].update(d)
            else:
                self.objects[ref] = d
            d = self.objects[ref]

        d.indirect = True
        d.Type = PdfName('Annot')
        if '/SrcPg' not in d:
            d.SrcPg = self.page
        if d.T == 'RBF9':
            print(d)
        self.annots.append(d)

    def func_pdfmark(self):
        a = self.pop()
        getattr(self, 'pdfmark_' + a)()

    def func_showpage(self):
        self.page += 1


template = open('dor-2020-inc-form-1-nrpy-form-overlay.ps').read()
runner = PdfmarkRunner()
pdfmarks = runner(template).annots

# self.pdfmarks = PdfArray()
# self.pdfmarks.indirect = True


for mark in pdfmarks:
    page = r.pages[mark.SrcPg - 1]
    if page.Annots is None:
        page.Annots = PdfArray()
    page.Annots.append(mark)
    r.Root.AcroForm.Fields.append(mark)


# for page, annots in zip(r.pages, pdfmarks):
#     page.Annots = annots

PdfWriter('out.pdf', trailer=r).write()

# def make_js_action(js):
#     action = PdfDict()
#     action.S = PdfName.JavaScript
#     action.JS = js
#     return action
#
#
# def append_js_to_pdf(file_name):
#     pdf_writer = PdfWriter()
#     pdf_reader = PdfReader(file_name)
#     try:
#         js = open(sys.argv[1]).read()
#     except:
#         js = "this.getField('residency_duration_ratio').value = (event.value / 365).toString().split('.')[1];"
#     for page_index in pdf_reader.pages:
#         page = page_index
#         page.Type = PdfName.Page
#         try:
#             for field in page.Annots:
#                 field.update(PdfDict(AA=PdfDict(V=make_js_action(js))))
#         except:
#             pass
#         # page.AA = PdfDict()
#         # page.AA.O = make_js_action(js)
#         pdf_writer.addpage(page)
#     with open('test.pdf', 'wb') as file:
#         pdf_writer.write(file)
#
#
# if __name__ == "__main__":
#     # javascript_added = append_js_to_pdf("/home/msirabella/Downloads/forms.pdf")
#     javascript_added = append_js_to_pdf("out.pdf")
#     # javascript_added = append_js_to_pdf("/home/msirabella/Downloads/forms.pdf")



