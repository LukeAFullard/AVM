from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors

def create_vintage_article(filename):
    c = canvas.Canvas(filename, pagesize=letter)

    # Page 1: The Hook and Setup
    c.setFont("Helvetica-Bold", 36)
    c.drawString(1 * inch, 10 * inch, "COMMUTE BY CHOPPER!")

    c.setFont("Helvetica-Oblique", 18)
    c.drawString(1 * inch, 9.5 * inch, "Will the skies of 1999 be filled with flying Fords?")

    c.setFont("Times-Roman", 12)
    text_object = c.beginText(1 * inch, 8.5 * inch)
    text_object.setFont("Times-Roman", 12)
    text_object.setLeading(18)

    story = [
        "By the year 1999, the grueling two-hour automobile commute will be a relic of the past.",
        "That is the bold promise of aerospace engineers working secretly in Detroit today.",
        "Forget the traffic jams and the endless ribbons of asphalt. The American family of",
        "tomorrow will simply step out of their suburban front door, climb into the family",
        "Hiller Hornet, and lift vertically into the morning sky.",
        "",
        "These 'Air-Cars' are surprisingly simple to operate. Utilizing twin ramjet engines",
        "mounted at the tips of the rotor blades, the contraption weighs less than a standard",
        "refrigerator and costs roughly the same as a mid-priced sedan. Safety? The engineers",
        "scoff at the question. 'It is safer than crossing the street,' claims lead designer",
        "Stanley Hiller Jr. In the event of engine failure, the craft simply auto-rotates",
        "gently to the earth like a maple seed.",
        "",
        "City planners are already redesigning downtown metropolis areas. Flat roofs on office",
        "buildings will be converted into sprawling 'Air-Parks' where thousands of these",
        "commuter helicopters can land each morning."
    ]

    for line in story:
        text_object.textLine(line)

    c.drawText(text_object)

    # Draw a mock image box
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.lightgrey)
    c.rect(1 * inch, 2 * inch, 6.5 * inch, 4 * inch, fill=1)

    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.black)
    c.drawString(2.5 * inch, 4 * inch, "[ ILLUSTRATION: A FAMILY HOVERING OVER TRAFFIC ]")

    c.showPage()
    c.save()

if __name__ == "__main__":
    create_vintage_article("vintage_commuter.pdf")
