import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def create_pdf(filename, title, dept, go_no, date, abstract, reads, order_body, table_data=None, signatories=None):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    doc = SimpleDocTemplate(filename, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=18, alignment=1)
    sub_title = ParagraphStyle('SubTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=16, alignment=1)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14)
    body_bold = ParagraphStyle('BodyBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=14)
    abstract_style = ParagraphStyle('AbstractStyle', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=10, leading=14)
    read_style = ParagraphStyle('ReadStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, leftIndent=20)
    
    elements = []
    
    elements.append(Paragraph("GOVERNMENT OF KERALA", title_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Abstract", sub_title))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(abstract, abstract_style))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph(f"<b>{dept}</b>", sub_title))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph(f"<b>{go_no}</b> &nbsp;&nbsp;&nbsp;&nbsp; Dated, Thiruvananthapuram, <b>{date}</b>", body_bold))
    elements.append(Spacer(1, 12))
    
    if reads:
        elements.append(Paragraph("Read:", body_bold))
        for idx, read_item in enumerate(reads, 1):
            elements.append(Paragraph(f"{idx}. {read_item}", read_style))
        elements.append(Spacer(1, 14))
        
    elements.append(Paragraph("ORDER", sub_title))
    elements.append(Spacer(1, 10))
    
    for para in order_body:
        elements.append(Paragraph(para, body_style))
        elements.append(Spacer(1, 8))
        
    if table_data:
        elements.append(Spacer(1, 6))
        # Format table cells with Paragraph for wrap
        formatted_table = []
        for row in table_data:
            formatted_row = []
            for cell in row:
                formatted_row.append(Paragraph(f"<b>{cell}</b>" if row == table_data[0] else cell, body_style))
            formatted_table.append(formatted_row)
            
        t = Table(formatted_table, colWidths=[250, 200])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e2e8f0")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#94a3b8")),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 14))
        
    elements.append(PageBreak())
    
    # Page 2: Distribution list
    elements.append(Paragraph("To:", body_bold))
    elements.append(Spacer(1, 8))
    d_list = [
        "The Principal Accountant General (A&E), Kerala, Thiruvananthapuram",
        "The Principal Accountant General (G &SSA), Kerala, Thiruvananthapuram",
        "The Accountant General (E&RSA), Karunakaran Nambiar Road, Thrissur",
        "The Chief Engineer, PWD (Roads / Bridges / Buildings), Thiruvananthapuram",
        "The Director of Treasuries, Thiruvananthapuram",
        "The Nodal Officer, Finance - ctfmweb@gmail.com",
        "Finance Department",
        "Stock File / Office Copy"
    ]
    for item in d_list:
        elements.append(Paragraph(f"• {item}", body_style))
        elements.append(Spacer(1, 4))
        
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("(By order of the Governor)", ParagraphStyle('RightSub', parent=body_style, alignment=2)))
    elements.append(Paragraph("<b>UNDER SECRETARY / SECRETARY TO GOVERNMENT</b>", ParagraphStyle('RightSub2', parent=body_bold, alignment=2)))
    
    doc.build(elements)
    print(f"Generated seed document: {filename}")

