# Coffey

- <http://math.uakron.edu/~dpstory/tutorial/pdfmarks/forms.pdf>
- <https://www.adobe.com/content/dam/acom/en/devnet/acrobat/pdfs/pdfmark_reference.pdf>
- <https://www.adobe.com/content/dam/acom/en/devnet/acrobat/pdfs/pdf_reference_1-7.pdf>
- <https://www.adobe.com/content/dam/acom/en/devnet/acrobat/pdfs/js_api_reference.pdf>
- <https://www.tinaja.com/glib/jpg2pdf.pdf>

Ghostscript didn't work unfortunately:
- strips some important decorations from a pdf (the red outlining for fields)
- doesn't fill up `/AcroForm/Fields` so pdftk can't detect the form fields
- if you do hacks to fill the `/Acroform/Fields` array, straight up crashes pdftk

but all the postscript found in the overlay file should be compatible if
ghostscript ever decides to work better.

`mupdf` doesn't respect text field justification (`/Q`) if the comb form field
is used ( `/Ff 1 24 bitshift` )

Tools used for testing:
- `qpdf`
- poppler stuff like `pdffont`
- mupdf
- chrome

Built while listening to [inabakumori](https://www.youtube.com/channel/UCNElM45JypxqAR73RoUQ10g)
