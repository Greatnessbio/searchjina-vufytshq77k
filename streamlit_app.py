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
            "rapidapi": st.secrets["secrets"]["rapidapi_key"],
            "exa": st.secrets["secrets"]["exa_api_key"] if exa_available else None
        }
    except KeyError as e:
        st.error(f"{e} API key not found in secrets.toml. Please add it.")
        return None

def load_users():
    return st.secrets["users"]

def login(username, password):
    users = load_users()
    if username in users and users[username] == password:
        return True
    return False

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
                st.error("Failed to fetch Jina search results. Please try again later.")
    return None

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
        LOGGER.error(f"Exa search request failed: {e}")
        st.error(f"Failed to fetch Exa search results. Please try again later. Error: {e}")
    return None

def get_company_info(company_url, rapidapi_key):
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
        LOGGER.error(f"Company info API request failed: {e}")
        st.error("Failed to fetch company information. Please try again later.")
    return None

def get_company_posts(company_url, rapidapi_key):
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
        LOGGER.error(f"Company posts API request failed: {e}")
        st.error("Failed to fetch company posts. Please try again later.")
    return None

def create_company_summary(company_info):
    if 'data' not in company_info:
        return "No company information available."

    data = company_info['data']
    summary = f"# {data.get('companyName', 'N/A')}\n\n"
    
    if 'logoResolutionResult' in data:
        summary += f"![Company Logo]({data['logoResolutionResult']})\n\n"
    
    summary += f"**Industry:** {data.get('industry', 'N/A')}\n"
    summary += f"**Company Size:** {data.get('employeeCount', 'N/A')} employees\n"
    summary += f"**Headquarters:** {data.get('headquarter', {}).get('city', 'N/A')}, {data.get('headquarter', {}).get('country', 'N/A')}\n"
    
    founded_on = data.get('foundedOn', 'N/A')
    if isinstance(founded_on, dict):
        founded_year = founded_on.get('year', 'N/A')
    elif isinstance(founded_on, str):
        founded_year = founded_on
    else:
        founded_year = 'N/A'
    summary += f"**Founded:** {founded_year}\n"
    
    summary += f"**Specialties:** {', '.join(data.get('specialities', ['N/A']))}\n\n"
    summary += f"**Description:** {data.get('description', 'N/A')}\n\n"
    
    summary += "## Competitors\n"
    for competitor in data.get('similarOrganizations', [])[:5]:
        summary += f"- **{competitor.get('name', 'N/A')}** ({competitor.get('industry', 'N/A')})\n"
    
    return summary

def analyze_posts(posts):
    post_texts = [post.get('postText', '') for post in posts if post.get('postText')]
    combined_text = "\n\n".join(post_texts)
    
    prompt = """Analyze the following LinkedIn posts and provide insights on:
    1. Content style (formal, casual, professional, etc.)
    2. Tone (informative, persuasive, inspirational, etc.)
    3. Common themes or topics
    4. Use of hashtags or mentions
    5. Length and structure of posts
    6. Engagement patterns (likes, comments, shares)
    
    Provide a summary of your analysis."""
    
    return analyze_text(combined_text, prompt)

def generate_post_prompt(company_info, post_analysis):
    prompt = f"""Based on the following company information and post analysis, create a detailed prompt that can be used to generate LinkedIn posts in the style of this company:

    Company Information:
    {json.dumps(company_info.get('data', {}), indent=2)}

    Post Analysis:
    {post_analysis}

    Your task is to create a prompt that captures:
    1. The company's industry and focus
    2. The typical content style and tone used in their posts
    3. Common themes and topics they discuss
    4. Their use of hashtags and mentions
    5. The typical length and structure of their posts
    6. Any other unique characteristics of their LinkedIn communication

    Provide the prompt in a format that can be directly used to generate new posts."""
    
    return analyze_text(prompt, prompt)

def analyze_text(text, prompt):
    api_keys = load_api_keys()
    if not api_keys or 'openrouter' not in api_keys:
        return "Error: OpenRouter API key not found."

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_keys['openrouter']}"},
            json={
                "model": "anthropic/claude-3-sonnet-20240229",
                "messages": [
                    {"role": "system", "content": "You are an expert in content analysis and creation."},
                    {"role": "user", "content": prompt + "\n\n" + text}
                ]
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.RequestException as e:
        LOGGER.error(f"OpenRouter API request failed: {e}")
        return f"Error: Failed to generate analysis. Please try again later. Details: {str(e)}"
    except (KeyError, IndexError, ValueError) as e:
        LOGGER.error(f"Error processing OpenRouter API response: {e}")
        return f"Error: Failed to process the generated content. Please try again. Details: {str(e)}"

def main_app():
    api_keys = load_api_keys()
    if not api_keys:
        return

    company_url = st.text_input("Enter LinkedIn Company URL:")

    if company_url:
        if 'company_info' not in st.session_state:
            with st.spinner("Fetching company information..."):
                company_info = get_company_info(company_url, api_keys["rapidapi"])
                if company_info:
                    st.session_state.company_info = company_info
                    st.success("Company information fetched successfully!")
                else:
                    st.error("Failed to fetch company information. Please try again.")
                    return

        if 'company_summary' not in st.session_state:
            st.session_state.company_summary = create_company_summary(st.session_state.company_info)

        st.markdown(st.session_state.company_summary)

        if 'jina_results' not in st.session_state:
            with st.spinner("Fetching Jina search results..."):
                jina_results = get_jina_search_results(company_url, api_keys["jina"])
                if jina_results:
                    st.session_state.jina_results = jina_results
                    st.success("Jina search results fetched successfully!")
                else:
                    st.warning("Failed to fetch Jina search results. Continuing with limited information.")

        if 'exa_results' not in st.session_state and exa_available:
            with st.spinner("Fetching Exa search results..."):
                exa_results = get_exa_search_results(company_url, api_keys["exa"])
                if exa_results:
                    st.session_state.exa_results = exa_results
                    st.success("Exa search results fetched successfully!")
                else:
                    st.warning("Failed to fetch Exa search results. Continuing with limited information.")

        if st.button("Analyze Company Posts"):
            if 'company_posts' not in st.session_state:
                with st.spinner("Fetching company posts..."):
                    company_posts = get_company_posts(company_url, api_keys["rapidapi"])
                    if company_posts:
                        st.session_state.company_posts = company_posts
                        st.success("Company posts fetched successfully!")
                    else:
                        st.error("Failed to fetch company posts. Please try again.")
                        return

            with st.spinner("Analyzing company posts..."):
                post_analysis = analyze_posts(st.session_state.company_posts.get('response', []))
                st.subheader("Post Analysis")
                st.write(post_analysis)
                st.session_state.post_analysis = post_analysis

        if 'post_analysis' in st.session_state and st.button("Generate AI Prompt for Posts"):
            with st.spinner("Generating AI prompt..."):
                ai_prompt = generate_post_prompt(st.session_state.company_info, st.session_state.post_analysis)
                st.subheader("AI Prompt for Generating Posts")
                st.text_area("Generated Prompt", ai_prompt, height=300)

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
        st.title("LinkedIn Company Analysis")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()
        else:
            main_app()

    st.caption("Note: This app uses RapidAPI's LinkedIn Data Scraper, Jina AI, Exa, and OpenRouter for AI model access. Make sure you have valid API keys for all services.")

if __name__ == "__main__":
    display()
