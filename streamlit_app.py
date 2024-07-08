import streamlit as st
import requests
import json
import time

def load_api_keys():
    try:
        return {
            "jina": st.secrets["secrets"]["jina_api_key"],
            "openrouter": st.secrets["secrets"]["openrouter_api_key"]
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
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                st.error(f"Jina AI search request failed after {max_retries} attempts: {e}")
    return None

def process_with_openrouter(prompt, context, openrouter_api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json"
    }
    
    full_prompt = f"""Context from previous interactions:
{context}

Current task:
{prompt}

Provide a response based on the context and the current task."""

    payload = {
        "model": "anthropic/claude-3-sonnet-20240229",
        "messages": [
            {"role": "system", "content": "You are an AI assistant tasked with processing and analyzing information from Jina AI search results and previous interactions."},
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

def main_app():
    st.title("Jina AI Search with OpenRouter Sequential Prompts")

    api_keys = load_api_keys()
    if not api_keys:
        return

    if 'jina_results' not in st.session_state:
        st.session_state.jina_results = None
    if 'context' not in st.session_state:
        st.session_state.context = ""

    query = st.text_input("Enter your search query:")

    if st.button("Search") and query:
        with st.spinner("Searching..."):
            jina_results = get_jina_search_results(query, api_keys["jina"])
            if jina_results:
                st.session_state.jina_results = jina_results
                st.subheader("Raw Jina AI Search Results")
                st.json(jina_results)
            else:
                st.error("No results found or an error occurred.")

    if st.session_state.jina_results:
        prompt = st.text_area("Enter your prompt for analysis:")
        if st.button("Process Prompt"):
            with st.spinner("Processing..."):
                result = process_with_openrouter(prompt, st.session_state.context, api_keys["openrouter"])
                if result:
                    st.subheader("Analysis Result")
                    st.write(result)
                    st.session_state.context += f"\nPrompt: {prompt}\nResult: {result}\n"
                else:
                    st.error("Failed to process the prompt.")

        if st.button("Clear Context"):
            st.session_state.context = ""
            st.success("Context cleared.")

        st.subheader("Current Context")
        st.text_area("Context", st.session_state.context, height=300, disabled=True)

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
