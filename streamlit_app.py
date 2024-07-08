import streamlit as st
import requests

def load_jina_api_key():
    try:
        return st.secrets["secrets"]["jina_api_key"]
    except KeyError:
        st.error("Jina API key not found in secrets.toml. Please add it.")
        return None

def get_jina_search_results(query, jina_api_key):
    url = f"https://s.jina.ai/{requests.utils.quote(query)}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {jina_api_key}",
        "X-With-Generated-Alt": "true",
        "X-With-Images-Summary": "true",
        "X-With-Links-Summary": "true"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Jina AI search request failed: {e}")
    return None

def main():
    st.title("Jina AI Search Test")

    jina_api_key = load_jina_api_key()
    if not jina_api_key:
        return

    query = st.text_input("Enter your search query:")

    if st.button("Search") and query:
        with st.spinner("Searching..."):
            results = get_jina_search_results(query, jina_api_key)
            if results:
                st.subheader("Search Results")
                st.json(results)  # Display the full JSON response
                
                # Display the answer if available
                if 'answer' in results:
                    st.subheader("Answer")
                    st.write(results['answer'])
                
                # Display image summaries if available
                if 'images_summary' in results:
                    st.subheader("Image Summaries")
                    for image in results['images_summary']:
                        st.image(image['url'], caption=image['alt'])
                
                # Display link summaries if available
                if 'links_summary' in results:
                    st.subheader("Link Summaries")
                    for link in results['links_summary']:
                        st.write(f"[{link['title']}]({link['url']})")
                        st.write(link['summary'])
            else:
                st.error("No results found or an error occurred.")

if __name__ == "__main__":
    main()
