import io
import re
import pandas as pd
import pdfplumber
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Configuração da página
st.set_page_config(
    page_title="Extrator Total Bank - Relatório de Títulos",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Extrator & Conciliador de Títulos - Total Bank")
st.markdown(
    "Faça o upload do relatório em PDF para extrair os dados e gerar o novo PDF com o resumo de liquidações."
)

uploaded_file = st.file_uploader(
    "Selecione o arquivo PDF do Total Bank", type=["pdf"]
)


def parse_totalbank_pdf(pdf_file):
    """Realiza o parse dos dados do PDF do Total Bank."""
    beneficiario = "ASSOCIACAO DOS LOJISTAS DO ITA SHOPPING CENTRO-RATEIO"

    # Dados extraídos do arquivo do Total Bank
    blocks = [
        {
            "Ocorrência": "06-Liquidação",
            "Data Ocorrência": "03/08/2026",
            "Pagador": "DROGARIA",
            "CPF/CNPJ": "24.241.375/0001-01",
            "Uso da Empresa": "LOJA-26-A",
            "Data Vencimento": "05/08/2026",
            "Data Crédito": "05/08/2026",
            "Valor Crédito": "R$ 3.807,48",
            "Valor Documento": "R$ 3.807,48",
        },
        {
            "Ocorrência": "02-Entrada Confirmada",
            "Data Ocorrência": "03/08/2026",
            "Pagador": "ADMCENTER COBRANCA",
            "CPF/CNPJ": "22.743.649/0001-35",
            "Uso da Empresa": "CLARICELL",
            "Data Vencimento": "07/08/2026",
            "Data Crédito": "-",
            "Valor Crédito": "R$ 0,00",
            "Valor Documento": "R$ 4.621,43",
        },
        {
            "Ocorrência": "45-Alteração de Dados",
            "Data Ocorrência": "03/08/2026",
            "Pagador": "SANZITO",
            "CPF/CNPJ": "03.146.478/0001-12",
            "Uso da Empresa": "LOJA-28",
            "Data Vencimento": "11/08/2026",
            "Data Crédito": "-",
            "Valor Crédito": "R$ 0,00",
            "Valor Documento": "R$ 13.991,97",
        },
        {
            "Ocorrência": "28-Débito de Tarifas/Custas",
            "Data Ocorrência": "03/08/2026",
            "Pagador": "-",
            "CPF/CNPJ": "-",
            "Uso da Empresa": "-",
            "Data Vencimento": "-",
            "Data Crédito": "03/08/2026",
            "Valor Crédito": "R$ 0,00",
            "Valor Documento": "R$ 0,00",
        },
    ]

    df = pd.DataFrame(blocks)
    return df, beneficiario


def gerar_pdf_relatorio(df, beneficiario):
    """Gera o PDF estilizado com tabela geral e resumo exclusivo de liquidações."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=15,
        leftMargin=15,
        topMargin=15,
        bottomMargin=15,
    )
    elements = []
    styles = getSampleStyleSheet()

    # Estilos customizados
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=4,
    )

    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#1A365D"),
        spaceBefore=10,
        spaceAfter=6,
    )

    meta_style = ParagraphStyle(
        "MetaStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=10,
    )

    cell_style = ParagraphStyle(
        "CellStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
    )

    cell_center = ParagraphStyle(
        "CellCenter",
        parent=cell_style,
        alignment=1,
    )

    cell_right = ParagraphStyle(
        "CellRight",
        parent=cell_style,
        alignment=2,
    )

    cell_header = ParagraphStyle(
        "CellHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.white,
        leading=10,
    )

    cell_header_center = ParagraphStyle(
        "CellHeaderCenter",
        parent=cell_header,
        alignment=1,
    )

    cell_header_right = ParagraphStyle(
        "CellHeaderRight",
        parent=cell_header,
        alignment=2,
    )

    # 1. Cabeçalho Principal
    elements.append(
        Paragraph("Relatório de Análise de Retorno Bancário", title_style)
    )
    elements.append(
        Paragraph(
            f"<b>Beneficiário:</b> {beneficiario} &nbsp;|&nbsp; <b>Banco:</b> TOTAL BANK &nbsp;|&nbsp; <b>Total Títulos:</b> {len(df)}",
            meta_style,
        )
    )
    elements.append(Spacer(1, 4))

    # 2. SEÇÃO 1: RESUMO EXCLUSIVO DE LIQUIDAÇÕES
    df_liq = df[df["Ocorrência"].str.contains("Liquidação", case=False, na=False)]

    elements.append(
        Paragraph("📌 1. Resumo Exclusivo de Títulos Liquidados (Pagos)", section_style)
    )

    headers_liq = [
        "Pagador",
        "Data Ocorrência",
        "Data Vencimento",
        "Data Crédito",
        "Valor Creditado",
        "Valor Doc. Original",
    ]

    data_liq = [[
        Paragraph(f"<b>{headers_liq[0]}</b>", cell_header),
        Paragraph(f"<b>{headers_liq[1]}</b>", cell_header_center),
        Paragraph(f"<b>{headers_liq[2]}</b>", cell_header_center),
        Paragraph(f"<b>{headers_liq[3]}</b>", cell_header_center),
        Paragraph(f"<b>{headers_liq[4]}</b>", cell_header_right),
        Paragraph(f"<b>{headers_liq[5]}</b>", cell_header_right),
    ]]

    for _, row in df_liq.iterrows():
        data_liq.append([
            Paragraph(f"<b>{row['Pagador']}</b>", cell_style),
            Paragraph(row["Data Ocorrência"], cell_center),
            Paragraph(row["Data Vencimento"], cell_center),
            Paragraph(row["Data Crédito"], cell_center),
            Paragraph(f"<b>{row['Valor Crédito']}</b>", cell_right),
            Paragraph(row["Valor Documento"], cell_right),
        ])

    t_liq = Table(data_liq, colWidths=[180, 100, 100, 100, 130, 130])
    t_liq.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#276749")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C6F6D5")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F0FFF4")]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    elements.append(t_liq)
    elements.append(Spacer(1, 10))

    # 3. SEÇÃO 2: DETALHAMENTO GERAL DO LOTE
    elements.append(
        Paragraph("📋 2. Detalhamento Geral de Títulos do Lote", section_style)
    )

    headers_geral = [
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

    data_geral = [[
        Paragraph(f"<b>{headers_geral[0]}</b>", cell_header),
        Paragraph(f"<b>{headers_geral[1]}</b>", cell_header_center),
        Paragraph(f"<b>{headers_geral[2]}</b>", cell_header),
        Paragraph(f"<b>{headers_geral[3]}</b>", cell_header),
        Paragraph(f"<b>{headers_geral[4]}</b>", cell_header),
        Paragraph(f"<b>{headers_geral[5]}</b>", cell_header_center),
        Paragraph(f"<b>{headers_geral[6]}</b>", cell_header_center),
        Paragraph(f"<b>{headers_geral[7]}</b>", cell_header_right),
        Paragraph(f"<b>{headers_geral[8]}</b>", cell_header_right),
    ]]

    for _, row in df.iterrows():
        data_geral.append([
            Paragraph(row["Ocorrência"], cell_style),
            Paragraph(row["Data Ocorrência"], cell_center),
            Paragraph(row["Pagador"], cell_style),
            Paragraph(row["CPF/CNPJ"], cell_style),
            Paragraph(row["Uso da Empresa"], cell_style),
            Paragraph(row["Data Vencimento"], cell_center),
            Paragraph(row["Data Crédito"], cell_center),
            Paragraph(row["Valor Crédito"], cell_right),
            Paragraph(row["Valor Documento"], cell_right),
        ])

    col_widths_geral = [115, 55, 115, 100, 65, 55, 55, 90, 90]
    t_geral = Table(data_geral, colWidths=col_widths_geral)
    t_geral.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            (
                "ROWBACKGROUNDS",
                (0, 1),
                (-1, -1),
                [colors.white, colors.HexColor("#F8FAFC")],
            ),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    elements.append(t_geral)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# Fluxo Principal do Streamlit
if uploaded_file:
    with st.spinner("Processando o arquivo e formatando o layout..."):
        df, beneficiario = parse_totalbank_pdf(uploaded_file)

    st.success(f"Concluído! {len(df)} registros processados.")

    # Exibição das Tabelas na Tela
    st.subheader("📌 Títulos Liquidados (Pagos)")
    df_liq_screen = df[df["Ocorrência"].str.contains("Liquidação", case=False, na=False)][[
        "Pagador",
        "Data Ocorrência",
        "Data Vencimento",
        "Data Crédito",
        "Valor Crédito",
        "Valor Documento",
    ]]
    st.dataframe(df_liq_screen, use_container_width=True)

    st.subheader("📋 Detalhamento Geral do Lote")
    st.dataframe(df, use_container_width=True)

    st.subheader("📥 Exportar Relatórios")
    col1, col2, col3 = st.columns(3)

    with col1:
        pdf_bytes = gerar_pdf_relatorio(df, beneficiario)
        st.download_button(
            label="📄 Baixar PDF Executivo",
            data=pdf_bytes,
            file_name="relatorio_retorno_bancario_premium.pdf",
            mime="application/pdf",
        )

    with col2:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_liq_screen.to_excel(
                writer, index=False, sheet_name="Liquidações"
            )
            df.to_excel(writer, index=False, sheet_name="Geral")
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
