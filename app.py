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
    page_title="Extrator Total Bank - Relatório Dinâmico",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Extrator & Conciliador de Títulos - Total Bank")
st.markdown(
    "Faça o upload do relatório em PDF para extrair os dados dinamicamente e gerar o relatório corporativo."
)

uploaded_file = st.file_uploader(
    "Selecione o arquivo PDF do Total Bank", type=["pdf"]
)


def extract_data_from_pdf(pdf_file):
    """Lê dinamicamente as páginas do PDF do Total Bank e extrai os títulos por Regex."""
    full_text = ""
    beneficiario = "NÃO IDENTIFICADO"

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    # Captura o nome do Beneficiário
    match_ben = re.search(r"Beneficiário:\s*(.*)", full_text)
    if match_ben:
        beneficiario = match_ben.group(1).strip()

    # Divide o texto por blocos de ocorrência
    lines = [line.strip() for line in full_text.split("\n") if line.strip()]
    records = []
    
    current_block = []
    for line in lines:
        # Padrão de início de título (ex: 06-Liquidação, 02-Entrada Confirmada, etc)
        if re.match(r"^\d{2}-", line):
            if current_block:
                parsed = parse_single_block("\n".join(current_block))
                if parsed:
                    records.append(parsed)
                current_block = []
        current_block.append(line)
    
    if current_block:
        parsed = parse_single_block("\n".join(current_block))
        if parsed:
            records.append(parsed)

    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=[
            "Ocorrência", "Data Ocorrência", "Pagador", "CPF/CNPJ", 
            "Uso da Empresa", "Data Vencimento", "Data Crédito", 
            "Valor Crédito", "Valor Documento"
        ])
        
    return df, beneficiario


def parse_single_block(block_text):
    """Extrai os campos específicos de um bloco individual de título."""
    # Ignora blocos de totalização/resumo
    if "Resumo da ocorrência" in block_text or "Totais para este filtro" in block_text:
        return None

    lines = [l.strip() for l in block_text.split("\n") if l.strip()]
    
    ocorrencia = lines[0] if len(lines) > 0 else "-"
    
    # Extrai CNPJ/CPF se houver
    cnpj_match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}", block_text)
    cpf_cnpj = cnpj_match.group(0) if cnpj_match else "-"

    # Extrai Datas (dd/mm/aaaa)
    dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", block_text)
    dt_ocorrencia = dates[0] if len(dates) > 0 else "-"
    dt_vencimento = dates[1] if len(dates) > 1 else "-"
    dt_credito = dates[2] if len(dates) > 2 else "-"

    # Extrai Valores Monetários (R$ X.XXX,XX ou R$ X,XX)
    values = re.findall(r"R\$\s*[\d\.]+\,\d{2}", block_text)
    
    # Mapeamento dinâmico dos valores
    valor_credito = "R$ 0,00"
    valor_doc = "R$ 0,00"

    if "Liquidação" in ocorrencia:
        if len(values) >= 2:
            valor_credito = values[-2]
            valor_doc = values[-1]
        elif len(values) == 1:
            valor_credito = values[0]
            valor_doc = values[0]
    else:
        if len(values) >= 1:
            valor_doc = values[-1]

    # Extrai Pagador e Uso Empresa com base na estrutura de linhas
    pagador = "-"
    uso_empresa = "-"

    if len(lines) > 1:
        # A segunda linha geralmente contém a Data da Ocorrência e o Nome do Pagador
        line_pag = re.sub(r"\d{2}/\d{2}/\d{4}", "", lines[1]).strip()
        if line_pag and not line_pag.startswith("R$"):
            pagador = line_pag

    # Identificação de Uso Empresa (ex: LOJA-26-A, CLARICELL, LOJA-28)
    uso_match = re.search(r"(LOJA-[A-Z0-9\-]+|CLARICELL|[A-Z0-9]{4,10})", block_text)
    if uso_match and uso_match.group(0) not in pagador:
        uso_empresa = uso_match.group(0)

    return {
        "Ocorrência": ocorrencia,
        "Data Ocorrência": dt_ocorrencia,
        "Pagador": pagador,
        "CPF/CNPJ": cpf_cnpj,
        "Uso da Empresa": uso_empresa,
        "Data Vencimento": dt_vencimento,
        "Data Crédito": dt_credito,
        "Valor Crédito": valor_credito,
        "Valor Documento": valor_doc,
    }


