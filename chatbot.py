import json
import time
from openai_utils import get_completion
from mylogger import logger

class MiraMusicRecommendationBot:
    def __init__(self, json_file_path: str, bot_name="MIRA - Hoopr Music AI"):
        self.bot_name = bot_name
        self.conversation = []
        self.tracks_data = self._load_tracks_from_json(json_file_path)
        
        # Updated MIRA system prompt for recommendations
        self.recommendation_prompt = """You are MIRA - Copyright Safe Music Recommender, owned by Hoopr.

RECOMMENDATION FORMAT (MUST BE FROM UPLOADED FILES):

🎵 Track: [TRACK_NAME] - [Hoopr Smash Link](https://hooprsmash.com/tracks/[name_slug]/[trackCode])
Why: [Detailed reasoning for why this track fits the request]
ROI impact:
| Metric | Expected Performance |
|--------|---------------------|
| Engagement Rate | [Specific analysis] |
| Watch Time | [Specific analysis] |
| CTR | [Specific analysis] |
Audience: [Detailed demographic description]
Reels Count: [Reels Count]([instagram_audio_link]) (Estimated [X]M views)
Hoopr Smash Link: https://hooprsmash.com/tracks/[name_slug]/[trackCode]

IMPORTANT RULES:
* Always recommend exactly 3 songs from uploaded track files
* Use trackCode and name_slug from uploaded files to build URL: https://hooprsmash.com/tracks/{name_slug}/{trackCode}
* Make brand-appropriate recommendations (don't recommend devotional songs for alcohol brands)
* Provide detailed ROI analysis with engagement metrics
* Dont answer anything other than music related questions if asked reply with "this is not related to hoopr or music"
* Include estimated reel counts and audience demographics
* Add context intro explaining why these picks work for the request
* End with a helpful follow-up question
* DON'T use web search or placeholder links
* Verify links match the track names"""

        # Conversational system prompt
        self.conversation_prompt = """You are MIRA - Copyright Safe Music Recommender from Hoopr.

Be friendly, helpful, and conversational. Answer questions about Hoopr, music licensing, or chat casually. 
Do NOT provide music recommendations unless specifically asked for songs/tracks/music.

Keep responses short, witty, and engaging. You can be a bit sarcastic but always helpful."""

        logger.info(f"MIRA initialized with {len(self.tracks_data)} tracks from JSON")

    def _load_tracks_from_json(self, json_file_path: str) -> list:
        """Load tracks from JSON file"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

            # Handle different JSON structures
            if isinstance(json_data, list):
                tracks = json_data
            elif isinstance(json_data, dict):
                tracks = json_data.get('tracks', json_data.get('data', []))
                if not tracks and 'results' in json_data:
                    tracks = json_data['results']
            else:
                logger.error("Invalid JSON structure")
                return []

            # Normalize track data structure
            normalized_tracks = []
            for track in tracks:
                normalized_track = {
                    'trackCode': str(track.get('trackCode', track.get('id', track.get('code', '')))),
                    'name': str(track.get('name', track.get('title', track.get('track_name', '')))),
                    'bpm': str(track.get('bpm', track.get('tempo', ''))),
                    'songKey': str(track.get('songKey', track.get('key', track.get('music_key', '')))),
                    'releaseDate': str(track.get('releaseDate', track.get('release_date', ''))),
                    'releaseYear': str(track.get('releaseYear', track.get('release_year', track.get('year', '')))),
                    'hasVocals': str(track.get('hasVocals', track.get('has_vocals', track.get('vocals', '')))),
                    'name_slug': str(track.get('name_slug', track.get('slug', track.get('url_slug', '')))),
                    'isExplicit': str(track.get('isExplicit', track.get('is_explicit', track.get('explicit', '')))),
                    'displayTags': str(track.get('displayTags', track.get('tags', track.get('genres', track.get('categories', '')))))
                }
                normalized_tracks.append(normalized_track)

            logger.info(f"Successfully loaded {len(normalized_tracks)} tracks from JSON")
            return normalized_tracks

        except FileNotFoundError:
            logger.error(f"JSON file not found: {json_file_path}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format in {json_file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading JSON file {json_file_path}: {e}")
            return []

    def _detect_recommendation_intent(self, user_message: str) -> bool:
        """Detect if user is asking for music recommendations"""
        music_keywords = [
            'recommend', 'suggestion', 'music', 'song', 'track', 'audio',
            'reel', 'video', 'background', 'instrumental', 'vocal',
            'upbeat', 'chill', 'energetic', 'mood', 'vibe', 'genre',
            'license', 'copyright', 'commercial', 'brand', 'campaign',
            'ad', 'advertisement', 'content', 'youtube', 'instagram',
            'tiktok', 'social media', 'beats', 'sound', 'playlist',
            'give me', 'need', 'want', 'looking for', 'find'
        ]
        
        user_lower = user_message.lower()
        return any(keyword in user_lower for keyword in music_keywords)

    def _get_relevant_tracks(self, user_message: str, limit: int = 15) -> list:
        """Find tracks relevant to user message with better scoring"""
        keywords = user_message.lower().split()
        relevant_tracks = []

        for track in self.tracks_data:
            track_text = f"{track['name']} {track['displayTags']} {track.get('bpm', '')}".lower()
            
            # Enhanced scoring system
            score = 0
            for keyword in keywords:
                if keyword in track_text:
                    # Higher score for exact matches in name
                    if keyword in track['name'].lower():
                        score += 3
                    # Medium score for tags
                    elif keyword in track['displayTags'].lower():
                        score += 2
                    else:
                        score += 1

            if score > 0:
                relevant_tracks.append((track, score))

        # Sort by relevance and return top matches
        relevant_tracks.sort(key=lambda x: x[1], reverse=True)
        return [track for track, _ in relevant_tracks[:limit]]

    def _build_tracks_context(self, tracks: list) -> str:
        """Build context string from track data"""
        if not tracks:
            tracks = self.tracks_data[:15]  # Default to first 15

        context = "AVAILABLE TRACKS:\n"
        for track in tracks:
            context += f"trackCode: {track['trackCode']}, name: {track['name']}, "
            context += f"bpm: {track['bpm']}, hasVocals: {track['hasVocals']}, "
            context += f"name_slug: {track['name_slug']}, displayTags: {track['displayTags']}\n"
        
        return context

    def chat(self, user_message: str) -> str:
        """Send message and get MIRA response"""
        logger.info(f"User message: {user_message}")
        
        # Check if this is a recommendation request
        needs_recommendation = self._detect_recommendation_intent(user_message)
        
        # Build conversation context
        conversation_context = self._build_conversation_context()
        
        if needs_recommendation:
            # Get relevant tracks for recommendations
            relevant_tracks = self._get_relevant_tracks(user_message)
            tracks_context = self._build_tracks_context(relevant_tracks)
            
            prompt = f"""{self.recommendation_prompt}

