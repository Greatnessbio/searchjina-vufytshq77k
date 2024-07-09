import streamlit as st
import requests
import json
import time
import base64
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

def analyze_company_info(context, openrouter_api_key):
    prompt = """
    Analyze the provided information and create a detailed company profile including:
    1. Company name and brief description
    2. Industry and main products/services
    3. Company size, location, and founding year
    4. Key executives and their roles
    5. Recent company developments or notable achievements
    """
    return process_with_openrouter(prompt, context, openrouter_api_key)

def analyze_competitors(context, openrouter_api_key):
    prompt = """
    Based on the provided information, analyze the company's competitive landscape:
    1. Identify main competitors and provide a brief description of each
    2. Compare the company's products/services with those of competitors
    3. Analyze the company's unique selling propositions (USPs) and competitive advantages
    4. Identify potential market threats or challenges from competitors
    """
    return process_with_openrouter(prompt, context, openrouter_api_key)

def analyze_linkedin_presence(context, openrouter_api_key):
    prompt = """
    Analyze the company's LinkedIn presence based on their profile data and recent posts:
    1. Follower count and growth trends (if available)
    2. Posting frequency and engagement rates
    3. Main themes and topics of their content
    4. Tone and style of their posts
    5. Use of hashtags, mentions, and media in posts
    6. Notable recent updates or announcements
    7. Overall effectiveness of their LinkedIn strategy
    """
    return process_with_openrouter(prompt, context, openrouter_api_key)
def analyze_linkedin_profile(context, openrouter_api_key):
    prompt = """
    Analyze the company's LinkedIn profile based on the provided data:
    1. Follower count and any available growth trends
    2. Company description and key information
    3. Stated specialties and focus areas
    4. Employee count and any insights on company size/growth
    5. Listed locations and headquarters
    6. Any notable achievements or milestones mentioned
    
    Provide a summary of the company's LinkedIn profile presence and any insights on how they're presenting themselves on the platform.
    """
    return process_with_openrouter(prompt, context, openrouter_api_key)

def analyze_linkedin_posts(context, openrouter_api_key):
    prompt = """
    Analyze the company's LinkedIn posts based on the provided data:
    1. Posting frequency and consistency
    2. Types of content shared (e.g., company news, industry insights, product information)
    3. Use of media (images, videos, links) in posts
    4. Engagement metrics (likes, comments, shares) and trends
    5. Use of hashtags and mentions
    6. Tone and style of writing in posts
    7. Any recurring themes or campaigns
    8. Notable recent announcements or updates
    
    Provide a summary of the company's content strategy on LinkedIn, including strengths and areas for improvement.
    """
    return process_with_openrouter(prompt, context, openrouter_api_key)

def generate_executive_summary(analyses, openrouter_api_key):
    context = analyses
    prompt = """
    Create a concise executive summary of the company based on the provided analyses. Include:
    1. Brief company overview and key statistics
    2. Main products/services and target market
    3. Key competitive advantages and market position
    4. Summary of main competitors and competitive landscape
    5. Overview of LinkedIn presence and social media strategy
    6. Key strengths, weaknesses, opportunities, and threats (SWOT)
    7. Main insights and recommendations for future growth
    
    The summary should be concise yet comprehensive, highlighting the most important findings from the analysis.
    """
    return process_with_openrouter(prompt, context, openrouter_api_key)

def get_download_link(content, filename, text):
    b64 = base64.b64encode(content.encode()).decode()
    return f'<a href="data:file/txt;base64,{b64}" download="{filename}">{text}</a>'

def main_app():
    st.title("Comprehensive Company Analyst")

    api_keys = load_api_keys()
    if not api_keys:
        return

    company_url = st.text_input("Enter the company's website URL:")
    linkedin_url = st.text_input("Enter the company's LinkedIn URL:")

    if st.button("Analyze Company") and company_url and linkedin_url:
        with st.spinner("Analyzing... This may take a few minutes."):
            # Fetch data
            jina_results = get_jina_search_results(company_url, api_keys["jina"])
            exa_results = get_exa_search_results(company_url, api_keys["exa"]) if exa_available else None
            linkedin_data = get_linkedin_company_data(linkedin_url, api_keys["rapidapi"])
            linkedin_posts = get_linkedin_company_posts(linkedin_url, api_keys["rapidapi"])

            # Store raw data in session state
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
            company_info = analyze_company_info(context, api_keys["openrouter"])
            competitor_analysis = analyze_competitors(context, api_keys["openrouter"])
            linkedin_profile_analysis = analyze_linkedin_profile(context, api_keys["openrouter"])
            linkedin_posts_analysis = analyze_linkedin_posts(context, api_keys["openrouter"])

            # Store analyses in session state
            st.session_state.company_info = company_info
            st.session_state.competitor_analysis = competitor_analysis
            st.session_state.linkedin_profile_analysis = linkedin_profile_analysis
            st.session_state.linkedin_posts_analysis = linkedin_posts_analysis

            # Generate executive summary
            analyses = {
                "company_info": company_info,
                "competitor_analysis": competitor_analysis,
                "linkedin_profile_analysis": linkedin_profile_analysis,
                "linkedin_posts_analysis": linkedin_posts_analysis
            }
            executive_summary = generate_executive_summary(analyses, api_keys["openrouter"])
            st.session_state.executive_summary = executive_summary

            # Compile full report
            full_report = f"""# Comprehensive Company Analysis

## Executive Summary

{executive_summary}

## Detailed Company Information

{company_info}

## Competitor Analysis

{competitor_analysis}

## LinkedIn Profile Analysis

{linkedin_profile_analysis}

## LinkedIn Posts Analysis

{linkedin_posts_analysis}
"""
            st.session_state.full_report = full_report

            st.success("Analysis completed!")

    if 'full_report' in st.session_state:
        st.markdown(st.session_state.full_report)

        # Provide download link for the full report
        report_filename = "comprehensive_company_analysis.md"
        download_link = get_download_link(st.session_state.full_report, report_filename, "Download Full Report")
        st.markdown(download_link, unsafe_allow_html=True)

        # Display raw data in expanders
        if st.session_state.get('jina_results'):
            with st.expander("Raw Jina Search Results"):
                st.json(st.session_state.jina_results)
        
        if st.session_state.get('exa_results'):
            with st.expander("Raw Exa Search Results"):
                st.json([result.__dict__ for result in st.session_state.exa_results])

        if st.session_state.get('linkedin_data'):
            with st.expander("Raw LinkedIn Company Data"):
                st.json(st.session_state.linkedin_data)

        if st.session_state.get('linkedin_posts'):
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
