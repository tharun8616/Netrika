# Netrika
What This Tool Does

# Upload Data

You can upload 1–3 CSV or Excel files.

Optionally, you can also upload a description file in YAML or JSON format.

This description explains how the files are related (like foreign keys / relationships between tables).

Ask Questions in English (or Malayalam)

Instead of writing SQL queries manually, you just type your question naturally.

# Example: “Show me the total sales by region in 2024” or “2024-ലെ റീജിയൻ അടിസ്ഥാനത്തിലുള്ള സെയിൽസ് കാണിക്കൂ”.

# How It Works (Behind the Scenes)

The app uses Groq LLM (a language model optimized for speed & efficiency) to:

Understand your natural-language question.

Convert it into an SQL query automatically.

It then runs this SQL query using DuckDB (a super-fast in-memory database, perfect for analytics on local files).

# Outputs You Get

A results table (the raw answer to your query).

A simple bar chart (whenever the data suits visualization).



# Technology Stack

Groq LLM → For natural language understanding & SQL generation.

DuckDB → For running the SQL queries quickly on uploaded data.

YAML/JSON schema → To define relationships between different data files (if needed).

Visualization → Basic bar charts to show insights graphically.

An AI-generated explanation of the results, available in English or Malayalam.
