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
        "posts": 20,
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

def analyze_company_info(context, openrouter_api_key):
    prompt = "Provide a concise overview of the company, including its name, industry, main products/services, and any key information about its size, location, or founding."
    return process_with_openrouter(prompt, context, openrouter_api_key)

def analyze_market_position(context, openrouter_api_key):
    prompt = "Analyze the company's market position, including its main competitors, target market, and any unique selling propositions or competitive advantages."
    return process_with_openrouter(prompt, context, openrouter_api_key)

def analyze_linkedin_presence(context, openrouter_api_key):
    prompt = """Analyze the company's LinkedIn presence based on the provided data. Include:
    1. Follower count and growth trends if available
    2. Posting frequency and engagement rates
    3. Main themes and topics of their content
    4. Tone and style of their posts
    5. Any notable recent updates or announcements
    6. Overall effectiveness of their LinkedIn strategy"""
    return process_with_openrouter(prompt, context, openrouter_api_key)

def analyze_post_structure(context, openrouter_api_key):
    prompt = """Analyze the structure and characteristics of the company's LinkedIn posts. Include:
    1. Average length of posts
    2. Use of hashtags, mentions, and emojis
    3. Types of media used (text, images, videos, etc.)
    4. Call-to-actions and engagement prompts
    5. Frequency of sharing external links or company content
    Provide recommendations for creating AI-generated posts that match their style."""
    return process_with_openrouter(prompt, context, openrouter_api_key)

def generate_executive_summary(analyses, openrouter_api_key):
    context = analyses
    prompt = """Create a concise executive summary of the company based on the provided analyses. Include:
    1. Brief company overview
    2. Key points about its market position and competitive advantages
    3. Summary of their LinkedIn presence and content strategy
    4. Main insights and recommendations"""
    return process_with_openrouter(prompt, context, openrouter_api_key)

def main_app():
    st.title("Advanced Company Analyst")

    api_keys = load_api_keys()
    if not api_keys:
        return

    company_url = st.text_input("Enter the company's website URL:")
    linkedin_url = st.text_input("Enter the company's LinkedIn URL:")

    if st.button("Analyze Company") and company_url and linkedin_url:
        with st.spinner("Analyzing..."):
            # Fetch data
            jina_results = get_jina_search_results(company_url, api_keys["jina"])
            exa_results = get_exa_search_results(company_url, api_keys["exa"]) if exa_available else None
            linkedin_data = get_linkedin_company_data(linkedin_url, api_keys["rapidapi"])
            linkedin_posts = get_linkedin_company_posts(linkedin_url, api_keys["rapidapi"])

            # Store data in session state
            st.session_state.jina_results = jina_results
            st.session_state.exa_results = exa_results
            st.session_state.linkedin_data = linkedin_data
            st.session_state.linkedin_posts = linkedin_posts

            # Prepare context for analysis
            context = {
                "jina_results": jina_results,
                "exa_results": [result.__dict__ for result in exa_results] if exa_results else None,
                "linkedin_data": linkedin_data,
                "linkedin_posts": linkedin_posts
            }

            # Perform analyses
            analyses = {
                "company_info": analyze_company_info(context, api_keys["openrouter"]),
                "market_position": analyze_market_position(context, api_keys["openrouter"]),
                "linkedin_presence": analyze_linkedin_presence(context, api_keys["openrouter"]),
                "post_structure": analyze_post_structure(context, api_keys["openrouter"])
            }

            # Generate executive summary
            executive_summary = generate_executive_summary(analyses, api_keys["openrouter"])

            # Store analyses and summary in session state
            st.session_state.analyses = analyses
            st.session_state.executive_summary = executive_summary

            st.success("Analysis completed!")

    if 'analyses' in st.session_state and 'executive_summary' in st.session_state:
        # Compile all information into a single report
        full_report = f"""# Company Analysis Report

## Executive Summary

{st.session_state.executive_summary}

## Detailed Analyses

### Company Information

{st.session_state.analyses['company_info']}

### Market Position

{st.session_state.analyses['market_position']}

### LinkedIn Presence

{st.session_state.analyses['linkedin_presence']}

### Post Structure Analysis

{st.session_state.analyses['post_structure']}
"""

        st.markdown(full_report)

        # Provide download link for the full report
        st.download_button(
            label="Download Full Report",
            data=full_report,
            file_name="company_analysis_report.md",
            mime="text/markdown"
        )

        # Display raw data in expanders
        if st.session_state.jina_results:
            with st.expander("Raw Jina Search Results"):
                st.json(st.session_state.jina_results)
        
        if st.session_state.exa_results:
            with st.expander("Raw Exa Search Results"):
                st.json([result.__dict__ for result in st.session_state.exa_results])

        if st.session_state.linkedin_data:
            with st.expander("Raw LinkedIn Company Data"):
                st.json(st.session_state.linkedin_data)

        if st.session_state.linkedin_posts:
            with st.expander("Raw LinkedIn Company Posts"):
                st.json(st.session_state.linkedin_posts)

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
