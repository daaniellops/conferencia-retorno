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
    "Upload e processamento dinâmico do relatório Total Bank com fonte reduzida, extração corrigida e linha de totais."
)

uploaded_file = st.file_uploader(
    "Selecione o arquivo PDF do Total Bank", type=["pdf"]
)


def clean_currency(val_str):
    """Converte string de moeda (R$ 1.234,56) para float."""
    if not val_str or val_str == "-":
        return 0.0
    clean = re.sub(r"[^\d,]", "", val_str).replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return 0.0


def format_currency(val):
    """Formatador de float para R$ X.XXX,XX."""
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def extract_data_from_pdf(pdf_file):
    """Lê as páginas do PDF do Total Bank de forma limpa e precisa."""
    full_text = ""
    beneficiario = "NÃO IDENTIFICADO"

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    # Captura Beneficiário
    match_ben = re.search(r"Beneficiário:\s*(.*)", full_text)
    if match_ben:
        beneficiario = match_ben.group(1).split("NSA:")[0].strip()

    # Filtra linhas inúteis de cabeçalhos/rodapés do portal
    ignored_patterns = [
        r"^Relatório de títulos",
        r"^Página \d+",
        r"^Enviado",
        r"^Retorno enviado",
        r"^http",
        r"^TOTAL BANK",
        r"^\d{2}/\d{2}/\d{4}\s+\d{2}\.\d{2}",
    ]

    lines = []
    for line in full_text.split("\n"):
        line_s = line.strip()
        if not line_s:
            continue
        if any(re.search(pat, line_s, re.IGNORECASE) for pat in ignored_patterns):
            continue
        lines.append(line_s)

    # Agrupa por blocos de ocorrência
    blocks = []
    current_block = []

    for line in lines:
        if re.match(r"^\d{2}-", line):
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
        current_block.append(line)

    if current_block:
        blocks.append("\n".join(current_block))

    records = []
    totais_pdf = {"tarifas": 0.0, "credito": 0.0, "pago": 0.0, "doc": 0.0}

    for b in blocks:
        # Se for o bloco final de Totais do próprio PDF
        if "Totais para este filtro" in b or "Resumo da ocorrência" in b:
            vals = re.findall(r"R\$\s*[\d\.]+\,\d{2}", b)
            if len(vals) >= 4:
                totais_pdf["tarifas"] += clean_currency(vals[0])
                totais_pdf["credito"] += clean_currency(vals[1])
                totais_pdf["pago"] += clean_currency(vals[2])
                totais_pdf["doc"] += clean_currency(vals[3])
            continue

        item = parse_single_block(b)
        if item:
            records.append(item)

    df = pd.DataFrame(records)

    if df.empty:
        df = pd.DataFrame(columns=[
            "Ocorrência", "Data Ocorrência", "Pagador", "CPF/CNPJ",
            "Uso da Empresa", "Data Vencimento", "Data Crédito",
            "Valor Tarifa", "Valor Crédito", "Valor Pago", "Valor Documento"
        ])

    return df, beneficiario, totais_pdf


def parse_single_block(block_text):
    """Extrai os dados reais de cada título individual sem misturar informações."""
    lines = [l.strip() for l in block_text.split("\n") if l.strip()]
    if not lines:
        return None

    # Ocorrência limpa (ex: 06-Liquidação)
    raw_occ = lines[0]
    occ_match = re.match(r"^(\d{2}-[A-Za-zÀ-ÿ\/\s]+)", raw_occ)
    ocorrencia = occ_match.group(1).strip() if occ_match else raw_occ

    # Busca CPF/CNPJ
    cnpj_match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}", block_text)
    cpf_cnpj = cnpj_match.group(0) if cnpj_match else "-"

    # Busca Datas (dd/mm/aaaa)
    dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", block_text)
    dt_ocorrencia = dates[0] if len(dates) > 0 else "-"
    dt_vencimento = dates[1] if len(dates) > 1 else "-"
    dt_credito = dates[2] if len(dates) > 2 else "-"

    # Busca Valores Monetários
    raw_values = re.findall(r"R\$\s*[\d\.]+\,\d{2}", block_text)
    vals = [clean_currency(v) for v in raw_values]

    v_tarifa = 0.0
    v_credito = 0.0
    v_pago = 0.0
    v_doc = 0.0

    if "Liquidação" in ocorrencia:
        if len(vals) >= 4:
            v_tarifa = vals[0]
            v_credito = vals[1]
            v_pago = vals[2]
            v_doc = vals[3]
        elif len(vals) == 3:
            v_credito = vals[0]
            v_pago = vals[1]
            v_doc = vals[2]
        elif len(vals) == 1:
            v_credito = vals[0]
            v_pago = vals[0]
            v_doc = vals[0]
    else:
        if len(vals) >= 2:
            v_tarifa = vals[0]
            v_doc = vals[-1]
        elif len(vals) == 1:
            v_doc = vals[0]

    # Nome do Pagador
    pagador = "-"
    # Linhas intermediárias contêm o pagador
    for line in lines[1:]:
        cleaned_line = re.sub(r"\d{2}/\d{2}/\d{4}|R\$\s*[\d\.]+\,\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", "", line).strip()
        if cleaned_line and not cleaned_line.startswith("LOJA") and not cleaned_line.isdigit():
            pagador = cleaned_line
            break

    # Uso Empresa
    uso_empresa = "-"
    uso_match = re.search(r"(LOJA-[A-Z0-9\-]+|CLARICELL|SHOPPING|[A-Z0-9]{4,12})", block_text)
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
        "Valor Tarifa": format_currency(v_tarifa),
        "Valor Crédito": format_currency(v_credito),
        "Valor Pago": format_currency(v_pago),
        "Valor Documento": format_currency(v_doc),
        "_num_tarifa": v_tarifa,
        "_num_credito": v_credito,
        "_num_pago": v_pago,
        "_num_doc": v_doc,
    }


