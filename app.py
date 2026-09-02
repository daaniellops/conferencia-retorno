import io
import re
import pandas as pd
import pdfplumber
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Configuração da página Streamlit
st.set_page_config(
    page_title="Extrator Total Bank - Retorno Bancário",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Extrator & Conciliador de Retorno Bancário - Total Bank")
st.markdown(
    "Upload de arquivos de retorno do Total Bank com extração estruturada de ocorrências, pagadores, imóveis e valores."
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


def summarize_occurrence(occ_text):
    """Limpa e resume a ocorrência para os termos padronizados."""
    if not occ_text or occ_text == "-":
        return "-"
    
    occ_upper = occ_text.upper()
    if "LIQUIDAÇÃO" in occ_upper or "LIQUIDACAO" in occ_upper:
        return "Liquidação"
    elif "BAIXA" in occ_upper:
        return "Baixa"
    elif "DEVOLUÇÃO" in occ_upper or "DEVOLUCAO" in occ_upper:
        return "Devolução"
    elif "TARIFA" in occ_upper or "CUSTAS" in occ_upper:
        return "Débito de Tarifas/Custas"
    elif "ENTRADA" in occ_upper:
        return "Entrada Confirmada"
    elif "ALTERAÇÃO" in occ_upper or "ALTERACAO" in occ_upper:
        return "Alteração de Dados"
    
    # Caso seja outro tipo, remove o prefixo numérico se houver
    clean = re.sub(r"^\d{2}-", "", occ_text).strip()
    return clean.split()[0] if clean else occ_text


def extract_data_from_pdf(pdf_file):
    """Realiza a leitura precisa do PDF por extração de palavras e posições."""
    full_text = ""
    beneficiario = "NÃO IDENTIFICADO"

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    # Captura nome do Beneficiário
    match_ben = re.search(r"Beneficiário:\s*(.*)", full_text)
    if match_ben:
        beneficiario = match_ben.group(1).split("NSA:")[0].split("|")[0].strip()

    # Separação de blocos por ocorrências (Ex: 06-Liquidação, 09-Baixa, 02-Entrada)
    blocks = re.split(r"\n(?=\d{2}-[A-Za-zÀ-ÿ])", full_text)
    
    records = []
    totais_pdf = {"tarifas": 0.0, "credito": 0.0, "pago": 0.0, "doc": 0.0}

    for b in blocks:
        # Pula cabeçalhos e resumos finais
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
            "Seu Número", "Forma Pagamento", "Imóvel", "Data Vencimento",
            "Data Crédito", "Valor Pago", "Valor Original"
        ])

    return df, beneficiario, totais_pdf


def parse_single_block(block_text):
    """Extrai exatamente os campos conforme especificado na regra de negócio."""
    lines = [l.strip() for l in block_text.split("\n") if l.strip()]
    if not lines or not re.match(r"^\d{2}-", lines[0]):
        return None

    # 1. Ocorrência Resumida
    raw_occ = lines[0]
    ocorrencia_resumida = summarize_occurrence(raw_occ)

    # 2. CPF / CNPJ
    cnpj_match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}", block_text)
    cpf_cnpj = cnpj_match.group(0) if cnpj_match else "-"

    # 3. Datas (dd/mm/aaaa)
    dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", block_text)
    dt_ocorrencia = dates[0] if len(dates) > 0 else "-"
    dt_vencimento = dates[1] if len(dates) > 1 else "-"
    dt_credito = dates[2] if len(dates) > 2 else "-"

    # 4. Valores Monetários (R$ X.XXX,XX)
    raw_values = re.findall(r"R\$\s*[\d\.]+\,\d{2}", block_text)
    vals = [clean_currency(v) for v in raw_values]

    v_tarifa = 0.0
    v_pago = 0.0
    v_original = 0.0

    if "Liquidação" in ocorrencia_resumida:
        if len(vals) >= 4:
            v_tarifa = vals[0]
            v_pago = vals[1]
            v_original = vals[3]
        elif len(vals) >= 2:
            v_pago = vals[0]
            v_original = vals[-1]
    else:
        if len(vals) >= 2:
            v_tarifa = vals[0]
            v_original = vals[-1]
        elif len(vals) == 1:
            v_original = vals[0]

    # 5. Seu Número
    seu_num_match = re.search(r"\b(140000000\d{6,10}|\d{10,20})\b", block_text)
    seu_numero = seu_num_match.group(0) if seu_num_match else "-"

    # 6. Canal / Forma de Pagamento
    forma_pag = "-"
    if "Cartão de crédito" in block_text or "Dinheiro" in block_text:
        forma_pag = "Cartão / Dinheiro"
    elif "DDA" in block_text:
        forma_pag = "DDA"
    elif "Pix" in block_text or "PIX" in block_text:
        forma_pag = "PIX"
    elif "Boleto" in block_text:
        forma_pag = "Boleto"

    # 7. Pagador (Identificação do Nome)
    pagador = "-"
    for line in lines[1:]:
        # Descarta linhas que contenham datas, números de documentos, URLs ou valores
        if re.search(r"\d{2}/\d{2}/\d{4}|R\$|\d{2}\.\d{3}\.\d{3}", line):
            continue
        if "LOJA" in line or "CLARICELL" in line or "TOTAL BANK" in line:
            continue
        cleaned = re.sub(r"[0-9\-]", "", line).strip()
        if len(cleaned) > 3:
            pagador = line.strip()
            break

    # 8. Imóvel (antigo Uso Empresa)
    imovel = "-"
    imovel_match = re.search(r"(LOJA-[A-Z0-9\-]+|CLARICELL|LOJA\s*\d+[A-Z\ -]*|[A-Z0-9]{4,15})", block_text)
    if imovel_match and imovel_match.group(0) not in pagador:
        imovel = imovel_match.group(0)

    return {
        "Ocorrência": ocorrencia_resumida,
        "Data Ocorrência": dt_ocorrencia,
        "Pagador": pagador,
        "CPF/CNPJ": cpf_cnpj,
        "Seu Número": seu_numero,
        "Forma Pagamento": forma_pag,
        "Imóvel": imovel,
        "Data Vencimento": dt_vencimento,
        "Data Crédito": dt_credito,
        "Valor Pago": format_currency(v_pago),
        "Valor Original": format_currency(v_original),
        "_num_tarifa": v_tarifa,
        "_num_pago": v_pago,
        "_num_original": v_original,
    }


