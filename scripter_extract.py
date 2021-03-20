#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

content = []
circltmpl = "[ << >> circlebox {x} x {y} y {w} {h} fbox {label} label dict2pdfmark /ANN pdfmark"
texttmpl = "[ << >> {maxlen} combtext {x} x {y} y {w} {h} fbox {label} label dict2pdfmark /ANN pdfmark"
start = None
end = 'None'
doit = start is None
for page in range(2, 3):
    scribus.gotoPage(page)
    for item, a, b in scribus.getPageItems():
        if item == start:
            doit = True
        elif item == end:
            break
        elif not doit:
            continue
        if item.startswith('Group'):
            scribus.unGroupObjects(item)
            continue
        if scribus.getProperty(item, 'lineColor') != 'PANTONE Warm Red U':
            # print(item, scribus.getProperty(item, 'lineColor'))
            continue
        # print(item)
        locals().update({prop: int(scribus.getProperty(item, prop)) for prop in ('xPos', 'yPos', 'width', 'height')})
        if height > 10:
            print(texttmpl.format(x=xPos, y=yPos, height=height, width=width, label=item, maxlen=width // 12)
        else:
            print(circltmpl.format(x=xPos, y=yPos, height=height, width=width, label=item))

# print('hi')

# print(dir(scribus))
