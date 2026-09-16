import io
from datetime import datetime
from reportlab import rl_config
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from app.domain.assessment_report import AssessmentReport, CompetencyReport

rl_config.pageCompression = 0


class PDFReportGenerator:
    """
    Generates a structured, professional, downloadable PDF report
    from an AssessmentReport instance using ReportLab.
    """

    def generate(self, report: AssessmentReport) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#475569"),
            spaceAfter=12,
        )
        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=12,
            spaceAfter=6,
        )
        subsection_heading = ParagraphStyle(
            "SubSectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#334155"),
            spaceBefore=6,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "BodyDark",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
        bullet_style = ParagraphStyle(
            "BulletText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1e293b"),
            leftIndent=12,
            firstLineIndent=-8,
        )
        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
        )
        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.white,
        )

        story = []

        # 1. Header & Title
        story.append(Paragraph("Adaptive Interview Assessment", title_style))
        gen_time_str = report.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        story.append(
            Paragraph(
                f"Generated on {gen_time_str} | Session ID: {report.session_id}",
                subtitle_style,
            )
        )
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceAfter=14))

        # 2. Executive Overview Box (Score & Session Details)
        status_label = "COMPLETED" if report.completed else "IN PROGRESS"
        status_color = colors.HexColor("#16a34a") if report.completed else colors.HexColor("#eab308")

        summary_data = [
            [
                Paragraph("<b>Session Status:</b>", body_style),
                Paragraph(f"<b><font color='{status_color.hexval()}'>{status_label}</font></b>", body_style),
                Paragraph("<b>Overall Score:</b>", body_style),
                Paragraph(f"<b><font size='12' color='#2563eb'>{report.overall_score:.1f} / 100</font></b>", body_style),
            ],
            [
                Paragraph("<b>Total Evidence Turns:</b>", body_style),
                Paragraph(str(report.total_evidence_count), body_style),
                Paragraph("<b>Competencies Assessed:</b>", body_style),
                Paragraph(str(len(report.competency_reports)), body_style),
            ],
        ]
        if report.candidate_id:
            summary_data.append([
                Paragraph("<b>Candidate ID:</b>", body_style),
                Paragraph(str(report.candidate_id), body_style),
                Paragraph("<b>Session Title:</b>", body_style),
                Paragraph(report.session_title or "Adaptive Interview", body_style),
            ])

        summary_table = Table(summary_data, colWidths=[130, 140, 130, 140])
        summary_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(summary_table)
        story.append(Spacer(1, 14))

        # 3. Competency Breakdown Summary Table
        story.append(Paragraph("Competency Score Breakdown", section_heading))

        headers = [
            Paragraph("Competency", table_header_style),
            Paragraph("Score", table_header_style),
            Paragraph("Demonstrated", table_header_style),
            Paragraph("Target", table_header_style),
            Paragraph("Confidence", table_header_style),
            Paragraph("Weight", table_header_style),
            Paragraph("Evidence", table_header_style),
        ]
        table_rows = [headers]

        for cr in report.competency_reports:
            conf_pct = f"{cr.confidence * 100:.0f}%"
            score_str = f"{cr.score:.1f}/100"
            table_rows.append([
                Paragraph(cr.competency_name, table_cell_style),
                Paragraph(score_str, table_cell_style),
                Paragraph(f"{cr.demonstrated_level:.1f} / 5", table_cell_style),
                Paragraph(f"{cr.target_level} / 5", table_cell_style),
                Paragraph(conf_pct, table_cell_style),
                Paragraph(f"{cr.weight:.1f}", table_cell_style),
                Paragraph(str(cr.evidence_count), table_cell_style),
            ])

        if len(report.competency_reports) == 0:
            table_rows.append([
                Paragraph("<i>No competencies evaluated</i>", table_cell_style),
                Paragraph("-", table_cell_style),
                Paragraph("-", table_cell_style),
                Paragraph("-", table_cell_style),
                Paragraph("-", table_cell_style),
                Paragraph("-", table_cell_style),
                Paragraph("-", table_cell_style),
            ])

        comp_table = Table(table_rows, colWidths=[150, 65, 75, 60, 65, 55, 70])
        comp_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ])
        )
        story.append(comp_table)
        story.append(Spacer(1, 14))

        # 4. Detailed Evidence Analysis per Competency (Strengths & Gaps)
        story.append(Paragraph("Detailed Competency Evidence & Analysis", section_heading))

        for cr in report.competency_reports:
            comp_elements = []
            comp_elements.append(
                Paragraph(
                    f"<b>{cr.competency_name}</b> &mdash; Score: <b>{cr.score:.1f}/100</b> "
                    f"(Demonstrated Level {cr.demonstrated_level:.1f} vs Target {cr.target_level})",
                    subsection_heading,
                )
            )

            # Strengths
            comp_elements.append(Paragraph("<b>Demonstrated Strengths:</b>", body_style))
            if cr.strengths:
                for s in cr.strengths:
                    comp_elements.append(Paragraph(f"&bull; {s}", bullet_style))
            else:
                comp_elements.append(Paragraph("<i>No specific strengths recorded.</i>", bullet_style))

            comp_elements.append(Spacer(1, 4))

            # Gaps
            comp_elements.append(Paragraph("<b>Identified Development Gaps:</b>", body_style))
            if cr.gaps:
                for g in cr.gaps:
                    comp_elements.append(Paragraph(f"&bull; {g}", bullet_style))
            else:
                comp_elements.append(Paragraph("<i>No specific gaps recorded.</i>", bullet_style))

            comp_elements.append(Spacer(1, 8))
            story.append(KeepTogether(comp_elements))

        # 5. Assessment Methodology & Boundary Notice
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8"), spaceAfter=8))
        story.append(
            Paragraph(
                "<b>Assessment Methodology Note:</b> Scores in this report are mathematically aggregated "
                "from deterministic response evaluations recorded across adaptive interview turns. "
                "This report provides objective competency signal based strictly on demonstrated evidence and "
                "does not make hiring or placement decisions.",
                body_style,
            )
        )

        doc.build(story)
        return buffer.getvalue()
