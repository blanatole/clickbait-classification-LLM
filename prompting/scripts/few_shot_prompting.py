#!/usr/bin/env python3
"""
Few-shot Prompting for clickbait classification
Method: Few-shot prompting using example samples to guide classification
"""

import os
import json
import time
import pandas as pd
import jsonlines
from dotenv import load_dotenv
from openai import OpenAI
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report

load_dotenv()

def initialize_llm():
    """Initialize OpenAI client with GPT-4o-mini"""
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY")
    )
    return client

def few_shot_prompting(client, title):
    """Few-shot prompting with curated examples"""
    prompt = f"""Classify headlines as clickbait based on these examples:

1. "Federal Reserve raises interest rates by 0.5%" → 0 (specific data, neutral)
2. "You'll NEVER believe what this dog did!" → 1 (emotional "NEVER", withholding info)
3. "Apple reports Q3 earnings: Revenue up 8%" → 0 (factual business news)
4. "This ONE trick doctors don't want you to know" → 1 ("ONE trick", conspiracy)
5. "Study: Mediterranean diet reduces heart disease 30%" → 0 (research findings)
6. "What happens next will SHOCK you completely" → 1 (emotional "SHOCK", vague)

Now classify: "{title}"

Answer: 0 or 1"""
    
    try:
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are an expert clickbait detection specialist."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Simple parsing
        if "answer:" in response_text.lower():
            answer_part = response_text.lower().split("answer:")[-1]
            if "1" in answer_part[:5]:
                return 1
            elif "0" in answer_part[:5]:
                return 0
        
        return parse_prompt_response(response_text, "few_shot")
    except Exception as e:
        print(f"Error in few-shot prompting: {e}")
        return -1

def parse_prompt_response(response_text, method="few_shot"):
    """Parse LLM response to extract prediction with improved flexibility"""
    original_text = response_text
    response_text = response_text.lower()
    

    
    # Enhanced patterns for various response formats
    patterns_1 = [
        '[1]', 'label: 1', 'classification: 1', 'answer: 1',
        '1 (clickbait)', '1(clickbait)', 'result: 1',
        'output: 1', 'prediction: 1', 'final: 1'
    ]
    
    patterns_0 = [
        '[0]', 'label: 0', 'classification: 0', 'answer: 0',
        '0 (no-clickbait)', '0(no-clickbait)', 'result: 0',
        'output: 0', 'prediction: 0', 'final: 0'
    ]
    
    # Check for explicit patterns
    for pattern in patterns_1:
        if pattern in response_text:
            return 1
    
    for pattern in patterns_0:
        if pattern in response_text:
            return 0
    
    # Fallback: look for standalone numbers at end of response
    lines = response_text.strip().split('\n')
    for line in reversed(lines):
        line = line.strip()
        if line == '1' or line.endswith(' 1') or line.startswith('1 '):
            return 1
        elif line == '0' or line.endswith(' 0') or line.startswith('0 '):
            return 0
    
    # Last resort: check for clickbait keywords
    if 'clickbait' in response_text and 'no-clickbait' not in response_text and 'not clickbait' not in response_text:
        return 1
    elif 'no-clickbait' in response_text or 'not clickbait' in response_text:
        return 0
    

    return -1  # Unable to parse

