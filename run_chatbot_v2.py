from chatbot_v2 import MiraMusicRecommendationBotV2
import os
import sys

def validate_database(db_path: str) -> bool:
    """Validate database file exists"""
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return False
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if audio_tags table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audio_tags'")
        if not cursor.fetchone():
            print(f"Warning: audio_tags table not found in {db_path}")
            print("The table will be created automatically on first run.")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error validating database: {e}")
        return False

def main():
    print("🎵 MIRA V2 - Hoopr Music Recommender (Database Edition) Initializing...")
    print("=" * 70)
    
    # Determine database path
    db_path = "ingestion_sheet.db"  # Default database
    
    # Allow database path via command line argument
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        print(f"Using custom database: {db_path}")
    else:
        print(f"Using default database: {db_path}")
    
    # Validate database file
    if not validate_database(db_path):
        print("\n💡 Usage: python run_chatbot_v2.py [path_to_database]")
        print("Example: python run_chatbot_v2.py recommendation.db")
        print("\nNote: If the database doesn't exist, it will be created automatically.")
        sys.exit(1)
    
    try:
        # Initialize MIRA V2 with database
        print("Initializing MIRA AI V2...")
        bot = MiraMusicRecommendationBotV2(db_path=db_path, bot_name="MIRA V2 - Hoopr Music AI")
        
        # Load tracks from database
        print("Loading tracks from database...")
        bot.tracks_data = bot._load_tracks_from_db()
        
        if not bot.tracks_data:
            print("⚠️  No tracks were loaded from the database!")
            print("The audio_tags table might be empty.")
            print("You can still use the chatbot, but recommendations may be limited.")
        else:
            print(f"✅ Loaded {len(bot.tracks_data)} tracks from database")
            
    except Exception as e:
        print(f"Failed to initialize MIRA V2: {e}")
        print("Please check your database file and configuration.")
        sys.exit(1)
    
    # Display startup info
    print("\nMIRA V2 - Hoopr Music Recommender is ready!")
    print(bot.get_stats())
    print("\n💬 Ask me for music recommendations for your:")
    print("   • Instagram Reels & TikTok videos")
    print("   • Brand campaigns & commercials") 
    print("   • Content creation & licensing needs")
    print("\n🔧 Commands:")
    print("   • Type 'quit' or 'exit' to end session")
    print("   • Type 'reset' to clear conversation history")
    print("   • Type 'stats' to see track statistics")
    print("   • Type 'refresh' to reload tracks from database")
    print("=" * 70)
    
    # Main chat loop
    while True:
        try:
            user_input = input("\n You: ").strip()
            
            # Handle exit commands
            if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
                print("Thank you for using MIRA V2! Visit hooprsmash.com for more music!")
                break
            
            # Handle utility commands
            if user_input.lower() == 'reset':
                bot.reset()
                continue
                
            if user_input.lower() == 'stats':
                print(f"{bot.get_stats()}")
                continue
            
            if user_input.lower() == 'refresh':
                print("Refreshing tracks from database...")
                bot.refresh_tracks()
                print(f"✅ Refreshed! {len(bot.tracks_data)} tracks loaded.")
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
            print("Please try again or restart MIRA V2.")

if __name__ == "__main__":
    main()

