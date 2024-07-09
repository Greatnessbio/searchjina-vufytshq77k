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

def process_with_openrouter(prompt, jina_results, openrouter_api_key):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json"
    }
    
    full_prompt = f"""Jina AI search results:
{json.dumps(jina_results, indent=2)}

Task: {prompt}

Provide a response based on the Jina AI search results and the given task."""

    payload = {
        "model": "anthropic/claude-3-sonnet-20240229",
        "messages": [
            {"role": "system", "content": "You are an AI assistant tasked with processing and analyzing information from Jina AI search results."},
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
    st.title("Jina AI Search with OpenRouter Summary and Chat")

    api_keys = load_api_keys()
    if not api_keys:
        return

    if 'jina_results' not in st.session_state:
        st.session_state.jina_results = None
    if 'summary' not in st.session_state:
        st.session_state.summary = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    query = st.text_input("Enter your search query:")

    if st.button("Search") and query:
        with st.spinner("Searching..."):
            jina_results = get_jina_search_results(query, api_keys["jina"])
            if jina_results:
                st.session_state.jina_results = jina_results
                st.success("Search completed. Generating summary...")
                summary = process_with_openrouter("Provide a concise summary of these search results.", jina_results, api_keys["openrouter"])
                if summary:
                    st.session_state.summary = summary
                    st.success("Summary generated.")
                else:
                    st.error("Failed to generate summary.")
            else:
                st.error("No results found or an error occurred.")

    if st.session_state.jina_results:
        st.subheader("Raw Jina AI Search Results")
        st.text_area("Raw Results", json.dumps(st.session_state.jina_results, indent=2), height=300)

        if st.session_state.summary:
            st.subheader("Concise Summary")
            st.write(st.session_state.summary)

        st.subheader("Chat with the Data")
        for message in st.session_state.chat_history:
            st.write(f"{'You' if message['role'] == 'user' else 'AI'}: {message['content']}")

        user_message = st.text_input("Enter your message:")
        if st.button("Send"):
            if user_message:
                st.session_state.chat_history.append({"role": "user", "content": user_message})
                response = process_with_openrouter(user_message, st.session_state.jina_results, api_keys["openrouter"])
                if response:
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    st.rerun()
                else:
                    st.error("Failed to get a response.")

        if st.button("Clear Chat History"):
            st.session_state.chat_history = []
            st.success("Chat history cleared.")

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
