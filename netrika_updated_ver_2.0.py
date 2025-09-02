"""<Netrika - AI based data analytics Tool>
    Copyright (C) <2025>  <harikrishnan R - hariiim2012@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>."""




import os
import json
import yaml
import duckdb
import pandas as pd
import requests
import streamlit as st
import re

st.set_page_config(
    page_title=" Netrika", 
    layout="wide",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Hide Streamlit default UI elements
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.stDeployButton {display:none;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# 🧠 Heading at the very top
st.markdown("<h1 style='text-align: center; color: #4A90E2;'>📊 Netrika </h1>", unsafe_allow_html=True)

# 🔐 API Key Section
st.sidebar.markdown("### 🔐 API Configuration")
DEFAULT_KEY = os.environ.get("GROQ_API_KEY", "")
api_key = st.sidebar.text_input("Enter Groq API Key", type="password", value=DEFAULT_KEY)
if st.sidebar.checkbox("Remember API Key", value=True):
    os.environ["GROQ_API_KEY"] = api_key

# 🌐 Language Toggle
language_toggle = st.sidebar.selectbox("Language", ["English", "Malayalam"])

# 🔬 Analysis Toggle
show_analysis = st.sidebar.checkbox("Show Analysis", value=True)

# 📁 File Upload Section
st.markdown("### 📁 Upload Your Data")
uploaded_files = st.file_uploader("Upload CSV or Excel files (Max 3)", type=["csv", "xls", "xlsx"], accept_multiple_files=True)

description_file = None
if uploaded_files and len(uploaded_files) > 1:
    description_file = st.file_uploader("Upload Description File (YAML/JSON)", type=["yaml", "yml", "json"])

# 🧠 Language detection helper
def detect_language(text):
    for ch in text:
        if '\u0D00' <= ch <= '\u0D7F':
            return "Malayalam"
    return "English"

@st.cache_resource
def load_single_file(file):
    con = duckdb.connect()
    df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
    table_name = re.sub(r'[^a-zA-Z0-9_]', '_', os.path.splitext(file.name)[0])
    con.register(table_name, df)
    return con, table_name, df

@st.cache_resource
def load_multiple_tables(file_list):
    con = duckdb.connect()
    table_names = []
    for file in file_list:
        table_name = re.sub(r'[^a-zA-Z0-9_]', '_', os.path.splitext(file.name)[0]).lower()
        try:
            df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
            con.register(table_name, df)
            table_names.append(table_name)
        except Exception as e:
            st.error(f"Failed to load {file.name}: {e}")
    return con, table_names

def parse_description_file(description_file):
    try:
        if description_file.name.endswith(('.yaml', '.yml')):
            return yaml.safe_load(description_file)
        else:
            return json.load(description_file)
    except Exception as e:
        st.error(f"Invalid description file: {e}")
        return {}

def build_schema_prompt(description_json):
    if not description_json:
        return "No schema was provided."
    prompt_lines = []
    for table in description_json.get("tables", []):
        prompt_lines.append(f"Table '{table['name']}': {table.get('description', '')}")
        for col, desc in table.get("columns", {}).items():
            prompt_lines.append(f'  - "{col}": {desc}')
    for rel in description_json.get("relationships", []):
        left = rel.get("left_table", "?")
        right = rel.get("right_table", "?")
        rel_type = rel.get("type", "unknown")
        on = rel.get("on")
        if not on:
            prompt_lines.append(f"Relationship: {left} ↔ {right} (NO KEY DEFINED)")
            continue
        if isinstance(on, list):
            on_str = " & ".join([f"{left}.{col} → {right}.{col}" for col in on])
        else:
            on_str = f"{left}.{on} → {right}.{on}"
        prompt_lines.append(f"Relationship: {on_str} ({rel_type})")
    return "\n".join(prompt_lines)

def get_schema_hint(con, table_name):
    columns = con.execute(f'DESCRIBE "{table_name}"').fetchdf()
    column_names = ", ".join([f'"{col}"' for col in columns['column_name'].tolist()])
    return f"{table_name}({column_names})"

def clean_generated_sql(sql: str) -> str:
    sql = re.sub(r"date_trunc\('month''", "date_trunc('month'", sql, flags=re.IGNORECASE)
    sql = re.sub(r"date_trunc\('month\"?", "date_trunc('month'", sql, flags=re.IGNORECASE)
    sql = sql.replace("AS DATE DATE", "AS DATE")
    match = re.search(r"date_trunc\('month',\s*TRY_CAST\((.+?) AS DATE\)\)", sql, re.IGNORECASE)
    if match:
        trunc_expr = f"DATE_TRUNC('month', TRY_CAST({match.group(1)} AS DATE))"
        sql = re.sub(r"GROUP BY\s+.+?(ORDER BY|$)", f"GROUP BY {trunc_expr} \\1", sql, flags=re.IGNORECASE | re.DOTALL)
    return sql

def generate_sql_from_question(question, schema_hint, lang):
    if not api_key:
        st.warning("⚠️ Please enter your Groq API key before submitting a query.")
        return ""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    system_instruction = (
        "Generate only a valid SQL query using DuckDB syntax. Do not add any explanation or comments. "
        "Respond only with the SQL code. Use only the provided schema.\n\nSchema:\n" + schema_hint
    )

    messages = [
        {
            "role": "system",
            "content": system_instruction
        },
        {
            "role": "user",
            "content": question
        }
    ]

    data = {"model": "llama3-70b-8192", "messages": messages, "temperature": 0.3}
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def extract_sql_code(response_text):
    match = re.search(r"```sql\s*(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    match = re.search(r"```(.*?)```", response_text, re.DOTALL)
    if match: return match.group(1).strip()
    return response_text.strip()

def analyze_result_with_llm(question, result_df, lang):
    if not api_key:
        st.warning("⚠️ Please enter your Groq API key before submitting a query.")
        return ""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        result_markdown = result_df.to_markdown(index=False)
    except ImportError:
        result_markdown = result_df.to_csv(index=False)

    messages = [
        {
            "role": "system",
            "content": "നിങ്ങൾ ഒരു ഡാറ്റാ വിശകലന വിദഗ്ദ്ധനാണ്. വിശദീകരണം മലയാളത്തിൽ തരും." if lang == "Malayalam"
            else "You are a data analyst. Explain clearly and concisely in English."
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nResult Table:\n{result_markdown}\n\nExplain the result."
        }
    ]
    data = {"model": "llama3-70b-8192", "messages": messages, "temperature": 0.5}
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# ------------------ MAIN ------------------
if uploaded_files:
    if len(uploaded_files) == 1 and not description_file:
        con, table_name, df = load_single_file(uploaded_files[0])
        schema_hint = get_schema_hint(con, table_name)
    elif len(uploaded_files) > 1 and description_file:
        con, table_names = load_multiple_tables(uploaded_files)
        description_json = parse_description_file(description_file)
        schema_hint = build_schema_prompt(description_json)
    else:
        st.warning("Please upload a YAML/JSON description file when using more than one data file.")
        st.stop()

    user_question = st.text_input("❓ Ask your question")
    if user_question:
        actual_lang = detect_language(user_question)
        try:
            sql_raw = generate_sql_from_question(user_question, schema_hint, actual_lang)
            sql_query = clean_generated_sql(extract_sql_code(sql_raw))
            if not sql_query:
                st.stop()

            result_df = con.execute(sql_query).fetchdf()
            st.dataframe(result_df)

            if not result_df.empty:
                st.subheader("📈 Chart")
                try:
                    num_cols = result_df.select_dtypes(include=["int", "float"]).columns.tolist()
                    if len(result_df.columns) >= 2 and num_cols:
                        st.bar_chart(result_df, x=result_df.columns[0], y=num_cols[0])
                except Exception as e:
                    st.info(f"Chart not shown: {e}")

                if show_analysis:
                    st.subheader("💡 Insight")
                    try:
                        insight = analyze_result_with_llm(user_question, result_df, actual_lang)
                        st.markdown(insight)
                    except Exception as e:
                        st.error(f"Insight generation failed: {e}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
