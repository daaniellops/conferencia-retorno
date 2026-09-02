# PROMPT DE DESENVOLVIMENTO: Gerador de Relatório PDF de Retorno Bancário

Você é um desenvolvedor Python sênior especializado em automação financeira e geração de relatórios corporativos.

## OBJETIVO
Desenvolver/atualizar o código no repositório do GitHub para que, após processar o PDF de retorno do Total Bank, o sistema gere automaticamente um **Relatório PDF formatado e estilizado**, pronto para download ou envio por e-mail.

---

## 1. CAMPOS OBRIGATÓRIOS DO RELATÓRIO PDF

O relatório em PDF deve conter obrigatoriamente os seguintes campos extraídos do arquivo de retorno:

1. **Cabeçalho Executivo**:
   - **Beneficiário**: Razão Social constante no relatório (ex: ASSOCIACAO DOS LOJISTAS DO ITA SHOPPING CENTRO-RATEIO).
   - **Banco Emissor**: Total Bank
   - **Data do Processamento**: Data de extração/emissão do relatório (DD/MM/AAAA).
   - **Total de Registros Analisados**: Quantidade total de títulos no lote.

2. **Tabela Detalhada dos Títulos**:
   - **Ocorrência**: Descrição/Código da ocorrência (ex: `06-Liquidação`, `02-Entrada Confirmada`, `45-Alteração de Dados`, `28-Débito de Tarifas/Custas`).
   - **Data da Ocorrência**: Data em que ocorreu o registro.
   - **Pagador**: Nome / Razão Social do Pagador.
   - **CPF/CNPJ**: Número do documento do pagador.
   - **Uso da Empresa**: Código de identificação interno (ex: `LOJA-26-A`, `CLARICELL`).
   - **Data de Vencimento**: Data de vencimento original do título.
   - **Data Crédito**: Data de entrada do valor na conta (se houver; caso contrário, indicar `-`).
   - **Valor Crédito**: Valor efetivamente pago/creditado em conta (R$).
   - **Valor Documento**: Valor original do documento/título (R$).

3. **Tabela de Resumo e Consolidação Financeira (Rodapé do Relatório)**:
   - Agrupamento dos títulos por **Tipo de Ocorrência** com a quantidade de títulos em cada tipo.
   - **Soma Total do Valor Crédito (R$)** e **Soma Total do Valor Documento (R$)**.
   - Linha de **TOTAL GERAL DO LOTE**.

---

## 2. REQUISITOS TÉCNICOS E FORMATAÇÃO (PDF)

- **Biblioteca Recomendada**: Utilize `reportlab` (ou `FPDF2`) em Python para gerar o PDF via buffer em memória (`io.BytesIO`).
- **Design & Paleta de Cores**:
  - Estilo corporativo com tons de azul escuro (`#1A365D`) nos títulos e azul primário (`#2B6CB0`) nos cabeçalhos de tabela.
  - Linhas zebradas (fundo claro alternado `#F8FAFC`) para facilitar a leitura.
  - Fonte padrão clara e legível (Helvetica / Arial), com margens de 15 a 20mm.
- **Valores Monetários e Ausentes**:
  - Todos os valores numéricos devem estar formatados no padrão brasileiro (`R$ X.XXX,XX`).
  - Campos não informados (como Data de Crédito em títulos pendentes) devem ser exibidos como `-` ou `N/A`.

---

## 3. INTEGRAÇÃO NO STREAMLIT (`app.py`)

Adicione ao script do aplicativo um botão dedicado para a exportação do PDF:

```python
st.download_button(
    label="📄 Baixar Relatório Completo em PDF",
    data=pdf_bytes,
    file_name="Relatorio_Retorno_Bancario_TotalBank.pdf",
    mime="application/pdf",
)
