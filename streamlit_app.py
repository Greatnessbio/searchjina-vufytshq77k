import streamlit as st
import requests
import json
import time
import os
import base64
from urllib.parse import urlparse

try:
    from exa_py import Exa
    exa_available = True
except ImportError:
    exa_available = False
    st.warning("Exa package is not installed. Exa search functionality will be disabled.")

# Timeout for API calls (in seconds)
API_TIMEOUT = 30

def load_api_keys():
    try:
        return {
            "jina": st.secrets["secrets"]["jina_api_key"],
            "openrouter": st.secrets["secrets"]["openrouter_api_key"],
            "exa": st.secrets["secrets"]["exa_api_key"] if exa_available else None,
            "rapidapi": st.secrets["secrets"]["rapidapi_key"]
        }
    except KeyError as e:
        st.error(f"{str(e)} API key not found in secrets.toml. Please add it.")
        return None

def load_users():
    return st.secrets["users"]

def login(username, password):
    users = load_users()
    if username in users and users[username] == password:
        return True
    return False

@st.cache_data(ttl=3600)
def get_jina_search_results(query, jina_api_key, max_retries=3, delay=5):
    url = f"https://s.jina.ai/{requests.utils.quote(query)}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {jina_api_key}",
        "X-With-Generated-Alt": "true",
        "X-With-Images-Summary": "true",
        "X-With-Links-Summary": "true"
    }
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=API_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                st.error(f"Jina AI search request failed after {max_retries} attempts: {e}")
    return None

@st.cache_data(ttl=3600)
def get_exa_search_results(url, exa_api_key):
    if not exa_available:
        st.warning("Exa search is not available.")
        return None
    exa = Exa(api_key=exa_api_key)
    try:
        search_response = exa.find_similar_and_contents(
            url,
            highlights={"num_sentences": 2},
            num_results=10
        )
        return search_response.results
    except Exception as e:
        st.error(f"Exa search request failed: {e}")
        return None

def get_linkedin_company_data(linkedin_url, rapidapi_key):
    url = "https://linkedin-company-data.p.rapidapi.com/linkedinCompanyDataV2"
    querystring = {"vanityName": linkedin_url.split("/company/")[1].strip("/")}
    headers = {
        "X-RapidAPI-Key": rapidapi_key,
        "X-RapidAPI-Host": "linkedin-company-data.p.rapidapi.com"
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"LinkedIn company data request failed: {e}")
    return None