def gerar_pdf_relatorio(df, beneficiario, totais_pdf):
    """Gera o relatório em PDF atualizado com os novos nomes de colunas e layout executivo."""
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

    # Header
    elements.append(Paragraph("Relatório de Análise de Retorno Bancário", title_style))
    elements.append(
        Paragraph(
            f"<b>Beneficiário:</b> {beneficiario} &nbsp;|&nbsp; <b>Banco Emissor:</b> TOTAL BANK &nbsp;|&nbsp; <b>Total de Registros:</b> {len(df)}",
            meta_style,
        )
    )

    # 1. RESUMO DE LIQUIDAÇÕES
    df_liq = df[df["Ocorrência"].str.contains("Liquidação", case=False, na=False)]

    if not df_liq.empty:
        elements.append(
            Paragraph("📌 1. Resumo Exclusivo de Títulos Liquidados (Pagos)", section_style)
        )

        headers_liq = [
            "Ocorrência", "Data Ocorr.", "Pagador / CPF / CNPJ", 
            "Imóvel", "Data Venc.", "Data Crédito", "Valor Pago", "Valor Original"
        ]

        data_liq = [[
            Paragraph(f"<b>{headers_liq[0]}</b>", cell_header),
            Paragraph(f"<b>{headers_liq[1]}</b>", cell_header_center),
            Paragraph(f"<b>{headers_liq[2]}</b>", cell_header),
            Paragraph(f"<b>{headers_liq[3]}</b>", cell_header),
            Paragraph(f"<b>{headers_liq[4]}</b>", cell_header_center),
            Paragraph(f"<b>{headers_liq[5]}</b>", cell_header_center),
            Paragraph(f"<b>{headers_liq[6]}</b>", cell_header_right),
            Paragraph(f"<b>{headers_liq[7]}</b>", cell_header_right),
        ]]

        for _, row in df_liq.iterrows():
            pag_str = f"{row['Pagador']} ({row['CPF/CNPJ']})" if row['CPF/CNPJ'] != "-" else row['Pagador']
            data_liq.append([
                Paragraph(row["Ocorrência"], cell_bold),
                Paragraph(row["Data Ocorrência"], cell_center),
                Paragraph(pag_str, cell_style),
                Paragraph(row["Imóvel"], cell_style),
                Paragraph(row["Data Vencimento"], cell_center),
                Paragraph(row["Data Crédito"], cell_center),
                Paragraph(f"<b>{row['Valor Pago']}</b>", cell_right),
                Paragraph(row["Valor Original"], cell_right),
            ])

        t_liq = Table(data_liq, colWidths=[80, 60, 210, 80, 60, 60, 110, 110])
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

    # 2. DETALHAMENTO GERAL DO LOTE
    elements.append(
        Paragraph("📋 2. Detalhamento Geral de Títulos do Lote", section_style)
    )

    headers_geral = [
        "Ocorrência", "Data Ocorr.", "Pagador", "CPF/CNPJ", 
        "Seu Número", "Forma Pag.", "Imóvel", "Data Venc.", "Data Crédito", "Valor Pago", "Valor Original"
    ]

    data_geral = [[
        Paragraph(f"<b>{headers_geral[0]}</b>", cell_header),
        Paragraph(f"<b>{headers_geral[1]}</b>", cell_header_center),
        Paragraph(f"<b>{headers_geral[2]}</b>", cell_header),
        Paragraph(f"<b>{headers_geral[3]}</b>", cell_header),
        Paragraph(f"<b>{headers_geral[4]}</b>", cell_header),
        Paragraph(f"<b>{headers_geral[5]}</b>", cell_header),
        Paragraph(f"<b>{headers_geral[6]}</b>", cell_header),
        Paragraph(f"<b>{headers_geral[7]}</b>", cell_header_center),
        Paragraph(f"<b>{headers_geral[8]}</b>", cell_header_center),
        Paragraph(f"<b>{headers_geral[9]}</b>", cell_header_right),
        Paragraph(f"<b>{headers_geral[10]}</b>", cell_header_right),
    ]]

    for _, row in df.iterrows():
        data_geral.append([
            Paragraph(row["Ocorrência"], cell_style),
            Paragraph(row["Data Ocorrência"], cell_center),
            Paragraph(row["Pagador"], cell_style),
            Paragraph(row["CPF/CNPJ"], cell_style),
            Paragraph(row["Seu Número"], cell_style),
            Paragraph(row["Forma Pagamento"], cell_style),
            Paragraph(row["Imóvel"], cell_style),
            Paragraph(row["Data Vencimento"], cell_center),
            Paragraph(row["Data Crédito"], cell_center),
            Paragraph(row["Valor Pago"], cell_right),
            Paragraph(row["Valor Original"], cell_right),
        ])

    t_geral = Table(data_geral, colWidths=[80, 50, 110, 85, 80, 75, 55, 50, 50, 65, 65])
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

    # 3. CONSOLIDAÇÃO DE TOTAIS
    tot_tarifa = df["_num_tarifa"].sum() if "_num_tarifa" in df else totais_pdf["tarifas"]
    tot_pago = df["_num_pago"].sum() if "_num_pago" in df else totais_pdf["pago"]
    tot_original = df["_num_original"].sum() if "_num_original" in df else totais_pdf["doc"]

    data_totais = [
        [
            Paragraph("<b>TOTAIS CONSOLIDADOS DO LOTE</b>", cell_header),
            Paragraph(f"<b>VALOR TARIFAS:</b> {format_currency(tot_tarifa)}", cell_header),
            Paragraph(f"<b>VALOR PAGO TOTAL:</b> {format_currency(tot_pago)}", cell_header),
            Paragraph(f"<b>VALOR ORIGINAL TOTAL:</b> {format_currency(tot_original)}", cell_header),
        ]
    ]

    t_totais = Table(data_totais, colWidths=[200, 180, 190, 190])
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


