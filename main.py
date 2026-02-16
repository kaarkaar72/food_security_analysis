import streamlit as st
import os
from streamlit_option_menu import option_menu
from ai_agent import ask_data_agent
from dotenv import load_dotenv
import awswrangler as wr
import plotly.express as px
import plotly.graph_objects as go
import boto3
import pandas as pd
import requests
import json

# --- 1. APP CONFIGURATION & STYLING ---
st.set_page_config(page_title="Agri-Intel: Global Risk Engine", layout="wide", page_icon="🌍")

# Professional CSS for "Card" Layouts
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        text-align: center;
    }
    .metric-value {font-size: 24px; font-weight: bold; color: #1f77b4;}
    .metric-label {font-size: 14px; color: #666;}
    .risk-high {color: #d62728; font-weight: bold;}
    .risk-low {color: #2ca02c; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

boto3.setup_default_session(region_name="us-east-2")
load_dotenv() 

DATABASE = os.environ.get('DATABASE', 'food_security_db') 
GRAPHQL_URL = os.environ.get('GRAPHQL_URL', '') 
API_KEY = os.environ.get('API_KEY', '') 

@st.cache_data
def fetch_global_snapshot(year):
    """Fetches the global snapshot data for a given year from Athena"""
    query = """
    query GetProfile($year: Int!) {
       getGlobalMapData(year: $year) {
              iso3
              area
              composite_risk_score
              resilience_index
              total_population
              production_per_capita
              heat_stress_days
              food_inflation_index
       }
    }
    """
    headers = {"Content-Type": "application/json","x-api-key": API_KEY}
    try:
       resp = requests.post(GRAPHQL_URL, json={'query': query, 'variables': {'year': year}}, headers=headers)
       return pd.DataFrame(resp.json().get('data', {}).get('getGlobalMapData'))
    except:
       return None

@st.cache_data  
def fetch_all_countries(year):
    """Fetches the global snapshot data for a given year from Athena"""
    query = """
    query GetProfile($year: Int!) {
       getGlobalMapData(year: $year) {
              iso3
              area
       }
    }
    """
    headers = {"Content-Type": "application/json","x-api-key": API_KEY}
    try:
       resp = requests.post(GRAPHQL_URL, json={'query': query, 'variables': {'year': year}}, headers=headers)
       return pd.DataFrame(resp.json().get('data', {}).get('getGlobalMapData', []))
    except:
       return None
    
@st.cache_data(ttl=3600)
def fetch_dossier(iso3):
       """
       Fetches the complete nested profile via GraphQL.
       Requests Risk Z-Scores and Structural Metrics.
       """
       query = """
       query getDossier($iso3: String!) {
              getCountryProfile(iso3: $iso3) {
                     area
                     year
                     risk {
                            composite_score
                            primary_crisis_driver
                            climate_shock_z
                            heat_stress_days
                     }
                     economy {
                            resilience_index
                            economic_shock_z
                            agri_share_gdp
                            inflation_index
                     }
                     supply {
                            production_shock_z
                            fertilizer_per_ha
                            land_area_ha
                            total_production_tonnes
                     }
                     trade {
                            dependency_ratio
                            net_trade_balance
                     }
                     pillars {
                            score_availability
                            score_access
                            score_utilization
                            score_stability
                            score_agency
                     }
                     demographics {
                            total_population
                            population_density
                            median_age
                            sex_ratio
                     }
              }
       }
       """
       headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
       try:
              resp = requests.post(GRAPHQL_URL, json={'query': query, 'variables': {'iso3': iso3}}, headers=headers)
              return resp.json().get('data', {}).get('getCountryProfile')
       except Exception as e:
              st.error(f"API Connection Failed: {e}")
              return None
    


# --- 3. NAVIGATION BAR ---
with st.sidebar:
       st.title("Agri-Intel Dashboard")
       st.caption(f"Connected to: {DATABASE}")
       year_select = st.slider("Monitoring Year", 2015, 2023, 2022)
       selected_page = option_menu(
              menu_title=None,
              options=["Global View", "Country Diagonstics", "FAO Framework", "AI Analyst", "System Architecture"],
              icons=["globe", "file-earmark-text", "cpu","cloud-fill"],
              default_index=0,
       )
       st.markdown("---")  
       # METHODOLOGY LEGEND
       with st.expander("ℹ️ Metric Definitions (Read Me)"):
              st.markdown("""
              ### 🛡️ Composite Risk Score (0-100)
              A unified index of food insecurity.
              - **Formula:** `(Supply_Risk * 0.5) + (Climate_Risk * 0.25) + (Drought_Risk * 0.25)`
              - 🔴 **80-100 (Critical):** Immediate famine risk.
              - 🟠 **50-79 (High):** Structural insecurity.
              - 🟢 **0-49 (Stable):** Food secure.

              ### 🌿 Resilience Index (0-100)
              Can this country buy its way out of a crisis?
              - **Formula:** `(Normalized_GDP + Trade_Openness) - (Climate_Exposure)`
              - 🟢 **High Score:** Wealthy/Connected (e.g., UAE, Singapore).
              - 🔴 **Low Score:** Poor/Isolated (e.g., Afghanistan).

              ### 🔥 Heat Stress Days
              Count of days where max temp exceeded **35°C** (Critical threshold for Maize/Wheat).

              ### 💸 Food Inflation Index
              Consumer Price Index (CPI) for Food.
              - **Base Year:** 2015 = 100.
              - **> 150:** Hyper-inflation territory (50% price hike since 2015).
              """)

countries_list = fetch_all_countries(2023)  
# ==================================================
# PAGE 1: GLOBAL COMMAND CENTER
# ==================================================
if selected_page == "Global View":
       # 1. Header & Context
       st.title(f"🌍 Global Risk Monitor ({year_select})")
       st.markdown("Real-time assessment of food security threats across **supply chains**, **climate**, and **economics**.")

       # Load Data
       df = fetch_global_snapshot(year_select)
       df.fillna(0, inplace=True) # Safety first

       # 2. The "Hero" KPI Section (Grouped for Impact)
       st.markdown("### 🚦 System Status")

       # Define custom CSS for "Pop" effect
       st.markdown("""
       <style>
       .kpi-box {
              background-color: #f8f9fa;
              border-radius: 8px;
              padding: 15px;
              box-shadow: 0 2px 4px rgba(0,0,0,0.1);
              text-align: center;
       }
       .kpi-title { font-size: 14px; color: #6c757d; font-weight: 600; text-transform: uppercase; }
       .kpi-val { font-size: 28px; font-weight: 800; color: #212529; }
       .kpi-sub { font-size: 12px; color: #dc3545; font-weight: bold; } /* Red for danger */
       </style>
       """, unsafe_allow_html=True)

       # Calculate Metrics
       high_risk_count = len(df[df['composite_risk_score'] > 75])
       pop_risk_m = df[df['composite_risk_score'] > 75]['total_population'].sum() / 1e6
       avg_resilience = df['resilience_index'].mean()
       high_inflation_count = len(df[df['food_inflation_index'] > 120])

       # Render KPIs in 4 Columns
       col1, col2, col3, col4 = st.columns(4)

       with col1:
              st.markdown(f"""
              <div class="kpi-box">
              <div class="kpi-title">Critical Countries</div>
              <div class="kpi-val">{high_risk_count}</div>
              <div class="kpi-sub">Risk Score > 75</div>
              </div>""", unsafe_allow_html=True)
              
       with col2:
              st.markdown(f"""
              <div class="kpi-box">
              <div class="kpi-title">Population at Risk</div>
              <div class="kpi-val">{pop_risk_m:,.0f} M</div>
              <div class="kpi-sub">Immediate Vulnerability</div>
              </div>""", unsafe_allow_html=True)

       with col3:
              st.markdown(f"""
              <div class="kpi-box">
              <div class="kpi-title">Global Resilience</div>
              <div class="kpi-val">{avg_resilience:.1f}</div>
              <div style="color: #28a745; font-size: 12px; font-weight: bold;">Index Avg (0-100)</div>
              </div>""", unsafe_allow_html=True)

       with col4:
              st.markdown(f"""
              <div class="kpi-box">
              <div class="kpi-title">Inflation Hotspots</div>
              <div class="kpi-val">{high_inflation_count}</div>
              <div class="kpi-sub">CPI > 120</div>
              </div>""", unsafe_allow_html=True)

       st.markdown("---")

       # 3. The "Hero" Map (Full Width)
       c_map_ctrl, c_map_view = st.columns([1, 4])

       with c_map_ctrl:
              st.markdown("#### 🗺️ Map Controls")
              metric = st.radio(
              "Visualize Metric:", 
              ['composite_risk_score', 'resilience_index', 'heat_stress_days', 'food_inflation_index'],
              format_func=lambda x: x.replace('_', ' ').title()
              )
              st.info("Hover over countries for detailed breakdown.")

       with c_map_view:
              # Dynamic Color Scale
              scale = "RdYlGn" if metric == "resilience_index" else "RdYlGn_r"
              
              fig_map = px.choropleth(
              df, locations="iso3", color=metric,
              hover_name="area", 
              hover_data=['composite_risk_score', 'production_per_capita', 'heat_stress_days'],
              color_continuous_scale=scale,
              title=f"Global Distribution: {metric.replace('_', ' ').title()}",
              height=600
              )
              fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0}, paper_bgcolor="rgba(0,0,0,0)")
              fig_map.update_geos(showframe=False, showcoastlines=True, coastlinecolor="#333333", projection_type="natural earth")
              st.plotly_chart(fig_map, use_container_width=True)

       # 4. The "Deep Dive" Section (Two Columns)
       st.markdown("### 📉 Risk Analysis & Watchlist")

       col_bubble, col_list = st.columns([2, 1])

       with col_bubble:
              st.markdown("**The Quadrant of Vulnerability**")
              st.caption("Identify countries with **Low Supply** (Left) and **High Heat** (Top).")
              
              fig_bubble = px.scatter(
              df, 
              x="production_per_capita", 
              y="heat_stress_days",
              size="total_population", 
              color="composite_risk_score",
              hover_name="area",
              log_x=True, 
              size_max=60,
              color_continuous_scale="RdYlGn_r",
              labels={"production_per_capita": "Food Supply (kg/person)", "heat_stress_days": "Heat Stress Days (>35°C)"}
              )
              # Add "Danger Zone" annotation
              fig_bubble.add_shape(type="rect",
              x0=0.01, y0=30, x1=1.0, y1=100,
              line=dict(color="Red", width=2, dash="dot"),
              fillcolor="Red", opacity=0.1
              )
              fig_bubble.add_annotation(x=0.1, y=90, text="CRITICAL ZONE", showarrow=False, font=dict(color="red", size=14))
              
              st.plotly_chart(fig_bubble, use_container_width=True)

       with col_list:
              st.markdown("**🚨 Top 10 Critical Watchlist**")
              worst = df.sort_values(metric, ascending=False if metric != 'resilience_index' else True).head(10)
              
              st.dataframe(
              worst[['area', metric]], 
              column_config={
                     "area": "Country",
                     metric: st.column_config.ProgressColumn(
                     "Score", 
                     format="%.1f", 
                     min_value=0, 
                     max_value=100 if metric != 'food_inflation_index' else 200
                     )
              },
              hide_index=True, 
              height=400
              )
       st.header("📂 Country Intelligence Dossier")
       sel_country = st.selectbox("Select Target Country", countries_list['area'].unique(), index=0)
       target_iso = countries_list[countries_list['area'] == sel_country]['iso3'].iloc[0]

       c1, c2 = st.columns([1, 1])
       row_sql = df[df['iso3'] == target_iso].iloc[0]
       with c1:
              # Normalize metrics for Radar (0-100 scale)
              # We handle NaN safely
              r_vals = [
              row_sql['composite_risk_score'] if pd.notnull(row_sql['composite_risk_score']) else 0,
              (100 - row_sql['resilience_index']) if pd.notnull(row_sql['resilience_index']) else 0, # Invert so outer = bad
              min(row_sql['heat_stress_days'], 100) if pd.notnull(row_sql['heat_stress_days']) else 0,
              min(row_sql['food_inflation_index'] - 100, 100) if pd.notnull(row_sql['food_inflation_index']) else 0,
              ]
              
              fig_radar = go.Figure(data=go.Scatterpolar(
              r=r_vals,
              theta=['Composite Risk', 'Lack of Resilience', 'Heat Stress', 'Inflation Excess'],
              fill='toself',
              name=sel_country
              ))
              fig_radar.update_layout(
              polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
              title=f"Vulnerability Profile: {sel_country}"
              )
              st.plotly_chart(fig_radar, use_container_width=True)
              
       with c2:
              st.subheader("Situation Report")
              # Mocking the AI generation for speed/cost
              st.markdown(f"""
              **Subject:** {sel_country} Security Assessment ({year_select})
              
              *   **Risk Status:** The calculated risk score is **{row_sql['composite_risk_score']:.1f}**.
              *   **Climate Exposure:** Recorded **{row_sql['heat_stress_days']}** days of extreme thermal stress, impacting crop yields.
              *   **Economic Buffer:** Resilience index is **{row_sql['resilience_index']:.1f}**, suggesting {'strong' if row_sql['resilience_index'] > 50 else 'weak'} capacity to import food substitutes.
              
              **Recommendation:** {'Prioritize irrigation infrastructure.' if row_sql['heat_stress_days'] > 30 else 'Monitor inflation metrics.'}
              """)
       

elif selected_page == "Country Diagonstics":
       st.header("🔍 Advanced Diagnostic Engine")
       st.caption("Powered by GraphQL: Fetching Risk, Economic, and Structural objects in one call.")

       # 1. Selector
       # We use the global 'df' (loaded via SQL for the map) just to get the list of countries
       target_country = st.selectbox("Select Target Country", countries_list['area'].unique(), index=0)
       target_iso = countries_list[countries_list['area'] == target_country]['iso3'].iloc[0]

       # 2. Fetch Data (Single API Call)
       with st.spinner(f"Retrieving Intelligence Dossier for {target_country}..."):
              dossier = fetch_dossier(target_iso)
       
       if dossier:
              # --- SECTION A: THE CRISIS DRIVER ---
              latest = pd.DataFrame(dossier[1])
              st.subheader("1️⃣ Primary Crisis Driver")
              
              driver = latest['risk']['primary_crisis_driver']
              
              if driver == "Climate Anomaly":
                     st.error(f"🔥 **CLIMATE SHOCK DETECTED**")
                     st.markdown  ("Heat/Drought stress is > 2 Standard Deviations above historical norm.")
              elif driver == "Hyper-Inflation Event":
                     st.error(f"💸 **ECONOMIC SHOCK DETECTED**")
                     st.markdown("Food prices are spiking significantly faster than the 5-year trend.")
              elif driver == "Supply Collapse":
                     st.error(f"📉 **SUPPLY COLLAPSE**")
                     st.markdown("Domestic production has dropped significantly below the baseline.")
              else:
                     st.success(f"⚖️ **Status: {driver}**")
                     st.markdown("No acute acute shocks detected. Issues may be chronic/structural.")

              st.divider()

              # --- SECTION B: Z-SCORE DECOMPOSITION ---
              st.subheader("2️⃣ Shock Decomposition (Anomaly Detection)")
              
              c1, c2 = st.columns([2, 1])
              
              with c1:
                     # Helper to handle None values from API
                     def get_z(val): return val if val is not None else 0.0
                     
                     # Helper to clip outliers for visualization
                     def clip_z(val): return max(min(val, 4), -4)

                     # Build DataFrame from Nested JSON
                     shock_data = pd.DataFrame({
                            'Factor': ['Climate (Heat)', 'Economic (Price)', 'Supply (Yield)'],
                            'Severity (Sigma)': [
                            clip_z(get_z(latest['risk']['climate_shock_z'])), 
                            clip_z(get_z(latest['economy']['economic_shock_z'])), 
                            clip_z(get_z(latest['supply']['production_shock_z']))
                            ],
                            'Raw Value': [
                            get_z(latest['risk']['climate_shock_z']), 
                            get_z(latest['economy']['economic_shock_z']), 
                            get_z(latest['supply']['production_shock_z'])
                            ]
                     })

                     # Plot
                     fig_z = px.bar(
                            shock_data, 
                            x="Severity (Sigma)", 
                            y="Factor", 
                            orientation='h',
                            color="Severity (Sigma)",
                            color_continuous_scale="RdBu_r", # Red = Bad (High Positive Z)
                            range_color=[-3, 3],
                            text="Raw Value",
                            title=f"Deviation from 5-Year Baseline ({latest['year']})"
                     )
                     
                     # Add Threshold Lines
                     fig_z.add_vline(x=2, line_dash="dash", line_color="red", annotation_text="CRITICAL (2σ)")
                     fig_z.add_vline(x=0, line_color="black")
                     fig_z.update_traces(texttemplate='%{text:.2f}', textposition='outside')
                     
                     st.plotly_chart(fig_z, use_container_width=True)

              with c2:
                     st.info("""
                     **How to read this chart:**
                     - **0:** Normal year.
                     - **+2.0:** Extreme Event (Top 5% worst years).
                     - **Red Bars:** Factors making the crisis *worse*.
                     - **Blue Bars:** Factors that are stable or improving.
                     """)

                     st.divider()

                     # --- SECTION C: STRUCTURAL HEALTH ---
                     st.subheader("3️⃣ Structural Health Check")
                     st.write("Is the infrastructure supporting resilience?")

                     m1, m2, m3 = st.columns(3)

                     # 1. Input Intensity
                     with m1:
                            fert = latest['supply']['fertilizer_per_ha']
                            val = f"{fert:.1f} kg" if fert else "N/A"
                            st.metric("Fertilizer / Hectare", val)
                            if fert and fert < 15:
                                   st.caption("⚠️ Low Input (Yield Gap Risk)")
                            else:
                                   st.caption("✅ Inputs Stable")

                     # 2. Trade Position
                     with m2:
                            dep = latest['trade']['dependency_ratio']
                            val = f"{dep*100:.1f}%" if dep is not None else "N/A"
                            st.metric("Import Dependency", val)
                            if dep and dep > 0.5:
                                   st.caption("⚠️ Highly Vulnerable to Trade Wars")
                            else:
                                   st.caption("✅ Food Sovereign / Exporter")

                     # 3. Economic Structure
                     with m3:
                            share = latest['economy']['agri_share_gdp']
                            val = f"{share:.1f}%" if share else "N/A"
                            st.metric("Agri share of GDP", val)
                            if share and share > 25:
                                   st.caption("⚠️ Economy relies heavily on rain")
                            else:
                                   st.caption("✅ Diversified Economy")

       else:
              st.warning("Data unavailable for this country in the selected year.")


       st.markdown("---")
       st.subheader("👥 Demographics: Labor & Land Pressure")
       # hist_df = pd.json_normalize(dossier)
       latest = pd.DataFrame(dossier[1])
       demo = latest['demographics']
       c1, c2, c3 = st.columns(3)

       # 1. MEDIAN AGE (Labor Force Indicator)
       with c1:
              age = demo['median_age']
              st.metric("Median Age", f"{age:.1f} years")
              
              if age < 20:
                     st.info("👶 **Youth Bulge:** Rapidly growing caloric demand. Risk of instability if jobs aren't created.")
              elif age > 40:
                     st.warning("👴 **Aging Workforce:** Labor shortage in agriculture likely. Mechanization required.")
              else:
                     st.success("✅ **Prime Workforce:** Optimal labor availability.")

       # 2. POPULATION DENSITY (Land Pressure Indicator)
       with c2:
              dens = demo['population_density']
              st.metric("Pop Density", f"{dens:.0f} / km²")
              
              if dens > 500:
                     st.warning("🏙️ **High Density:** Cannot rely on land expansion. Must rely on High-Yield Tech or Imports.")
              elif dens < 50:
                     st.success("🚜 **Low Density:** Potential for agricultural land expansion.")

       # 3. MALTHUSIAN INDEX (Calculated)
       # Simple heuristic: Density / Median Age
       # High Density + Young Pop = Extreme Pressure
       with c3:
              if age and dens:
                     pressure_score = dens / age
                     st.metric("Resource Pressure Index", f"{pressure_score:.1f}")
              if pressure_score > 20:
                     st.error("🚨 **Critical Strain:** Young population crowded into small space.")

       st.divider()
        



       # --- SECTION D: TIMELINE OF EVENTS ---
       st.subheader("4️⃣ Timeline of Instability")
       st.write("Correlating shocks over time: Did Heat Stress cause the Production Drop?")

       
       if dossier:
              # hist_df = pd.DataFrame(dossier)
              hist_df = pd.json_normalize(dossier)
              from plotly.subplots import make_subplots 
              # 2. Create Multi-Axis Chart
              fig_timeline = make_subplots(specs=[[{"secondary_y": True}]])
              # Area: Production (Background)
              fig_timeline.add_trace(
                     go.Scatter(
                     x=hist_df['year'], y=hist_df['supply.total_production_tonnes'], 
                     name="Production Output", 
                     fill='tozeroy', 
                     line=dict(color='lightgrey', width=0),
                     marker=dict(opacity=0)
                     ),
                     secondary_y=False
              )
              
              # Line: Heat Stress (Risk 1)
              fig_timeline.add_trace(
                     go.Scatter(
                     x=hist_df['year'], y=hist_df['risk.heat_stress_days'], 
                     name="Heat Stress Days", 
                     mode='lines+markers',
                     line=dict(color='#d62728', width=3) # Red
                     ),
                     secondary_y=True
              )
              
              # Line: Inflation (Risk 2)
              fig_timeline.add_trace(
                     go.Scatter(
                     x=hist_df['year'], y=hist_df['economy.inflation_index'], 
                     name="Food Price Index", 
                     mode='lines',
                     line=dict(color='#ff7f0e', width=2, dash='dot') # Orange
                     ),
                     secondary_y=True
              )
              
              # Layout
              fig_timeline.update_layout(
                     title=f"The Crisis History of {target_country}",
                     hovermode="x unified",
                     legend=dict(orientation="h", y=1.1)
              )
              fig_timeline.update_yaxes(title_text="Production (Tonnes)", secondary_y=False, showgrid=False)
              fig_timeline.update_yaxes(title_text="Stress Metrics (Days / Index)", secondary_y=True, showgrid=True)
              
              st.plotly_chart(fig_timeline, use_container_width=True)
              
              # 3. Automated Event Detection (Resume Flex)
              # Find the worst year
              worst_year = hist_df.loc[hist_df['risk.composite_score'].idxmax()]
              st.info(f"📅 **Critical Event Detected in {int(worst_year['year'])}:** Composite Risk peaked at **{worst_year['risk.composite_score']:.1f}**. Heat Stress was {worst_year['risk.heat_stress_days']} days.")
              
       else:
              st.warning("Historical data unavailable via API.")

elif selected_page == "FAO Framework":
       st.header("📊 FAO Framework Explorer")
       st.caption("Visualizing the 5 Pillars of Food Security: Availability, Access, Utilization, Stability, and Agency.")
       
       # Placeholder content for now
       st.markdown("""
       This section will break down the complex FAO Food Security Framework into interactive visualizations.
       - **Availability:** Domestic production, imports, stock levels.
       - **Access:** Economic and physical access to food (poverty rates, market access).
       - **Utilization:** Nutritional quality, food safety, dietary diversity.
       - **Stability:** Variability of supply and access over time (shocks).
       - **Agency:** Empowerment and decision-making capacity of individuals/communities.
       
       Each pillar will have its own set of KPIs and charts to diagnose specific vulnerabilities. Stay tuned for the full rollout in the next iteration!
       """)
       target_country = st.selectbox("Select Target Country", countries_list['area'].unique(), index=0)
       target_iso = countries_list[countries_list['area'] == target_country]['iso3'].iloc[0]

       # 2. Fetch Data (Single API Call)
       with st.spinner(f"Retrieving Intelligence Dossier for {target_country}..."):
              dossier = fetch_dossier(target_iso)
       

       dossier = pd.json_normalize(dossier)
       dossier = dossier[dossier['year'] > 2014]
       latest = dossier.iloc[1]
       # st.write(dossier["pillars.score_access"][0]))
       c1, c2, c3, c4, c5 = st.columns(5)
    
       def render_pillar(col, title, score, icon):
              color = "green" if int(score) > 70 else "orange" if int(score) > 40 else "red"
              col.markdown(f"""
              <div style="padding:10px; border-radius:10px; border:1px solid #ddd; text-align:center;">
              <h1>{icon}</h1>
              <h4>{title}</h4>
              <h2 style="color:{color};">{score}/100</h2>
              </div>
              """, unsafe_allow_html=True)
       
       render_pillar(c1, "Availability", latest['pillars.score_availability'], "🚜")
       render_pillar(c2, "Access", latest['pillars.score_access'], "💰")
       render_pillar(c3, "Utilization", latest['pillars.score_utilization'], "💧")
       render_pillar(c4, "Stability", latest['pillars.score_stability'], "⚖️")
       render_pillar(c5, "Agency", latest['pillars.score_agency'], "🗳️") # New Icon
       st.markdown("###")

       # --- 2. THE DIAGNOSIS ---
       # Logic to find the weakest link
       scores = {
              "Availability (Supply Chain)": latest['pillars.score_availability'],
              "Access (Economics)": latest['pillars.score_access'],
              "Utilization (Health/Water)": latest['pillars.score_utilization'],
              "Stability (Climate/Conflict)": latest['pillars.score_stability'],
              "Agency (Governance)": latest['pillars.score_agency']
       }
       weakest_link = min(scores, key=scores.get)

       st.error(f"🚨 **Critical Failure Point:** {weakest_link}")

       if "Availability" in weakest_link:
              st.write("👉 This country cannot produce or import enough food. Focus on **Yields & Trade Deals**.")
       elif "Access" in weakest_link:
              st.write("👉 Food exists, but people cannot afford it. Focus on **Inflation Control & Infrastructure**.")
       elif "Utilization" in weakest_link:
              st.write("👉 People are eating, but getting sick or stunted. Focus on **Clean Water & Sanitation**.")
       elif "Stability" in weakest_link:
              st.write("👉 The system collapses periodically due to shocks. Focus on **Climate Adaptation & Peace**.")
       elif "Agency" in weakest_link:
              st.write("👉 People lack the power to change their situation. Focus on **Governance & Social Safety Nets**.")

       fig_trend = px.line(dossier, x='year', y=['pillars.score_stability', 'pillars.score_access','pillars.score_agency','pillars.score_utilization','pillars.score_availability'], title="Stability vs Access vs Agency over Time")
       st.plotly_chart(fig_trend, use_container_width=True)
       


elif selected_page == 'AI Analyst':
       st.header("🤖 Agri-Intel AI Assistant")   
       st.caption("Powered by AWS Bedrock (Claude 3) & Athena")
       if "messages" not in st.session_state:
              st.session_state.messages = []

       for message in st.session_state.messages:
              with st.chat_message(message["role"]):
                     st.markdown(message["content"])
              if "dataframe" in message:
                     st.dataframe(message["dataframe"])
              if "sql" in message:
                     with st.expander("View Generated SQL"):
                            st.code(message["sql"], language="sql")
       if prompt := st.chat_input("Ask about global food security..."):
              # 1. Show User Message
              st.session_state.messages.append({"role": "user", "content": prompt})
              with st.chat_message("user"):
                     st.markdown(prompt)

       # 2. Generate Response
       with st.chat_message("assistant"):
              with st.spinner("Thinking in SQL..."):
                     sql, df, summary = ask_data_agent(prompt)

                     if df is not None:
                            st.markdown(summary)
                            st.dataframe(df)
                            with st.expander("View Generated SQL"):
                                   st.code(sql, language="sql")
                    
                            # Save to history
                            st.session_state.messages.append({
                                   "role": "assistant", 
                                   "content": summary,
                                   "dataframe": df,
                                   "sql": sql
                            })
                     else:
                            st.error(summary)
elif selected_page == "System Architecture":
       st.header("☁️ Cloud Architecture")
       st.write("This platform is built on a Serverless Event-Driven Architecture.")

       # You can replace this with an actual image of your diagram later
       st.graphviz_chart("""
       digraph G {
              rankdir=LR;
              node [shape=box, style=filled, fillcolor=lightblue];
              
              subgraph cluster_ingest {
              label = "Ingestion Layer";
              style=dashed;
              WPP [label="UN WPP API"];
              FAO [label="FAOSTAT API"];
              NASA [label="NASA POWER API"];
              WB [label="World Bank API"];
              Lambda1 [label="Lambda Workers", fillcolor=orange];
              SQS [label="SQS Queue"];
              }
              
              subgraph cluster_storage {
              label = "Data Lake";
              S3 [label="S3 (Parquet)", shape=cylinder, fillcolor=lightgrey];
              Glue [label="AWS Glue Crawler"];
              }
              
              subgraph cluster_serve {
              label = "Serving Layer";
              Athena [label="AWS Athena"];
              AppSync [label="AWS AppSync (GraphQL)", fillcolor=pink];
              }
              
              FAO -> Lambda1;
              NASA -> Lambda1;
              WB -> Lambda1;
              Lambda1 -> S3;
              S3 -> Glue;
              Glue -> Athena;
              Athena -> AppSync;
              Athena -> Streamlit;
              AppSync -> Streamlit;
       }
       """)

       st.markdown("""
       **Tech Stack:**
       - **Compute:** AWS Lambda (Python 3.9) + SQS for buffering.
       - **Storage:** S3 (Partitioned Parquet: `domain/year/country`).
       - **Catalog:** AWS Glue Data Catalog.
       - **Query Engine:** AWS Athena (SQL).
       - **API:** AWS AppSync (GraphQL) for country profiles.
       - **Frontend:** Streamlit + Plotly.
       """)

       