def process_with_openrouter(prompt, context, openrouter_api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json"
    }
    
    full_prompt = f"""Context:
{json.dumps(context, indent=2)}

Task: {prompt}

Provide a response based on the given context and task."""

    payload = {
        "model": "anthropic/claude-3-sonnet-20240229",
        "messages": [
            {"role": "system", "content": "You are an AI assistant tasked with analyzing company information and providing insights."},
            {"role": "user", "content": full_prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.RequestException as e:
        st.error(f"OpenRouter API request failed: {e}")
    return None

def generate_company_info(jina_results, exa_results, linkedin_data, openrouter_api_key):
    company_info_prompt = """
    Extract and summarize key information about the company, including:
    1. Company name
    2. Description
    3. Products/services
    4. Industry
    5. Company size (if available)
    6. Founded year (if available)
    7. Headquarters location
    8. Key executives (if available)
    
    Provide this information in a structured format.
    """
    
    context = {
        "jina_results": jina_results,
        "exa_results": [result.__dict__ for result in exa_results] if exa_results else None,
        "linkedin_data": linkedin_data
    }
    
    return process_with_openrouter(company_info_prompt, context, openrouter_api_key)

def generate_competitor_analysis(jina_results, exa_results, openrouter_api_key):
    competitor_analysis_prompt = """
    Based on the search results, identify and analyze the main competitors of the company. For each competitor, provide:
    1. Competitor name
    2. Brief description
    3. Key products/services
    4. Strengths and weaknesses compared to the main company
    
    Summarize the competitive landscape and the company's position within it.
    """
    
    context = {
        "jina_results": jina_results,
        "exa_results": [result.__dict__ for result in exa_results] if exa_results else None
    }
    
    return process_with_openrouter(competitor_analysis_prompt, context, openrouter_api_key)

def generate_final_report(company_info, competitor_analysis, jina_results, exa_results, linkedin_data, openrouter_api_key):
    report_prompt = """
    Create a comprehensive report on the company based on the provided information. 
    The report should include the following sections:
    1. Executive Summary
    2. Company Overview (use the company_info and linkedin_data)
    3. Products and Services
    4. Market Analysis
    5. Competitive Landscape (use the competitor_analysis)
    6. SWOT Analysis
    7. Future Outlook and Recommendations

    Be concise yet informative. Use bullet points where appropriate.
    """
    
    context = {
        "company_info": company_info,
        "competitor_analysis": competitor_analysis,
        "jina_results": jina_results,
        "exa_results": [result.__dict__ for result in exa_results] if exa_results else None,
        "linkedin_data": linkedin_data
    }

    return process_with_openrouter(report_prompt, context, openrouter_api_key)

def get_download_link(content, filename, text):
    b64 = base64.b64encode(content.encode()).decode()
    return f'<a href="data:file/txt;base64,{b64}" download="{filename}">{text}</a>'

def main_app():
    st.title("Advanced Company Analyst with Jina and Exa Search")

    api_keys = load_api_keys()
    if not api_keys:
        return

    if 'jina_results' not in st.session_state:
        st.session_state.jina_results = None
    if 'exa_results' not in st.session_state:
        st.session_state.exa_results = None
    if 'company_info' not in st.session_state:
        st.session_state.company_info = None
    if 'competitor_analysis' not in st.session_state:
        st.session_state.competitor_analysis = None
    if 'final_report' not in st.session_state:
        st.session_state.final_report = None

    company_url = st.text_input("Enter the company's URL:")
    linkedin_url = st.text_input("Enter the company's LinkedIn URL (format: https://www.linkedin.com/company/company-name):")

    if st.button("Analyze Company") and company_url and linkedin_url:
        with st.spinner("Analyzing..."):
            # Get LinkedIn company data
            linkedin_data = get_linkedin_company_data(linkedin_url, api_keys["rapidapi"])
            
            # Jina Search (using both URLs)
            jina_results = get_jina_search_results(f"{company_url} {linkedin_url}", api_keys["jina"])
            st.session_state.jina_results = jina_results

            # Exa Search (using both URLs)
            if exa_available and api_keys["exa"]:
                exa_results = get_exa_search_results(f"{company_url} {linkedin_url}", api_keys["exa"])
                st.session_state.exa_results = exa_results
            else:
                st.session_state.exa_results = None
                st.warning("Exa search is not available. Analysis will be based only on Jina results.")

            # Generate company info
            company_info = generate_company_info(jina_results, st.session_state.exa_results, linkedin_data, api_keys["openrouter"])
            st.session_state.company_info = company_info

            # Generate competitor analysis
            competitor_analysis = generate_competitor_analysis(jina_results, st.session_state.exa_results, api_keys["openrouter"])
            st.session_state.competitor_analysis = competitor_analysis

            # Generate final report
            final_report = generate_final_report(company_info, competitor_analysis, jina_results, st.session_state.exa_results, linkedin_data, api_keys["openrouter"])
            st.session_state.final_report = final_report

            st.success("Analysis completed!")

    if st.session_state.jina_results or st.session_state.exa_results:
        st.subheader("Analysis Results")
        
        if st.session_state.jina_results:
            with st.expander("Jina Search Results"):
                st.json(st.session_state.jina_results)
        
        if st.session_state.exa_results:
            with st.expander("Exa Search Results"):
                for result in st.session_state.exa_results:
                    st.write(f"Title: {result.title}")
                    st.write(f"URL: {result.url}")
                    st.write(f"Highlights: {result.highlights}")
                    st.write("---")

        if st.session_state.company_info:
            st.subheader("Company Information")
            st.write(st.session_state.company_info)

        if st.session_state.competitor_analysis:
            st.subheader("Competitor Analysis")
            st.write(st.session_state.competitor_analysis)

        if st.session_state.final_report:
            st.subheader("Final Report")
            st.write(st.session_state.final_report)
            
            report_filename = "company_analysis_report.txt"
            download_link = get_download_link(st.session_state.final_report, report_filename, "Download Report")
            st.markdown(download_link, unsafe_allow_html=True)

def login_page():
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if login(username, password):
            st.session_state.logged_in = True
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password")

def display():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_page()
    else:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
        else:
            main_app()

if __name__ == "__main__":
    display()