def gerar_pdf_relatorio(df, beneficiario, totais_pdf):
    """Gera o PDF com fonte reduzida e tabela de totais acumulados."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12,
        leftMargin=12,
        topMargin=12,
        bottomMargin=12,
    )
    elements = []
    styles = getSampleStyleSheet()

    # Estilos com fonte menor
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=2,
    )

    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=colors.HexColor("#1A365D"),
        spaceBefore=8,
        spaceAfter=4,
    )

    meta_style = ParagraphStyle(
        "MetaStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=6,
    )

    # Fonte das Células da Tabela (Reduzida para 6.5pt)
    cell_style = ParagraphStyle(
        "CellStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
    )

    cell_bold = ParagraphStyle("CellBold", parent=cell_style, fontName="Helvetica-Bold")
    cell_center = ParagraphStyle("CellCenter", parent=cell_style, alignment=1)
    cell_right = ParagraphStyle("CellRight", parent=cell_style, alignment=2)

    cell_header = ParagraphStyle(
        "CellHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=colors.white,
        leading=9,
    )
    cell_header_center = ParagraphStyle("CellHeaderCenter", parent=cell_header, alignment=1)
    cell_header_right = ParagraphStyle("CellHeaderRight", parent=cell_header, alignment=2)

    # Cabeçalho
    elements.append(Paragraph("Relatório de Análise de Retorno Bancário", title_style))
    elements.append(
        Paragraph(
            f"<b>Beneficiário:</b> {beneficiario} &nbsp;|&nbsp; <b>Banco Emissor:</b> TOTAL BANK &nbsp;|&nbsp; <b>Total de Registros:</b> {len(df)}",
            meta_style,
        )
    )

    # 1. RESUMO EXCLUSIVO DE LIQUIDAÇÕES
    df_liq = df[df["Ocorrência"].str.contains("Liquidação", case=False, na=False)]

    if not df_liq.empty:
        elements.append(
            Paragraph("📌 1. Resumo Exclusivo de Títulos Liquidados (Pagos)", section_style)
        )

        headers_liq = [
            "Ocorrência", "Data Ocorr.", "Pagador / CPF / CNPJ", 
            "Data Venc.", "Data Crédito", "Valor Creditado", "Valor Original Doc."
        ]

        data_liq = [[
            Paragraph(f"<b>{headers_liq[0]}</b>", cell_header),
            Paragraph(f"<b>{headers_liq[1]}</b>", cell_header_center),
            Paragraph(f"<b>{headers_liq[2]}</b>", cell_header),
            Paragraph(f"<b>{headers_liq[3]}</b>", cell_header_center),
            Paragraph(f"<b>{headers_liq[4]}</b>", cell_header_center),
            Paragraph(f"<b>{headers_liq[5]}</b>", cell_header_right),
            Paragraph(f"<b>{headers_liq[6]}</b>", cell_header_right),
        ]]

        for _, row in df_liq.iterrows():
            pag_str = f"{row['Pagador']} ({row['CPF/CNPJ']})" if row['CPF/CNPJ'] != "-" else row['Pagador']
            data_liq.append([
                Paragraph(row["Ocorrência"], cell_bold),
                Paragraph(row["Data Ocorrência"], cell_center),
                Paragraph(pag_str, cell_style),
                Paragraph(row["Data Vencimento"], cell_center),
                Paragraph(row["Data Crédito"], cell_center),
                Paragraph(f"<b>{row['Valor Crédito']}</b>", cell_right),
                Paragraph(row["Valor Documento"], cell_right),
            ])

        t_liq = Table(data_liq, colWidths=[100, 70, 220, 70, 70, 115, 115])
        t_liq.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#276749")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C6F6D5")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F0FFF4")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(t_liq)
        elements.append(Spacer(1, 6))

    # 2. DETALHAMENTO GERAL
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

    t_geral = Table(data_geral, colWidths=[120, 60, 140, 110, 65, 60, 60, 75, 75])
    t_geral.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    elements.append(t_geral)
    elements.append(Spacer(1, 8))

    # 3. TABELA DE TOTAIS
    tot_tarifa = df["_num_tarifa"].sum() if "_num_tarifa" in df else totais_pdf["tarifas"]
    tot_credito = df["_num_credito"].sum() if "_num_credito" in df else totais_pdf["credito"]
    tot_pago = df["_num_pago"].sum() if "_num_pago" in df else totais_pdf["pago"]
    tot_doc = df["_num_doc"].sum() if "_num_doc" in df else totais_pdf["doc"]

    data_totais = [
        [
            Paragraph("<b>TOTAIS CONSOLIDADOS DO LOTE</b>", cell_header),
            Paragraph(f"<b>VALOR TARIFAS:</b> {format_currency(tot_tarifa)}", cell_header),
            Paragraph(f"<b>VALOR CRÉDITO:</b> {format_currency(tot_credito)}", cell_header),
            Paragraph(f"<b>VALOR PAGO:</b> {format_currency(tot_pago)}", cell_header),
            Paragraph(f"<b>VALOR DOC. ORIGINAL:</b> {format_currency(tot_doc)}", cell_header),
        ]
    ]

    t_totais = Table(data_totais, colWidths=[160, 150, 150, 150, 150])
    t_totais.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1A365D")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1A365D")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    elements.append(t_totais)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# Fluxo Principal Streamlit
if uploaded_file:
    with st.spinner("Processando o arquivo e ajustando campos..."):
        df, beneficiario, totais_pdf = extract_data_from_pdf(uploaded_file)

    st.success(f"Concluído! {len(df)} registros processados.")

    # Visualização na Tela
    df_liq_screen = df[df["Ocorrência"].str.contains("Liquidação", case=False, na=False)]

    if not df_liq_screen.empty:
        st.subheader("📌 Títulos Liquidados (Pagos)")
        st.dataframe(
            df_liq_screen[[
                "Ocorrência", "Data Ocorrência", "Pagador", "CPF/CNPJ",
                "Data Vencimento", "Data Crédito", "Valor Crédito", "Valor Documento"
            ]],
            use_container_width=True,
        )

    st.subheader("📋 Detalhamento Geral do Lote")
    st.dataframe(
        df[[
            "Ocorrência", "Data Ocorrência", "Pagador", "CPF/CNPJ",
            "Uso da Empresa", "Data Vencimento", "Data Crédito",
            "Valor Crédito", "Valor Documento"
        ]],
        use_container_width=True,
    )

    # Exibição dos Totais no Streamlit
    tot_credito = df["_num_credito"].sum() if "_num_credito" in df else 0.0
    tot_doc = df["_num_doc"].sum() if "_num_doc" in df else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Valor Tarifas Total", format_currency(df["_num_tarifa"].sum() if "_num_tarifa" in df else 0.0))
    c2.metric("Valor Crédito Total", format_currency(tot_credito))
    c3.metric("Valor Pago Total", format_currency(df["_num_pago"].sum() if "_num_pago" in df else 0.0))
    c4.metric("Valor Documentos Total", format_currency(tot_doc))

    st.subheader("📥 Exportar Relatórios Corrigidos")
    col1, col2, col3 = st.columns(3)

    with col1:
        pdf_bytes = gerar_pdf_relatorio(df, beneficiario, totais_pdf)
        st.download_button(
            label="📄 Baixar PDF Executivo",
            data=pdf_bytes,
            file_name="relatorio_retorno_bancario.pdf",
            mime="application/pdf",
        )

    with col2:
        excel_buffer = io.BytesIO()
        cols_export = [
            "Ocorrência", "Data Ocorrência", "Pagador", "CPF/CNPJ",
            "Uso da Empresa", "Data Vencimento", "Data Crédito",
            "Valor Tarifa", "Valor Crédito", "Valor Pago", "Valor Documento"
        ]
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            if not df_liq_screen.empty:
                df_liq_screen[cols_export].to_excel(writer, index=False, sheet_name="Liquidações")
            df[cols_export].to_excel(writer, index=False, sheet_name="Geral")
        st.download_button(
            label="📊 Baixar Excel (.xlsx)",
            data=excel_buffer.getvalue(),
            file_name="relatorio_titulos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col3:
        csv_buffer = io.StringIO()
        df[cols_export].to_csv(csv_buffer, index=False, sep=";")
        st.download_button(
            label="📥 Baixar CSV (para Excel)",
            data=csv_buffer.getvalue(),
            file_name="relatorio_titulos.csv",
            mime="text/csv",
        )
else:
    st.info("Aguardando upload do arquivo PDF do Total Bank...")