# Fluxo do App
if uploaded_file:
    with st.spinner("Lendo e estruturando dados do PDF..."):
        df, beneficiario, totais_pdf = extract_data_from_pdf(uploaded_file)

    st.success(f"Concluído! {len(df)} registros processados.")

    df_liq_screen = df[df["Ocorrência"].str.contains("Liquidação", case=False, na=False)]

    if not df_liq_screen.empty:
        st.subheader("📌 Títulos Liquidados (Pagos)")
        st.dataframe(
            df_liq_screen[[
                "Ocorrência", "Data Ocorrência", "Pagador", "CPF/CNPJ",
                "Imóvel", "Data Vencimento", "Data Crédito", "Valor Pago", "Valor Original"
            ]],
            use_container_width=True,
        )

    st.subheader("📋 Detalhamento Geral do Lote")
    st.dataframe(
        df[[
            "Ocorrência", "Data Ocorrência", "Pagador", "CPF/CNPJ",
            "Seu Número", "Forma Pagamento", "Imóvel", "Data Vencimento",
            "Data Crédito", "Valor Pago", "Valor Original"
        ]],
        use_container_width=True,
    )

    # Exibição dos Totais no Streamlit
    tot_pago = df["_num_pago"].sum() if "_num_pago" in df else 0.0
    tot_orig = df["_num_original"].sum() if "_num_original" in df else 0.0
    tot_tarifa = df["_num_tarifa"].sum() if "_num_tarifa" in df else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Valor Tarifas Total", format_currency(tot_tarifa))
    c2.metric("Valor Pago Total", format_currency(tot_pago))
    c3.metric("Valor Original Total", format_currency(tot_orig))

    st.subheader("📥 Exportar Relatórios")
    col1, col2, col3 = st.columns(3)

    cols_export = [
        "Ocorrência", "Data Ocorrência", "Pagador", "CPF/CNPJ",
        "Seu Número", "Forma Pagamento", "Imóvel", "Data Vencimento",
        "Data Crédito", "Valor Pago", "Valor Original"
    ]

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
