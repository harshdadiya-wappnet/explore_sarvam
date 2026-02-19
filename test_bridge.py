#!/usr/bin/env python3
"""
Test script for Sarvam AI OpenAI-compatible bridge

Demonstrates both Chat Completions and Responses API endpoints
"""

import os
import sys
from openai import OpenAI

from dotenv import load_dotenv

load_dotenv()

# Configuration
BASE_URL = os.getenv("BRIDGE_URL", "http://localhost:8000")
API_KEY = os.getenv("SARVAM_API_KEY")

# Initialize client
client = OpenAI(base_url=BASE_URL, api_key=API_KEY)


def test_health_check():
    """Test health check endpoint"""
    print("\n=== Health Check ===")
    try:
        import httpx
        response = httpx.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_list_models():
    """Test model listing"""
    print("\n=== List Models ===")
    try:
        models = client.models.list()
        for model in models.data:
            print(f"- {model.id} (owner: {model.owned_by})")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_chat_completions():
    """Test Chat Completions API (legacy)"""
    print("\n=== Chat Completions API ===")
    try:
        response = client.chat.completions.create(
            model="sarvam-m",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2+2? Answer in one sentence."}
            ],
            max_tokens=100,
            temperature=0.1
        )
        
        print(f"Response ID: {response.id}")
        print(f"Model: {response.model}")
        print(f"Finish Reason: {response.choices[0].finish_reason}")
        print(f"Content: {response.choices[0].message.content}")
        if response.usage:
            print(f"Tokens - Prompt: {response.usage.prompt_tokens}, Completion: {response.usage.completion_tokens}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_responses_api_simple():
    """Test Responses API with simple string input"""
    print("\n=== Responses API (Simple Input) ===")
    try:
        response = client.responses.create(
            model="sarvam-m",
            input="What is 3+3? Answer in one sentence.",
            instructions="You are a helpful math assistant.",
            max_output_tokens=100,
            temperature=0.1
        )
        
        print(f"Response ID: {response.id}")
        print(f"Model: {response.model}")
        print(f"Output Type: {response.output[0].type}")
        print(f"Content: {response.output_text}")
        if response.usage:
            print(f"Tokens - Prompt: {response.usage.prompt_tokens}, Completion: {response.usage.completion_tokens}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_responses_api_array():
    """Test Responses API with message array input"""
    print("\n=== Responses API (Array Input) ===")
    try:
        response = client.responses.create(
            model="sarvam-m",
            input=[
                {"role": "user", "content": "What is the capital of France?"},
                {"role": "assistant", "content": "Paris is the capital of France."},
                {"role": "user", "content": "What about Germany?"}
            ],
            instructions="You are a geography expert.",
            max_output_tokens=100,
            temperature=0.1
        )
        
        print(f"Response ID: {response.id}")
        print(f"Model: {response.model}")
        print(f"Output Type: {response.output[0].type}")
        print(f"Content: {response.output_text}")
        if response.usage:
            print(f"Tokens - Prompt: {response.usage.prompt_tokens}, Completion: {response.usage.completion_tokens}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_responses_api_chain():
    """Test Responses API with chained responses"""
    print("\n=== Responses API (Chained Responses) ===")
    try:
        # First response
        response1 = client.responses.create(
            model="sarvam-m",
            input="What is the capital of France?",
            instructions="You are a helpful assistant.",
            max_output_tokens=100,
            temperature=0.1,
            store=True
        )
        
        print(f"First Response ID: {response1.id}")
        print(f"Content: {response1.output_text}")
        
        # Chain second response
        response2 = client.responses.create(
            model="sarvam-m",
            input="What is its population?",
            previous_response_id=response1.id
        )
        
        print(f"Second Response ID: {response2.id}")
        print(f"Content: {response2.output_text}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Sarvam AI Bridge - Test Suite")
    print("=" * 60)
    print(f"Bridge URL: {BASE_URL}")
    print(f"Using API Key: {API_KEY[:10]}...")
    
    tests = [
        ("Health Check", test_health_check),
        ("List Models", test_list_models),
        ("Chat Completions API", test_chat_completions),
        ("Responses API - Simple", test_responses_api_simple),
        ("Responses API - Array", test_responses_api_array),
        ("Responses API - Chained", test_responses_api_chain),
    ]
    
    results = {}
    for name, test_func in tests:
        results[name] = test_func()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())