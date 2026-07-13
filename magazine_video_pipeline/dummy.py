from reportlab.pdfgen import canvas
c = canvas.Canvas("test.pdf")
c.drawString(100, 100, "Example Magazine")
c.save()