def gerar_pdf_relatorio(df, beneficiario):
    """Gera o PDF estilizado dinamicamente."""
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

    cell_center = ParagraphStyle("CellCenter", parent=cell_style, alignment=1)
    cell_right = ParagraphStyle("CellRight", parent=cell_style, alignment=2)

    cell_header = ParagraphStyle(
        "CellHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.white,
        leading=10,
    )
    cell_header_center = ParagraphStyle("CellHeaderCenter", parent=cell_header, alignment=1)
    cell_header_right = ParagraphStyle("CellHeaderRight", parent=cell_header, alignment=2)

    # 1. Cabeçalho Principal
    elements.append(Paragraph("Relatório de Análise de Retorno Bancário", title_style))
    elements.append(
        Paragraph(
            f"<b>Beneficiário:</b> {beneficiario} &nbsp;|&nbsp; <b>Banco:</b> TOTAL BANK &nbsp;|&nbsp; <b>Total Títulos:</b> {len(df)}",
            meta_style,
        )
    )
    elements.append(Spacer(1, 4))

    # 2. Resumo de Liquidações
    df_liq = df[df["Ocorrência"].str.contains("Liquidação", case=False, na=False)]

    if not df_liq.empty:
        elements.append(
            Paragraph("📌 1. Resumo Exclusivo de Títulos Liquidados (Pagos)", section_style)
        )

        headers_liq = [
            "Pagador", "Data Ocorrência", "Data Vencimento", 
            "Data Crédito", "Valor Creditado", "Valor Doc. Original"
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

    # 3. Detalhamento Geral
    elements.append(
        Paragraph("📋 2. Detalhamento Geral de Títulos do Lote", section_style)
    )

    headers_geral = [
        "Ocorrência", "Data Ocorr.", "Pagador", "CPF/CNPJ", 
        "Uso Empresa", "Data Venc.", "Data Crédito", "Valor Crédito", "Valor Doc."
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
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
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
    with st.spinner("Lendo o PDF e processando dados..."):
        df, beneficiario = extract_data_from_pdf(uploaded_file)

    st.success(f"Concluído! {len(df)} registros extraídos com sucesso do arquivo atual.")

    # Exibição na Tela
    df_liq_screen = df[df["Ocorrência"].str.contains("Liquidação", case=False, na=False)]
    
    if not df_liq_screen.empty:
        st.subheader("📌 Títulos Liquidados (Pagos)")
        st.dataframe(
            df_liq_screen[[
                "Pagador", "Data Ocorrência", "Data Vencimento", 
                "Data Crédito", "Valor Crédito", "Valor Documento"
            ]],
            use_container_width=True,
        )

    st.subheader("📋 Detalhamento Geral do Lote")
    st.dataframe(df, use_container_width=True)

    st.subheader("📥 Exportar Relatórios")
    col1, col2, col3 = st.columns(3)

    with col1:
        pdf_bytes = gerar_pdf_relatorio(df, beneficiario)
        st.download_button(
            label="📄 Baixar PDF Executivo",
            data=pdf_bytes,
            file_name="relatorio_retorno_bancario.pdf",
            mime="application/pdf",
        )

    with col2:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            if not df_liq_screen.empty:
                df_liq_screen.to_excel(writer, index=False, sheet_name="Liquidações")
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
    st.info("Aguardando upload de um arquivo PDF do Total Bank...")
