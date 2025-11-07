from chatbot import MiraMusicRecommendationBot
import os
import sys
import json

def validate_json_file(json_file_path: str) -> bool:
    """Validate JSON file exists and has valid structure"""
    if not os.path.exists(json_file_path):
        print(f"JSON file not found: {json_file_path}")
        return False
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if it's a valid structure
        if isinstance(data, list) and len(data) > 0:
            #print(f"Valid JSON array with {len(data)} items")
            return True
        elif isinstance(data, dict) and any(key in data for key in ['tracks', 'data', 'results']):
            #print(f"Valid JSON object structure")
            return True
        else:
            #print(f" JSON structure might not be optimal, but will attempt to load")
            return True
            
    except json.JSONDecodeError as e:
        print(f"Invalid JSON format: {e}")
        return False
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

def main():
    print("🎵 MIRA - Hoopr Music Recommender Initializing...")
    print("=" * 70)
    
    # Determine JSON file path
    json_file = r"C:\Users\AAAA\Desktop\chatbot\chatbot-be\hoopr_data_v2.json"  # Default file
    
    # Allow JSON file path via command line argument
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
       # print(f"Using custom JSON file: {json_file}")
    else:
        print(f"Using default JSON file: {json_file}")
    
    # Validate JSON file
    if not validate_json_file(json_file):
        print("\n💡 Usage: python run_chatbot.py [path_to_json_file]")
        print("Example: python run_chatbot.py my_tracks.json")
        sys.exit(1)
    
    try:
        # Initialize MIRA with JSON file
        print("Initializing MIRA AI...")
        bot = MiraMusicRecommendationBot(json_file, "MIRA - Hoopr Music AI")
        
        if not bot.tracks_data:
            print("No tracks were loaded from the JSON file!")
            print("Please check your JSON file format and try again.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Failed to initialize MIRA: {e}")
        print("Please check your JSON file format and openai_utils configuration.")
        sys.exit(1)
    
    # Display startup info
    print("MIRA - Hoopr Music Recommender is ready!")
    # print(bot.get_stats())
    # print("\n💬 Ask me for music recommendations for your:")
    # print("   • Instagram Reels & TikTok videos")
    # print("   • Brand campaigns & commercials") 
    # print("   • Content creation & licensing needs")
    # print("\n🔧 Commands:")
    # print("   • Type 'quit' or 'exit' to end session")
    # print("   • Type 'reset' to clear conversation history")
    # print("   • Type 'stats' to see track statistics")
    # print("=" * 70)
    
    # Main chat loop
    while True:
        try:
            user_input = input("\n You: ").strip()
            
            # Handle exit commands
            if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
                print("Thank you for using MIRA! Visit hooprsmash.com for more music!")
                break
            
            # Handle utility commands
            if user_input.lower() == 'reset':
                bot.reset()
                continue
                
            if user_input.lower() == 'stats':
                print(f"{bot.get_stats()}")
                continue
            
            # Handle empty input
            if not user_input:
                print("Please describe what kind of music you need!")
                print("Example: 'I need upbeat music for a fitness brand reel'")
                continue
            
            # Get MIRA response
            print("MIRA is analyzing your request and matching tracks...")
            response = bot.chat(user_input)
            print(f"\nMIRA: {response}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Session interrupted. Goodbye!")
            break
        except EOFError:
            print("\n\n👋 Session ended. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again or restart MIRA.")

if __name__ == "__main__":
    main()
