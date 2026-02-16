import boto3
import json
import awswrangler as wr
import pandas as pd

# AWS Config
bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')
DATABASE = "food_security_db"

def get_athena_schema():
    """
    Provides the schema context for the LLM to generate accurate SQL.
    """
    return """
    You are a Data Analyst for the UN. You have access to an AWS Athena Database.
    
    Table: v_agent
    
    Columns & Definitions:
    -- Identifiers --
    - iso3 (string): 3-letter Country Code (e.g., 'USA', 'IND')
    - area (string): Country Name
    - year (int): 2015 to 2024
    
    -- Risk & Climate --
    - composite_risk_score (float): 0-100 Index (Higher is Worse/Risky)
    - heat_stress_days (int): Count of days > 35°C
    - max_dry_streak_days (int): Longest consecutive run of days with <1mm rain
    - total_precip_mm (float): Total annual rainfall
    - planting_start_doy (int): Day of Year when planting season starts
    
    -- Nutrition & Supply --
    - kcal_cap_total_day (float): Daily calories available per person
    - production_per_capita (float): Domestic food production per person
    - total_production (float): Total crop output in tonnes
    
    -- Economics & Trade --
    - food_inflation_index (float): CPI for Food (Base 2015=100)
    - gdp_per_capita (float): Gross Domestic Product per person (USD)
    - economic_power_score (float): Normalized economic strength
    - import_tonnes (float): Total food imports
    - export_tonnes (float): Total food exports
    - net_trade_balance (float): Exports minus Imports
    - import_dependency_ratio (float): Percentage of food supply imported
    
    -- Structural --
    - total_agri_land_ha (float): Total agricultural land in hectares
    - fertilizer_per_ha (float): Nitrogen input intensity
    - val_added_agri_share_gdp (float): % of GDP coming from Agriculture
    
    -- FAO Framework Scores (0-100, Higher is Better) --
    - score_availability: Supply sufficiency
    - score_access: Economic capacity to buy food
    - score_utilization: Health/Water infrastructure
    - score_stability: Resilience to shocks
    - score_agency: Political voice and equality
    
    -- Demographics --
    - total_population (float): Total people
    - population_density (float): People per sq km
    - median_age (float): Average age of population
    - population_growth_rate (float): Annual % growth
    - sex_ratio (float): Males per 100 Females
    
    Rules:
    1. Always use table 'v_agent'.
    2. Ignore nulls using 'WHERE column IS NOT NULL' when doing calculations.
    3. If asked for 'Riskiest', order by composite_risk_score DESC.
    4. If asked for 'Resilient', order by score_stability DESC.
    5. Return ONLY the valid Presto/Athena SQL query. Do not use Markdown blocks.
    """

def generate_sql(question):
    """
    Step 1: Ask LLM to write SQL
    """
    schema = get_athena_schema()
    prompt = f"""
    {schema}
    
    User Question: "{question}"
    
    Write a valid Presto/Athena SQL query to answer this. 
    Limit results to 10 unless specified.
    """
    
    # Payload for Claude 3
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}]
    })

    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-haiku-20240307-v1:0', # Or Sonnet
        body=body
    )
    
    response_body = json.loads(response.get('body').read())
    sql_query = response_body['content'][0]['text'].strip()
    
    # Cleanup markdown if the LLM adds it
    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
    return sql_query

def explain_results(question, df):
    """
    Step 3: Ask LLM to summarize the data frame in English
    """
    data_summary = df.to_csv(index=False)
    
    prompt = f"""
    User Question: "{question}"
    Data Retrieved:
    {data_summary}
    
    Summarize this data in 2 concise sentences. Highlight the key outlier.
    """
    
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    })

    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-haiku-20240307-v1:0',
        body=body
    )
    
    return json.loads(response.get('body').read())['content'][0]['text']

def ask_data_agent(question):
    """
    Orchestrator
    """
    try:
        # 1. Generate SQL
        sql = generate_sql(question)
        
        # 2. Run SQL
        df = wr.athena.read_sql_query(sql, database=DATABASE)
        
        if df.empty:
            return sql, df, "No data found for that query."
            
        # 3. Explain
        summary = explain_results(question, df)
        
        return sql, df, summary
        
    except Exception as e:
        return None, None, f"Error: {str(e)}"