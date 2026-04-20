import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

def get_llm(temperature=0):
    """
    Factory function to get the configured LLM based on environment variables.
    """
    provider = os.getenv("LLM_PROVIDER", "google").lower()
    
    if provider == "openai":
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=temperature
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620"),
            temperature=temperature
        )
    elif provider == "google" or provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            temperature=temperature,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def get_daily_rollup_llm(temperature=0):
    """
    Separate LLM factory for daily rollup operations.
    Reads DAILY_ROLLUP_* env vars independently of the main LLM config.
    """
    provider = os.getenv("DAILY_ROLLUP_LLM_PROVIDER", "google").lower()

    if provider == "openai":
        return ChatOpenAI(
            model=os.getenv("DAILY_ROLLUP_OPENAI_MODEL", "gpt-4o"),
            temperature=temperature
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model=os.getenv("DAILY_ROLLUP_ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620"),
            temperature=temperature
        )
    elif provider == "google" or provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=os.getenv("DAILY_ROLLUP_GEMINI_MODEL", "gemini-3.1-flash-lite-preview"),
            temperature=temperature,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
    else:
        raise ValueError(f"Unsupported DAILY_ROLLUP_LLM provider: {provider}")
