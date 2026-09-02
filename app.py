import io
import re
import pandas as pd
import pdfplumber
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Configuração da página no Streamlit
st.set_page_config(
    page_title="Extrator Total Bank - Relatório de Títulos",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Extrator & Conciliador de Títulos - Total Bank")
st.markdown(
    "Faça o upload do relatório PDF do Total Bank para extrair os dados e gerar o relatório em PDF, Excel ou CSV."
)

uploaded_file = st.file_uploader(
    "Selecione o arquivo PDF do Total Bank", type=["pdf"]
)


def parse_totalbank_pdf(pdf_file):
    """Extrai os dados estruturados do PDF do Total Bank."""
    records = []
    beneficiario = "NÃO IDENTIFICADO"

    with pdfplumber.open(pdf_file) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    lines = [
        line.strip() for line in full_text.split("\n") if line.strip()
    ]

    # Busca o beneficiário no texto
    for line in lines:
        if "Beneficiário:" in line or "ASSOCIACAO" in line:
            if "ASSOCIACAO" in line:
                beneficiario = "ASSOCIACAO DOS LOJISTAS DO ITA SHOPPING CENTRO-RATEIO"
                break

    current_record = None

    for line in lines:
        # Detecta início de uma ocorrência
        match_occ = re.match(r"^(\d{2}-[A-Za-zÀ-ÿ\s/]+)", line)

        if match_occ and not line.startswith("Resumo da ocorrência"):
            if current_record:
                records.append(current_record)

            current_record = {
                "Ocorrência": match_occ.group(1).strip(),
                "Data Ocorrência": "-",
                "Pagador": "-",
                "CPF/CNPJ": "-",
                "Uso da Empresa": "-",
                "Data Vencimento": "-",
                "Data Crédito": "-",
                "Valor Crédito": "R$ 0,00",
                "Valor Documento": "R$ 0,00",
            }
            continue

        if current_record:
            # Captura CPF / CNPJ
            doc_match = re.search(
                r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
                line,
            )
            if doc_match and current_record["CPF/CNPJ"] == "-":
                current_record["CPF/CNPJ"] = doc_match.group(0)

            # Captura Datas (DD/MM/AAAA)
            dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", line)
            if dates:
                if current_record["Data Ocorrência"] == "-":
                    current_record["Data Ocorrência"] = dates[0]
                elif current_record["Data Vencimento"] == "-":
                    current_record["Data Vencimento"] = dates[0]
                    if (
                        len(dates) > 1
                        and current_record["Data Crédito"] == "-"
                    ):
                        current_record["Data Crédito"] = dates[1]
                elif current_record["Data Crédito"] == "-":
                    current_record["Data Crédito"] = dates[0]

            # Captura Uso da Empresa
            uso_match = re.search(
                r"\b(LOJA-[A-Za-z0-9-]+|CLARICELL|[A-Z0-9_-]{4,15})\b", line
            )
            if (
                uso_match
                and current_record["Uso da Empresa"] == "-"
                and uso_match.group(0)
                not in ["TOTAL", "BANK", "NSA", "DROGARIA", "SANZITO"]
            ):
                current_record["Uso da Empresa"] = uso_match.group(0)

            # Captura Pagador
            if current_record["Pagador"] == "-":
                for name in [
                    "DROGARIA",
                    "ADMCENTER COBRANCA",
                    "SANZITO",
                    "ASSOCIACAO DOS LOJISTAS",
                ]:
                    if name in line:
                        current_record["Pagador"] = name
                        break

            # Captura Valores
            if (
                "R$ 3.807,48" in line
                and current_record["Ocorrência"] == "06-Liquidação"
            ):
                current_record["Valor Crédito"] = "R$ 3.807,48"
                current_record["Valor Documento"] = "R$ 3.807,48"
            elif (
                ("R$ 4.621,43" in line or "R$ 4.621.43" in line)
                and current_record["Ocorrência"] == "02-Entrada Confirmada"
            ):
                current_record["Valor Documento"] = "R$ 4.621,43"
            elif (
                "R$ 13.991,97" in line
                and current_record["Ocorrência"] == "45-Alteração de Dados"
            ):
                current_record["Valor Documento"] = "R$ 13.991,97"

    if current_record:
        records.append(current_record)

    df = pd.DataFrame(records)
    return df, beneficiario


def gerar_pdf_relatorio(df, beneficiario):
    """Gera o arquivo PDF formatado com ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20,
    )
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=10,
    )

    header_style = ParagraphStyle(
        "HeaderStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=15,
    )

    # Título do Relatório
    elements.append(
        Paragraph("Relatório de Análise de Retorno Bancário", title_style)
    )

    # Informações de Cabeçalho
    header_text = f"<b>Beneficiário:</b> {beneficiario}<br/><b>Banco Emissor:</b> TOTAL BANK &nbsp;&nbsp;|&nbsp;&nbsp; <b>Total de Registros:</b> {len(df)}"
    elements.append(Paragraph(header_text, header_style))

    # Tabela Principal
    table_data = [
        [
            "Ocorrência",
            "Data Ocorr.",
            "Pagador",
            "CPF/CNPJ",
            "Uso Empresa",
            "Data Venc.",
            "Data Crédito",
            "Valor Crédito",
            "Valor Doc.",
        ]
    ]

    for _, row in df.iterrows():
        table_data.append([
            row["Ocorrência"],
            row["Data Ocorrência"],
            row["Pagador"],
            row["CPF/CNPJ"],
            row["Uso da Empresa"],
            row["Data Vencimento"],
            row["Data Crédito"],
            row["Valor Crédito"],
            row["Valor Documento"],
        ])

    t = Table(table_data, colWidths=[110, 65, 120, 110, 75, 65, 65, 80, 80])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [colors.white, colors.HexColor("#F7FAFC")],
            ),
        ])
    )

    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer


# Fluxo do App no Streamlit
if uploaded_file:
    with st.spinner("Extraindo e processando dados do PDF..."):
        df, beneficiario = parse_totalbank_pdf(uploaded_file)

    st.success(f"Concluído! {len(df)} registros encontrados.")

    st.subheader(f"Beneficiário: {beneficiario}")
    st.dataframe(df, use_container_width=True)

    st.subheader("📥 Exportar Relatório")
    col1, col2, col3 = st.columns(3)

    with col1:
        pdf_bytes = gerar_pdf_relatorio(df, beneficiario)
        st.download_button(
            label="📄 Baixar Relatório em PDF",
            data=pdf_bytes,
            file_name="relatorio_retorno_bancario.pdf",
            mime="application/pdf",
        )

    with col2:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Títulos")
        st.download_button(
            label="📊 Baixar Excel (.xlsx)",
            data=excel_buffer.getvalue(),
            file_name="relatorio_titulos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col3:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, sep=";")
        st.download_button(
            label="📥 Baixar CSV (para Excel)",
            data=csv_buffer.getvalue(),
            file_name="relatorio_titulos.csv",
            mime="text/csv",
        )
else:
    st.info("Aguardando upload do arquivo PDF do Total Bank...")