{tracks_context}

CONVERSATION HISTORY:
{conversation_context}

USER REQUEST: {user_message}

Provide a brief intro explaining why these tracks work for the request, then exactly 3 track recommendations using the specified format with detailed ROI analysis, audience demographics, and proper Hoopr Smash links. End with a helpful follow-up question."""
        
        else:
            # Conversational response without recommendations
            prompt = f"""{self.conversation_prompt}

CONVERSATION HISTORY:
{conversation_context}

USER MESSAGE: {user_message}

Respond naturally and conversationally. Keep it brief and engaging."""
        
        try:
            response = get_completion(prompt, is_json=False)
            
            # Store conversation
            self.conversation.append(("User", user_message))
            self.conversation.append(("MIRA", response))
            
            # Keep conversation manageable
            if len(self.conversation) > 20:
                self.conversation = self.conversation[-20:]
                
            logger.info(f"MIRA response generated successfully")
            return response
            
        except Exception as e:
            logger.error(f"MIRA chat error: {e}")
            return "I'm having trouble right now. Please try again!"

    def _build_conversation_context(self) -> str:
        """Build conversation history"""
        if not self.conversation:
            return "This is the start of our conversation."

        context_lines = []
        for role, message in self.conversation[-8:]:  # Last 4 exchanges
            context_lines.append(f"{role}: {message}")
        
        return "\n".join(context_lines)

    def reset(self):
        """Clear conversation history"""
        self.conversation = []
        logger.info("MIRA conversation reset")
        print("🎵 MIRA: Let's start fresh! What can I help you with?")

    def get_stats(self):
        """Get statistics about loaded tracks"""
        if not self.tracks_data:
            return "No tracks loaded"

        total = len(self.tracks_data)
        with_vocals = sum(1 for track in self.tracks_data if track.get('hasVocals', '').lower() in ['true', '1', 'yes'])
        explicit = sum(1 for track in self.tracks_data if track.get('isExplicit', '').lower() in ['true', '1', 'yes'])
        
        return f"📊 Stats: {total} tracks loaded | {with_vocals} with vocals | {explicit} explicit"
