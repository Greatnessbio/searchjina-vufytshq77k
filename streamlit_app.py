import streamlit as st
import requests
import json
import time
from streamlit.logger import get_logger

try:
    from exa_py import Exa
    exa_available = True
except ImportError:
    exa_available = False
    st.warning("Exa package is not installed. Exa search functionality will be disabled.")

LOGGER = get_logger(__name__)

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
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                LOGGER.error(f"Jina AI search request failed after {max_retries} attempts: {e}")
    return None

@st.cache_data(ttl=3600)
def get_exa_search_results(url, exa_api_key):
    if not exa_available:
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
        LOGGER.error(f"Exa search request failed: {e}")
    return None

def get_linkedin_company_data(company_url, rapidapi_key):
    url = "https://linkedin-data-scraper.p.rapidapi.com/company_pro"
    payload = {"link": company_url}
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "linkedin-data-scraper.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        LOGGER.error(f"LinkedIn company data request failed: {e}")
    return None

def get_linkedin_company_posts(company_url, rapidapi_key):
    url = "https://linkedin-data-scraper.p.rapidapi.com/company_updates"
    payload = {
        "company_url": company_url,
        "posts": 30,
        "comments": 10,
        "reposts": 10
    }
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "linkedin-data-scraper.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        LOGGER.error(f"LinkedIn company posts request failed: {e}")
    return None

def process_with_openrouter(prompt, context, openrouter_api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "anthropic/claude-3-sonnet-20240229",
        "messages": [
            {"role": "system", "content": "You are an AI assistant tasked with analyzing company information."},
            {"role": "user", "content": f"Context:\n{json.dumps(context, indent=2)}\n\nTask: {prompt}"}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.RequestException as e:
        LOGGER.error(f"OpenRouter API request failed: {e}")
    return None

def generate_report(company_info, jina_results, exa_results, linkedin_data, linkedin_posts, openrouter_api_key):
    report_prompt = """
    Create a comprehensive report on the company based on the provided information. 
    The report should include the following sections:
    1. Executive Summary
    2. Company Overview
    3. Products and Services
    4. Market Analysis
    5. Competitive Landscape
    6. LinkedIn Presence and Activity
    7. SWOT Analysis
    8. Future Outlook and Recommendations

    Be concise yet informative. Use bullet points where appropriate.
    """
    
    context = {
        "company_info": company_info,
        "jina_results": jina_results,
        "exa_results": [result.__dict__ for result in exa_results] if exa_results else "Not available",
        "linkedin_data": linkedin_data,
        "linkedin_posts": linkedin_posts
    }

    return process_with_openrouter(report_prompt, context, openrouter_api_key)

def get_download_link(content, filename, text):
    b64 = base64.b64encode(content.encode()).decode()
    return f'<a href="data:file/txt;base64,{b64}" download="{filename}">{text}</a>'

def main_app():
    st.title("Advanced Company Analyst with Jina, Exa, and LinkedIn Data")

    api_keys = load_api_keys()
    if not api_keys:
        return

    company_url = st.text_input("Enter the company's website URL:")
    linkedin_url = st.text_input("Enter the company's LinkedIn URL:")

    if st.button("Analyze Company") and company_url and linkedin_url:
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

            # LinkedIn Data
            linkedin_data = get_linkedin_company_data(linkedin_url, api_keys["rapidapi"])
            st.session_state.linkedin_data = linkedin_data

            # LinkedIn Posts
            linkedin_posts = get_linkedin_company_posts(linkedin_url, api_keys["rapidapi"])
            st.session_state.linkedin_posts = linkedin_posts

            # Process all results
            combined_results = {
                "jina": jina_results,
                "exa": [result.__dict__ for result in st.session_state.exa_results] if st.session_state.exa_results else None,
                "linkedin_data": linkedin_data,
                "linkedin_posts": linkedin_posts
            }
            
            company_info_prompt = "Extract key information about the company, including its name, description, products/services, and any other relevant details."
            company_info = process_with_openrouter(company_info_prompt, combined_results, api_keys["openrouter"])
            st.session_state.company_info = company_info

            linkedin_analysis_prompt = "Analyze the company's LinkedIn presence based on their profile data and recent posts. Include insights on posting frequency, engagement, and content themes."
            linkedin_analysis = process_with_openrouter(linkedin_analysis_prompt, combined_results, api_keys["openrouter"])
            st.session_state.linkedin_analysis = linkedin_analysis

            # Generate final report
            final_report = generate_report(company_info, jina_results, st.session_state.exa_results, linkedin_data, linkedin_posts, api_keys["openrouter"])
            st.session_state.final_report = final_report

            st.success("Analysis completed!")

    if st.session_state.get('jina_results') or st.session_state.get('exa_results') or st.session_state.get('linkedin_data'):
        st.subheader("Analysis Results")
        
        if st.session_state.get('jina_results'):
            with st.expander("Jina Search Results"):
                st.json(st.session_state.jina_results)
        
        if st.session_state.get('exa_results'):
            with st.expander("Exa Search Results"):
                st.json([result.__dict__ for result in st.session_state.exa_results])

        if st.session_state.get('linkedin_data'):
            with st.expander("LinkedIn Company Data"):
                st.json(st.session_state.linkedin_data)

        if st.session_state.get('linkedin_posts'):
            with st.expander("LinkedIn Company Posts"):
                st.json(st.session_state.linkedin_posts)

        if st.session_state.get('company_info'):
            st.subheader("Company Information")
            st.write(st.session_state.company_info)

        if st.session_state.get('linkedin_analysis'):
            st.subheader("LinkedIn Presence Analysis")
            st.write(st.session_state.linkedin_analysis)

        if st.session_state.get('final_report'):
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
