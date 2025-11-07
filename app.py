from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import json
import logging
import time
from chatbot import MiraMusicRecommendationBot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global bot instance
bot = None

def initialize_bot(json_file_path=None):
    """Initialize the MIRA bot with tracks data"""
    global bot
    
    if json_file_path is None:
        json_file_path = r"C:\Users\AAAA\Desktop\chatbot\chatbot-be\hoopr_data_v2.json"
    
    try:
        if not os.path.exists(json_file_path):
            raise FileNotFoundError(f"JSON file not found: {json_file_path}")
        
        bot = MiraMusicRecommendationBot(json_file_path, "MIRA - Hoopr Music AI")
        
        if not bot.tracks_data:
            raise ValueError("No tracks were loaded from the JSON file")
        
        logger.info(f"MIRA bot initialized successfully with {len(bot.tracks_data)} tracks")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize MIRA bot: {e}")
        return False

@app.route('/', methods=['GET'])
def home():
    """Home endpoint with API information"""
    return jsonify({
        "message": "🎵 MIRA - Hoopr Music Recommender API",
        "version": "1.0.0",
        "status": "active" if bot else "bot_not_initialized",
        "endpoints": {
            "health": "GET /health - Check server health",
            "chat": "POST /chat - Send messages to MIRA",
            "stats": "GET /stats - Get track statistics", 
            "reset": "POST /reset - Reset conversation",
            "conversation": "GET /conversation - Get conversation history",
            "init": "POST /init - Reinitialize bot"
        },
        "example_curl": "curl -X POST http://localhost:5000/chat -H 'Content-Type: application/json' -d '{\"message\": \"I need music for my video\"}'"
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    if bot is None:
        return jsonify({
            "status": "error",
            "message": "Bot not initialized"
        }), 503
    
    return jsonify({
        "status": "healthy",
        "bot_name": bot.bot_name,
        "tracks_loaded": len(bot.tracks_data) if bot.tracks_data else 0,
        "server_time": int(time.time())
    })

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint for music recommendations and conversations"""
    if bot is None:
        return jsonify({
            "error": "Bot not initialized. Please restart the server or call /init endpoint."
        }), 503
    
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                "error": "Missing 'message' field in request body",
                "example": {"message": "I need music for my video"}
            }), 400
        
        user_message = data['message'].strip()
        
        if not user_message:
            return jsonify({
                "error": "Message cannot be empty",
                "example": {"message": "I need upbeat music for Instagram reels"}
            }), 400
        
        # Log the request
        logger.info(f"Chat request: {user_message}")
        
        # Get bot response
        response = bot.chat(user_message)
        
        return jsonify({
            "success": True,
            "user_message": user_message,
            "bot_response": response,
            "bot_name": bot.bot_name,
            "timestamp": int(time.time()),
            "conversation_length": len(bot.conversation)
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            "error": f"Internal server error: {str(e)}"
        }), 500

@app.route('/reset', methods=['POST'])
def reset_conversation():
    """Reset the conversation history"""
    if bot is None:
        return jsonify({
            "error": "Bot not initialized"
        }), 503
    
    try:
        bot.reset()
        logger.info("Conversation history reset")
        return jsonify({
            "success": True,
            "message": "Conversation history reset successfully",
            "timestamp": int(time.time())
        })
    except Exception as e:
        logger.error(f"Error resetting conversation: {e}")
        return jsonify({
            "error": f"Failed to reset conversation: {str(e)}"
        }), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get statistics about loaded tracks"""
    if bot is None:
        return jsonify({
            "error": "Bot not initialized"
        }), 503
    
    try:
        stats_text = bot.get_stats()
        
        # Parse stats for structured response
        total_tracks = len(bot.tracks_data) if bot.tracks_data else 0
        with_vocals = sum(1 for track in bot.tracks_data if track.get('hasVocals', '').lower() in ['true', '1', 'yes'])
        explicit = sum(1 for track in bot.tracks_data if track.get('isExplicit', '').lower() in ['true', '1', 'yes'])
        
        return jsonify({
            "success": True,
            "total_tracks": total_tracks,
            "tracks_with_vocals": with_vocals,
            "explicit_tracks": explicit,
            "non_explicit_tracks": total_tracks - explicit,
            "instrumental_tracks": total_tracks - with_vocals,
            "stats_text": stats_text,
            "timestamp": int(time.time())
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({
            "error": f"Failed to get stats: {str(e)}"
        }), 500

@app.route('/conversation', methods=['GET'])
def get_conversation():
    """Get current conversation history"""
    if bot is None:
        return jsonify({
            "error": "Bot not initialized"
        }), 503
    
    try:
        conversation = []
        for role, message in bot.conversation:
            conversation.append({
                "role": role,
                "message": message,
                "timestamp": int(time.time())  # In real implementation, store actual timestamps
            })
        
        return jsonify({
            "success": True,
            "conversation": conversation,
            "length": len(bot.conversation),
            "max_length": 20,  # From the bot's conversation limit
            "timestamp": int(time.time())
        })
        
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        return jsonify({
            "error": f"Failed to get conversation: {str(e)}"
        }), 500

@app.route('/init', methods=['POST'])
def initialize():
    """Initialize or reinitialize the bot with a different JSON file"""
    try:
        data = request.get_json()
        json_file_path = data.get('json_file_path') if data else None
        
        logger.info(f"Reinitializing bot with file: {json_file_path or 'default'}")
        success = initialize_bot(json_file_path)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Bot initialized successfully",
                "tracks_loaded": len(bot.tracks_data),
                "bot_name": bot.bot_name,
                "timestamp": int(time.time())
            })
        else:
            return jsonify({
                "error": "Failed to initialize bot. Check server logs for details."
            }), 500
            
    except Exception as e:
        logger.error(f"Error initializing bot: {e}")
        return jsonify({
            "error": f"Initialization failed: {str(e)}"
        }), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "error": "Endpoint not found",
        "message": "The requested endpoint does not exist",
        "available_endpoints": {
            "GET /": "API information",
            "GET /health": "Server health check",
            "POST /chat": "Send messages to MIRA",
            "POST /reset": "Reset conversation history",
            "GET /stats": "Get track statistics",
            "GET /conversation": "Get conversation history",
            "POST /init": "Reinitialize bot"
        }
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors"""
    return jsonify({
        "error": "Method not allowed",
        "message": "The HTTP method is not allowed for this endpoint"
    }), 405

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "error": "Internal server error",
        "message": "Something went wrong on the server"
    }), 500

if __name__ == '__main__':
    print("MIRA Flask Server Initializing...")
    print("=" * 50)
    
    # Get JSON file path from command line argument or use default
    json_file = None
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        print(f"Using custom JSON file: {json_file}")
    else:
        print(f"Using default JSON file")
    
    # Initialize bot
    print("Initializing MIRA AI...")
    if initialize_bot(json_file):
        # print("✅ MIRA bot initialized successfully!")
        # print(f"📊 {bot.get_stats()}")
        # print("\n🌐 Server starting...")
        # print("📍 Server URL: http://localhost:5000")
        # print("\nAvailable endpoints:")
        # print("  • GET  /               - API information")
        # print("  • GET  /health         - Check server health")
        # print("  • POST /chat           - Send messages to MIRA (structured)")
        # print("  • POST /chat/formatted - Get beautifully formatted responses")
        # print("  • POST /tracks/search  - Search tracks in database")
        # print("  • POST /reset          - Reset conversation")
        # print("  • GET  /stats          - Get track statistics")
        # print("  • GET  /conversation   - Get conversation history")
        # print("  • POST /init           - Reinitialize bot")
        # print("\n📝 Example curl command:")
        # print("curl -X POST http://localhost:5000/chat \\")
        # print("  -H 'Content-Type: application/json' \\")
        # print("  -d '{\"message\": \"I need music for my fitness video\"}'")
        # print("=" * 50)/
        print("sucessful")
        
        # Start Flask server
        app.run(
            host='0.0.0.0',  # Allow external connections
            port=5000,       # Default port
            debug=True       # Enable debug mode
        )
    else:
        print("❌ Failed to initialize MIRA bot.")
        print("💡 Please check:")
        print("   • JSON file exists and is valid")
        print("   • openai_utils.py is configured correctly")
        print("   • .env file contains OPENAI_API_KEY")
        sys.exit(1)