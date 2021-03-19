#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

tmpl = "[ /Subtype /Widget /Rect [{}] /F 4 /FT /Tx /T ({}) bd /Ff 1 24 bitshift /MaxLen {} /ANN pdfmark"
for page in range(2, 3):
    scribus.gotoPage(page)
    for item, a, b in scribus.getPageItems():
        if item.startswith('Group'):
            scribus.unGroupObjects(item)
            continue
        if scribus.getProperty(item, 'lineColor') != 'PANTONE Warm Red U':
            # print(item, scribus.getProperty(item, 'lineColor'))
            continue
        # print(item)
        locals().update({prop: int(scribus.getProperty(item, prop)) for prop in ('xPos', 'yPos', 'width', 'height')})
        print(tmpl.format(f'{xPos} x {yPos} y {xPos + width} x {yPos + height} y', item, width // 12))

# print('hi')

# print(dir(scribus))
