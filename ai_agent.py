import boto3
import json
import awswrangler as wr
import pandas as pd

# AWS Config
bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')
DATABASE = "food_security_db"

def get_athena_schema():
    """
    Hardcodes the schema context so the LLM knows what tables exist.
    """
    return """
    You are a Data Analyst for the UN. You have access to an AWS Athena Database.
    
    Table: v_global_food_risk
    Columns:
    - iso3 (string): Country Code (e.g., 'USA', 'IND')
    - area (string): Country Name
    - year (string): 2015 to 2023
    - total_crop_production_tonnes (bigint): Total food produced
    - total_population (double): Population 
    - heat_stress_days (bigint): Days > 35C
    - food_inflation_index (double): CPI for Food (Base 100)
    - production_per_capita (double): Food per person
    - kcal_cap_total_day (double): Daily calories available
    - total_precip_mm (double): Rain for year
    - import_tonnes (double): imports to country in tonnes
    - export_tonnes (double): exports from country in tonnes

    Table: v_holistic_analysis
    - iso3 (string): Country Code (e.g., 'USA', 'IND')
    - area (string): Country Name
    - year (string): 2015 to 2023
    - total_agri_land_ha (float): usable agricutural land
    - val_added_agri_share_gdp (float): value added of agriculture to gdp
    - fertilizer_per_ha (float): Yield Intensity of nutrient nitogen to usable agricultural land
    - net_trade_balance (float): different between exports and imports
    - import_dependency_ratio (float): ratio of imports to production plus imports difference with exports


    
    Rules:
    1. Always use 'v_global_food_risk'.
    2. Use 'v_holistic_analysis' to join with 'v_global_food_risk' to get more data.
    3. Ignore nulls using 'WHERE column IS NOT NULL'.
    4. If asked for 'Riskiest', order by heat_stress_days DESC or food_inflation_index DESC.
    5. Return ONLY the SQL query. Do not use Markdown. Do not explain.
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