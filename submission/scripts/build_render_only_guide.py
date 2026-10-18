from pathlib import Path
from xml.sax.saxutils import escape
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

root=Path(__file__).resolve().parents[2]
source=root/'submission/RENDER_ONLY_DEMONSTRATION_GUIDE.md'
out=root/'output/pdf/CFLIA_Render_Only_Demonstration_Guide.pdf'
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleX',fontName='Helvetica-Bold',fontSize=20,leading=24,textColor=colors.HexColor('#173d34'),spaceAfter=12))
styles.add(ParagraphStyle(name='H2X',fontName='Helvetica-Bold',fontSize=14,leading=18,textColor=colors.HexColor('#173d34'),spaceBefore=10,spaceAfter=8,keepWithNext=True))
styles.add(ParagraphStyle(name='H3X',fontName='Helvetica-Bold',fontSize=10.3,leading=13,spaceBefore=8,spaceAfter=5,keepWithNext=True))
styles.add(ParagraphStyle(name='BodyX',fontName='Helvetica',fontSize=9.3,leading=12.5,spaceAfter=6))
styles.add(ParagraphStyle(name='StepX',parent=styles['BodyX'],leftIndent=9,firstLineIndent=-9,spaceAfter=4))
styles.add(ParagraphStyle(name='CellX',parent=styles['BodyX'],fontSize=8.6,leading=11,spaceAfter=0))
styles.add(ParagraphStyle(name='CodeX',fontName='Courier',fontSize=7.8,leading=10.2,spaceBefore=4,spaceAfter=9))

def fmt(text):
    text=escape(text)
    text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)
    text=re.sub(r'(https?://[^\s<>]+)',lambda m:'<link href="'+m[0]+'" color="#17594a">'+m[0]+'</link>',text)
    return text

flow=[]
lines=source.read_text().splitlines();i=0
while i<len(lines):
    line=lines[i]
    if not line.strip():i+=1;continue
    if line=='<!-- PAGE -->':flow.append(PageBreak());i+=1;continue
    if line.startswith('```'):
        code=[];i+=1
        while i<len(lines) and not lines[i].startswith('```'):code.append(lines[i]);i+=1
        # Keep URLs intact; use a smaller monospace size if one line is long.
        longest=max(map(len,code),default=0)
        size=min(7.8, (507/(longest*0.6)) if longest else 7.8)
        cs=ParagraphStyle('codeblock',parent=styles['CodeX'],fontSize=size,leading=size*1.32)
        box=Table([[Preformatted('\n'.join(code),cs)]],colWidths=[511])
        box.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#eef4f0')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
        flow.extend([box,Spacer(1,7)]);i+=1;continue
    if line.startswith('|'):
        rows=[]
        while i<len(lines) and lines[i].startswith('|'):
            cells=[c.strip() for c in lines[i].strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?',c) for c in cells):rows.append(cells)
            i+=1
        widths=([107,404] if len(rows[0])==2 else ([100,80,331] if len(rows[0])==3 and rows[0][0]=='Time' else [171,170,170]))
        data=[[Paragraph(fmt(c),styles['CellX']) for c in row] for row in rows]
        table=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbe9e1')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#9fb9aa')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dbe5df')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        flow.extend([table,Spacer(1,9)]);continue
    if line.startswith('# '):flow.append(Paragraph(fmt(line[2:]),styles['TitleX']))
    elif line.startswith('## '):flow.append(Paragraph(fmt(line[3:]),styles['H2X']))
    elif line.startswith('### '):flow.append(Paragraph(fmt(line[4:]),styles['H3X']))
    elif re.match(r'\d+\. ',line) or line.startswith('- '):flow.append(Paragraph(fmt(line[2:] if line.startswith('- ') else line),styles['StepX']))
    else:flow.append(Paragraph(fmt(line),styles['BodyX']))
    i+=1

def footer(c,d):
    c.setStrokeColor(colors.HexColor('#bfd1c6'));c.line(42,39,553,39)
    c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#52675d'))
    c.drawString(42,26,'LEGACYDESK | Render-only demonstration | 18 October 2026')
    c.drawRightString(553,26,str(d.page))

SimpleDocTemplate(str(out),pagesize=(595.28,841.89),leftMargin=42,rightMargin=42,topMargin=32,bottomMargin=50,title='LegacyDesk - Render-only Demonstration Guide',author='LegacyDesk project team').build(flow,onFirstPage=footer,onLaterPages=footer)
print(out)
