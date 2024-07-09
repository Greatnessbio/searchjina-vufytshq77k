import streamlit as st
import requests
import json
import time
import os
import base64

try:
    from exa_py import Exa
    exa_available = True
except ImportError:
    exa_available = False
    st.warning("Exa package is not installed. Exa search functionality will be disabled.")

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
            response = requests.get(url, headers=headers)
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

def process_with_openrouter(prompt, search_results, openrouter_api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json"
    }
    
    full_prompt = f"""Search results:
{json.dumps(search_results, indent=2)}

Task: {prompt}

Provide a response based on the search results and the given task."""

    payload = {
        "model": "anthropic/claude-3-sonnet-20240229",
        "messages": [
            {"role": "system", "content": "You are an AI assistant tasked with processing and analyzing information from search results."},
            {"role": "user", "content": full_prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.RequestException as e:
        st.error(f"OpenRouter API request failed: {e}")
    return None

def generate_report(company_info, jina_results, exa_results, openrouter_api_key):
    report_prompt = """
    Create a comprehensive report on the company based on the provided information. 
    The report should include the following sections:
    1. Executive Summary
    2. Company Overview
    3. Products and Services
    4. Market Analysis
    5. Competitive Landscape
    6. SWOT Analysis
    7. Future Outlook and Recommendations

    Be concise yet informative. Use bullet points where appropriate.
    """
    
    combined_info = f"""
    Company Info:
    {json.dumps(company_info, indent=2)}

    Jina Search Results:
    {json.dumps(jina_results, indent=2)}

    Exa Search Results:
    {json.dumps([result.__dict__ for result in exa_results], indent=2) if exa_results else "Not available"}
    """

    return process_with_openrouter(report_prompt, combined_info, openrouter_api_key)

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
    if 'final_report' not in st.session_state:
        st.session_state.final_report = None

    company_url = st.text_input("Enter the company's URL:")

    if st.button("Analyze Company") and company_url:
        with st.spinner("Analyzing..."):
            # Jina Search
            jina_results = get_jina_search_results(company_url, api_keys["jina"])
            st.session_state.jina_results = jina_results

            # Exa Search
            if exa_available and api_keys["exa"]:
                exa_results = get_exa_search_results(company_url, api_keys["exa"])
                st.session_state.exa_results = exa_results
            else:
                st.session_state.exa_results = None
                st.warning("Exa search is not available. Analysis will be based only on Jina results.")

            # Process Jina and Exa results
            combined_results = {
                "jina": jina_results,
                "exa": [result.__dict__ for result in st.session_state.exa_results] if st.session_state.exa_results else None
            }
            
            company_info_prompt = "Extract key information about the company, including its name, description, products/services, and any other relevant details."
            company_info = process_with_openrouter(company_info_prompt, combined_results, api_keys["openrouter"])
            st.session_state.company_info = company_info

            # Generate final report
            final_report = generate_report(company_info, jina_results, st.session_state.exa_results, api_keys["openrouter"])
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
