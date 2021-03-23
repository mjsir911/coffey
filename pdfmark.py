#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

from pdfrw import PdfReader, PdfWriter
from pdfrw.objects import *


from sys import argv

import postscript


r = PdfReader(argv[1] if len(argv) > 1 else 'dor-2020-inc-form-1-nrpy.pdf')


def translate(d, objdict):
    if isinstance(d, postscript.ExecutableArray):
        d = tuple(d)
        return objdict.setdefault(d, IndirectPdfDict())
        # assert len(d) == 1
        # and d[0] == 'MoonNotes':
        # return moon_notes
    elif isinstance(d, dict):
        return PdfDict({translate(k, objdict): translate(v, objdict) for k, v in d.items()})
    elif isinstance(d, (list, postscript.Array)):
        return [translate(item, objdict) for item in d]
    elif isinstance(d, postscript.Name):
        return PdfName(d)
    elif isinstance(d, postscript.String):
        return str(d)
    elif isinstance(d, bool):
        # Can get rid of this once pdfrw#220 comes through
        return PdfObject('true') if d else PdfObject('false')

    return d

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

class PdfmarkRunner(postscript.Runner):
    def __init__(self, catalog, *args):
        super().__init__(*args)
        self.annots = []
        self.page = 1

        self.objects = {
            postscript.Array(['Catalog']): catalog,
            postscript.Array(['ZaDb']): ZaDb,
            # postscript.Block(['MoonNotes']): moon_notes,
            # postscript.Block(['MoonNotesOff']): moon_notes_off,
        }

    def pdfmark_OBJ(self):
        d = self.func_hex_3E3E()
        ref = d.pop(postscript.Name('_objdef'))
        ref = tuple(ref)
        t = str(d.pop(postscript.Name('type')))
        if t == 'dict' or t == 'stream':
            self.objects.setdefault(ref, IndirectPdfDict())
        elif t == 'array':
            default = PdfArray()
            default.indirect = True
            self.objects.setdefault(ref, default)
        else:
            raise Exception(t)


    def pdfmark_PUT(self):
        ref, stuff = self.func_unmark()
        ref = tuple(ref)
        obj = self.objects.setdefault(ref, IndirectPdfDict())
        if isinstance(stuff, postscript.String):
            obj.stream = str(stuff)
        elif isinstance(obj, dict):
            obj.update(translate(stuff, self.objects))
        else:
            raise Exception(stuff)

    def pdfmark_APPEND(self):
        ref, stuff = self.func_unmark()
        ref = tuple(ref)
        obj = self.objects.setdefault(ref, IndirectPdfDict())
        if isinstance(obj, list):
            obj.append(translate(stuff, self.objects))
        else:
            raise Exception(stuff)

    def pdfmark_CLOSE(self):
        self.run(["cleartomark"])

    def pdfmark_ANN(self):
        annot = self.func_hex_3E3E()
        ref = tuple(annot.pop(postscript.Name('_objdef'), [None]))
        d = translate(annot, self.objects)

        if ref is not None:
            if ref in self.objects:
                self.objects[ref].update(d)
            else:
                self.objects[ref] = d
            d = self.objects[ref]

        d.indirect = True
        d.Type = PdfName('Annot')
        if '/SrcPg' not in d:
            d.SrcPg = self.page
        if d.T == 'RaBF9':
            print(d)
        self.annots.append(d)

    def func_pdfmark(self):
        a = self.pop()
        getattr(self, 'pdfmark_' + a)()

    def func_showpage(self):
        self.page += 1


template = open('dor-2020-inc-form-1-nrpy-form-overlay.ps').read()
runner = PdfmarkRunner(r.Root)
pdfmarks = runner(template).annots

# self.pdfmarks = PdfArray()
# self.pdfmarks.indirect = True

for mark in pdfmarks:
    page = r.pages[mark.SrcPg - 1]
    if page.Annots is None:
        page.Annots = PdfArray()
    page.Annots.append(mark)
    r.Root.AcroForm.Fields.append(mark)  # Need to migrate this to the lib eventually


# for page, annots in zip(r.pages, pdfmarks):
#     page.Annots = annots

PdfWriter('out.pdf', trailer=r).write()