def generate_all_seeds(output_dir="data/uploads"):
    os.makedirs(output_dir, exist_ok=True)
    
    # GO 1: BDS April 2026 Schedule
    create_pdf(
        os.path.join(output_dir, "GO_Rt_5618_2026_FIN.pdf"),
        "GOVERNMENT OF KERALA",
        "FINANCE (BD&GB) DEPARTMENT",
        "G.O.(Rt)No.5618/2026/FIN",
        "08-07-2026",
        "Bill Discounting System- BDS - Schedule for the issuance of Letter of Credit of pending bills of contractors for the month of April 2026- Sanctioned- Orders issued.",
        [
            "G.O. ( P ) No. 123/2016/FIN Dated 29/08/2016",
            "G.O. (Rt) No. 4874/2026/FIN Dated 09/06/2026"
        ],
        [
            "As per the Government Order read 1st above, Government issued detailed guidelines on the procedure of Bill Discounting system (BDS) for making payment of pending bills of contractors. Based on the procedure laid down therein, Government have issued orders fixing the schedule of payment of pending bills up to the month of March 2026 in the Government order read 2nd above.",
            "In continuation to this, Government are now pleased to sanction the schedule date for issuing LoC for clearing the pending bills in respect of PWD (Roads), PWD (Bridges) and PWD (Buildings & Local Works) for the month of April 2026 as detailed below:"
        ],
        [
            ["Name of the Department", "Schedule date"],
            ["PWD ( Roads )", "14/12/2026"],
            ["PWD ( Bridges )", "14/12/2026"],
            ["PWD ( Buildings & Local Works )", "14/12/2026"]
        ]
    )

    # GO 2: KFC Limit Enhancement to 100 Crore
    create_pdf(
        os.path.join(output_dir, "GO_Ms_106_2026_FIN.pdf"),
        "GOVERNMENT OF KERALA",
        "FINANCE (PUBLIC UNDERTAKINGS-A) DEPARTMENT",
        "G.O.(Ms)No.106/2026/FIN",
        "29-07-2026",
        "Finance Department-Appointing Kerala Financial Corporation as the agent of the State Government under Section 25 1(e) of State Financial Corporation's (SFC's) Act 1951, for providing financial assistance upto Rs.100 crore to Industrial concerns, MSMEs and State PSUs-Orders issued.",
        [
            "GO(Ms)No.34/2021/Fin dated 20/02/2021",
            "GO(Ms)No.23/2022/Fin dated 03/02/2022",
            "GO(Ms)No.15/2024/Fin dated 15/02/2024",
            "GO(Ms)No.17/2026/Fin dated 15/02/2026",
            "Letter No.KFC-HO/226/2024-M(MDO) dated 16/07/2026 from the Managing Director, Kerala Financial Corporation."
        ],
        [
            "Kerala Financial Corporation was appointed as the agent of the State Government, under Section 25 1 (e) of State Financial Corporation's (SFCs) Act 1951 for providing financial assistance upto Rs.50 Crore to State PSUs only, without any restriction on paid-up share capital and free reserves limit, vide the Government Order read 1st above. Vide Government Order read 2nd above, the Government Order read 1st above was modified to appoint KFC as an agent of the State Government, under Section 25 1(e) of State Financial Corporation's (SFCs) Act 1951, for providing financial assistance up to Rs.50 Crore to Industrial Concerns, MSMEs and State PSUs, without the restriction on paid up share capital and free reserves limit, for a period of 2 years with following safeguards.",
            "(a) KFC shall mobilise own fund without any financial commitment/Guarantee from the Government.<br/>(b) The Board of KFC shall put in place adequate internal controls and safeguards in its lending Policy.<br/>(c) KFC shall insist on obtaining Credit Rating from RBI accredited Credit Rating Agencies while funding large projects.",
            "2) Vide Government orders read 3rd and 4th paper above, sanction has been accorded for the extension of the validity period of the scheme for 2 years from 03.02.2024 to 02.02.2026 and then two years from 03.02.2026 to 02.02.2028 accordingly subject to the existing terms and conditions.",
            "3) In the letter read 5th paper above Managing Director, Kerala Financial Corporation has requested to accord sanction to appoint KFC as an agent of the State Government, under Section 25 1(e) of State Financial Corporation's (SFCs) Act 1951, for providing financial assistance up to Rs.100 Crore to Industrial Concerns, MSMEs and State PSUs, without the restriction on paid-up share capital and free reserves limit subject to the existing terms and conditions.",
            "4) Government have examined the matter in detail and are pleased to accord sanction to appoint KFC as an agent of the State Government, under Section 25 1(e) of State Financial Corporation's (SFCs) Act 1951 to accord sanction to appoint KFC as an agent of the State Government for providing financial assistance up to Rs.100 Crore to Industrial Concerns, MSMEs and State PSUs, without the restriction on paid-up share capital and free reserves limit, subject to the existing terms and conditions."
        ]
    )

    # GO 3: Prior KFC limit Rs 50 Crore
    create_pdf(
        os.path.join(output_dir, "GO_Ms_23_2022_FIN.pdf"),
        "GOVERNMENT OF KERALA",
        "FINANCE (PUBLIC UNDERTAKINGS-A) DEPARTMENT",
        "G.O.(Ms)No.23/2022/FIN",
        "03-02-2022",
        "Finance Department-Appointing Kerala Financial Corporation as agent of State Government for financial assistance up to Rs.50 Crore to Industrial concerns, MSMEs and State PSUs - Sanctioned - Orders issued.",
        [
            "GO(Ms)No.34/2021/Fin dated 20/02/2021"
        ],
        [
            "Government are pleased to accord sanction to appoint Kerala Financial Corporation (KFC) as agent under Section 25 1(e) of SFCs Act 1951 for providing financial assistance up to Rs.50 Crore to Industrial Concerns, MSMEs and State PSUs without restriction on paid-up share capital and free reserves for a period of 2 years."
        ]
    )

    # GO 4: Prior BDS March 2026
    create_pdf(
        os.path.join(output_dir, "GO_Rt_4874_2026_FIN.pdf"),
        "GOVERNMENT OF KERALA",
        "FINANCE (BD&GB) DEPARTMENT",
        "G.O.(Rt)No.4874/2026/FIN",
        "09-06-2026",
        "Bill Discounting System- BDS - Schedule for issuance of LoC up to March 2026 - Sanctioned - Orders issued.",
        [
            "G.O. ( P ) No. 123/2016/FIN Dated 29/08/2016"
        ],
        [
            "Government are pleased to fix the schedule date for issuing Letter of Credit (LoC) for clearing pending bills of contractors up to March 2026 as per BDS procedure."
        ]
    )

if __name__ == "__main__":
    generate_all_seeds()
