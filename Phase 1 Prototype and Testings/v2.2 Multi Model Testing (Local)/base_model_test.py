import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import List, Dict, Any

def load_model_and_tokenizer(model_path: str):
    """Load the model and tokenizer from the specified path."""
    print("Loading model and tokenizer...")
    
    # Load tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    )
    
    # Ensure model is on GPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    
    print("Model and tokenizer loaded successfully!")
    return model, tokenizer, device

def generate_response(
    model: Any,
    tokenizer: Any,
    device: torch.device,
    prompt: str,
    max_new_tokens: int = 512,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> str:
    """Generate a response from the model given a prompt."""
    # Encode the input text
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    
    # Generate response
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    
    # Decode and return the response
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Remove the input prompt from the response
    response = response[len(prompt):].strip()
    return response

def chat_loop():
    """Run an interactive chat loop with the model."""
    model_path = r"D:\convo-ease\gemma-2-9b-it"  # Relative path to the model directory
    
    try:
        # Load the model and tokenizer
        model, tokenizer, device = load_model_and_tokenizer(model_path)
        
        print("\n=== Gemma 2.9B Chat ===")
        print("Type 'exit' to end the conversation.\n")
        
        # Chat loop

        # Get user input
        user_input = ("what is the tallest man made structure in the world?")

        # Generate response
        print("\nGenerating response...")
        response = generate_response(model, tokenizer, device, user_input)
        
        # Print the response
        print(f"\nGemma: {response}\n")
            
    except KeyboardInterrupt:
        print("\nChat ended by user.")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
    finally:
        # Clean up
        if 'model' in locals():
            del model
            torch.cuda.empty_cache()

if __name__ == "__main__":
    # Check for GPU availability
    if torch.cuda.is_available():
        print(f"Using GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("Warning: No GPU detected. Running on CPU will be very slow!")
    
    # Start the chat loop
    chat_loop()