def load_evaluation_data(file_path, limit=50):
    """Load evaluation data from JSONL file"""
    data = []
    try:
        # Try direct path first
        if os.path.exists(file_path):
            current_path = file_path
        else:
            # Try relative path from current directory
            current_path = os.path.join("../../shared/data/test/data.jsonl")
            if not os.path.exists(current_path):
                # Try other paths
                possible_paths = [
                    "../../shared/data/test/data_demo.jsonl",
                    "../shared/data/test/data.jsonl",
                    "shared/data/test/data.jsonl",
                    "data/test/data.jsonl"
                ]
                current_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        current_path = path
                        break
        
        if current_path and os.path.exists(current_path):
            print(f"✅ Loading data from: {current_path}")
            with open(current_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    item = json.loads(line.strip())
                    # Extract title from text field if needed
                    if 'text' in item and '[SEP]' in item['text']:
                        text_parts = item['text'].split('[SEP]')
                        title = text_parts[0].strip().strip('"')
                        data.append({
                            'id': item.get('id', i),
                            'title': title,
                            'label': item['label'],
                            'truth_class': item.get('truth_class', 'unknown')
                        })
                    else:
                        data.append(item)
            print(f"✅ Loaded {len(data)} data samples")
        else:
            print("❌ Test data file not found")
            
    except Exception as e:
        print(f"❌ Error loading data: {e}")
    
    return data

def calculate_metrics(predictions, true_labels, method_name):
    """Calculate evaluation metrics"""
    # Filter valid predictions
    valid_indices = [i for i, pred in enumerate(predictions) if pred != -1]
    valid_predictions = [predictions[i] for i in valid_indices]
    valid_true_labels = [true_labels[i] for i in valid_indices]
    
    if len(valid_predictions) == 0:
        print(f"❌ No valid predictions for method {method_name}")
        return None
    
    # Calculate all metrics
    accuracy = accuracy_score(valid_true_labels, valid_predictions)
    
    # Macro averages
    precision_macro = precision_score(valid_true_labels, valid_predictions, average='macro', zero_division=0)
    recall_macro = recall_score(valid_true_labels, valid_predictions, average='macro', zero_division=0)
    f1_macro = f1_score(valid_true_labels, valid_predictions, average='macro', zero_division=0)
    
    # Weighted averages
    precision_weighted = precision_score(valid_true_labels, valid_predictions, average='weighted', zero_division=0)
    recall_weighted = recall_score(valid_true_labels, valid_predictions, average='weighted', zero_division=0)
    f1_weighted = f1_score(valid_true_labels, valid_predictions, average='weighted', zero_division=0)
    
    # Detailed report
    report = classification_report(valid_true_labels, valid_predictions, target_names=['No-clickbait', 'Clickbait'])
    
    print(f"\n📊 RESULTS FOR METHOD: {method_name.upper()}")
    print("=" * 60)
    print(f"Valid samples: {len(valid_predictions)}/{len(predictions)}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"\nMacro Averages:")
    print(f"  Precision (macro): {precision_macro:.4f}")
    print(f"  Recall (macro): {recall_macro:.4f}")
    print(f"  F1-Score (macro): {f1_macro:.4f}")
    print(f"\nWeighted Averages:")
    print(f"  Precision (weighted): {precision_weighted:.4f}")
    print(f"  Recall (weighted): {recall_weighted:.4f}")
    print(f"  F1-Score (weighted): {f1_weighted:.4f}")
    print("\nDetailed Classification Report:")
    print(report)
    
    return {
        'method': method_name,
        'accuracy': accuracy,
        'precision_macro': precision_macro,
        'recall_macro': recall_macro,
        'f1_macro': f1_macro,
        'precision_weighted': precision_weighted,
        'recall_weighted': recall_weighted,
        'f1_weighted': f1_weighted,
        'valid_samples': len(valid_predictions),
        'total_samples': len(predictions)
    }

def evaluate_few_shot_method(client, data, delay=1.0):
    """Evaluate few-shot prompting method"""
    predictions = []
    true_labels = []
    
    print(f"\n{'='*50}")
    print(f"🧪 EVALUATING: FEW-SHOT PROMPTING")
    print(f"{'='*50}")
    
    for i, item in enumerate(data):
        title = item['title']
        true_label = item['label']
        
        print(f"[{i+1}/{len(data)}] {title[:60]}...")
        
        prediction = few_shot_prompting(client, title)
        predictions.append(prediction)
        true_labels.append(true_label)
        
        if prediction != -1:
            label_map = {0: "No-clickbait", 1: "Clickbait"}
            label_name = label_map.get(prediction, "Unknown")
            print(f"  → {prediction} - {label_name}")
        else:
            print(f"  → Response parsing error")
        
        time.sleep(delay)  # Rate limiting
    
    return predictions, true_labels

def run_few_shot_evaluation(client, data_limit=20):
    """Run few-shot evaluation"""
    print("🚀 FEW-SHOT PROMPTING EVALUATION")
    print("=" * 60)
    
    # Load test data
    data_path = "../../shared/data/test/data.jsonl"
    test_data = load_evaluation_data(data_path, limit=data_limit)
    
    if not test_data:
        print("❌ Unable to load test data")
        return
    
    print(f"✅ Loaded {len(test_data)} test samples\n")
    
    try:
        predictions, true_labels = evaluate_few_shot_method(
            client, test_data, delay=1.0
        )
        metrics = calculate_metrics(predictions, true_labels, "few_shot")
        if metrics:
            print(f"✅ Few-shot evaluation completed successfully!")
        else:
            print(f"⚠️ Few-shot evaluation failed to generate valid metrics")
            
    except KeyboardInterrupt:
        print("\n⚠️ Stopped by user")
    except Exception as e:
        print(f"❌ Error in few-shot evaluation: {e}")

def demo_few_shot_examples(client):
    """Demo with specific examples"""
    print("\n🎯 FEW-SHOT PROMPTING DEMO")
    print("=" * 50)
    
    examples = [
        "Federal Reserve announces new monetary policy changes",
        "This SHOCKING discovery will blow your mind!",
        "Microsoft reports record quarterly profits",
        "Doctors hate him for this ONE weird trick",
        "Breaking: Major trade agreement signed between countries"
    ]
    
    for i, title in enumerate(examples, 1):
        print(f"\n--- Example {i} ---")
        print(f"Headline: {title}")
        
        # Test few-shot
        result = few_shot_prompting(client, title)
        label = "Clickbait" if result == 1 else "Not Clickbait" if result == 0 else "Error"
        print(f"Result: {result} ({label})")
        
        time.sleep(0.5)

def main():
    """Main function with examples"""
    print("🎯 FEW-SHOT PROMPTING FOR CLICKBAIT CLASSIFICATION (OpenAI)")
    print("=" * 60)
    
    # Check environment variables
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ Error: Please set OPENAI_API_KEY in .env file")
        print("   Get your API key from: https://platform.openai.com/api-keys")
        return
    
    print("🚀 Initializing OpenAI client...")
    try:
        client = initialize_llm()
        print("✅ Initialization successful!\n")
    except Exception as e:
        print(f"❌ OpenAI client initialization error: {e}")
        return
    
    # Run demo
    demo_few_shot_examples(client)
    
    # Run evaluation - test with 25 samples first
    print("\n" + "="*60)
    print("Would you like to run full evaluation? (25 samples)")
    print("Press Enter to continue or Ctrl+C to stop...")
    input()
    
    run_few_shot_evaluation(client, data_limit=25)

if __name__ == "__main__":
    main() 