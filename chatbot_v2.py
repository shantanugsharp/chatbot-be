import sqlite3
import time
from openai_utils import get_completion
from mylogger import logger
from prompts import RECOMMENDATION_PROMPT, CONVERSATION_PROMPT, build_recommendation_prompt, build_conversation_prompt

class MiraMusicRecommendationBotV2:
    def __init__(self, db_path: str = "recommendation.db", bot_name="MIRA - Hoopr Music AI"):
        self.bot_name = bot_name
        self.conversation = []
        self.db_path = db_path
        self.tracks_data = []
        
        # Initialize database connection and load tracks
        self._initialize_database()
        
        # Load prompts from prompts.py
        self.recommendation_prompt = RECOMMENDATION_PROMPT
        self.conversation_prompt = CONVERSATION_PROMPT

        logger.info(f"MIRA V2 initialized with {len(self.tracks_data)} tracks from database")

    def _initialize_database(self):
        """Initialize database connection and verify audio_tags table exists"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if audio_tags table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audio_tags'")
            if not cursor.fetchone():
                logger.warning(f"audio_tags table not found in {self.db_path}. Creating table structure...")
                # Create audio_tags table if it doesn't exist (with common fields)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audio_tags (
                        id INTEGER PRIMARY KEY,
                        trackCode TEXT,
                        name TEXT,
                        name_slug TEXT,
                        bpm TEXT,
                        songKey TEXT,
                        hasVocals TEXT,
                        isExplicit TEXT,
                        displayTags TEXT,
                        releaseDate TEXT,
                        releaseYear TEXT,
                        search_blob TEXT,
                        tags_json TEXT
                    )
                """)
                conn.commit()
                logger.info("Created audio_tags table structure")
            else:
                # Get table schema
                cursor.execute("PRAGMA table_info(audio_tags)")
                columns = [col[1] for col in cursor.fetchall()]
                logger.info(f"Found audio_tags table with columns: {columns}")
            
            conn.close()
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
        except Exception as e:
            logger.error(f"Error initializing database {self.db_path}: {e}")

    def _load_tracks_from_db(self) -> list:
        """Load tracks from audio_tags table in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            # Query audio_tags table
            cursor.execute("SELECT * FROM audio_tags")
            rows = cursor.fetchall()
            
            # Normalize track data structure
            normalized_tracks = []
            for row in rows:
                # Convert row to dict, handling different column names
                track = dict(row)
                
                # Map actual database columns to normalized structure
                # Database uses: track-title, name-slug, Track bpm, track-songKey, VOCALS, Explicit, display-tags, keywords
                normalized_track = {
                    'trackCode': str(track.get('unique_code', track.get('trackCode', track.get('track_code', track.get('id', ''))))),
                    'name': str(track.get('track-title', track.get('name', track.get('title', track.get('track_name', ''))))),
                    'bpm': str(track.get('Track bpm', track.get('bpm', track.get('tempo', '')))),
                    'songKey': str(track.get('track-songKey', track.get('songKey', track.get('song_key', track.get('key', track.get('key_sig', '')))))),
                    'releaseDate': str(track.get('ReleaseDate', track.get('releaseDate', track.get('release_date', '')))),
                    'releaseYear': str(track.get('ReleaseYear', track.get('releaseYear', track.get('release_year', track.get('year', ''))))),
                    'hasVocals': str(track.get('VOCALS', track.get('hasVocals', track.get('has_vocals', track.get('vocals', ''))))),
                    'name_slug': str(track.get('name-slug', track.get('name_slug', track.get('slug', track.get('url_slug', ''))))),
                    'isExplicit': str(track.get('Explicit', track.get('isExplicit', track.get('is_explicit', track.get('explicit', ''))))),
                    'displayTags': str(track.get('display-tags', track.get('displayTags', track.get('tags', track.get('genres', track.get('categories', '')))))),
                    'search_blob': str(track.get('keywords', track.get('search_blob', ''))) or str(track.get('display-tags', '')) or ''
                }
                
                # Combine multiple searchable fields for better matching
                search_fields = [
                    track.get('keywords', ''),
                    track.get('display-tags', ''),
                    track.get('filter-mood', ''),
                    track.get('filter-genre1', ''),
                    track.get('subFilter-subGenre1', ''),
                    track.get('Use Cases', ''),
                    track.get('filter-instrument', '')
                ]
                normalized_track['search_blob'] = ' '.join([str(f) for f in search_fields if f])
                
                # If name_slug is empty, generate from name
                if not normalized_track['name_slug'] or normalized_track['name_slug'].lower() == 'none':
                    if normalized_track['name'] and normalized_track['name'].lower() != 'none':
                        normalized_track['name_slug'] = normalized_track['name'].lower().replace(' ', '-').replace('_', '-')
                    else:
                        normalized_track['name_slug'] = f"track-{normalized_track['trackCode']}"
                
                # Use unique_code as trackCode if available
                if not normalized_track['trackCode'] or normalized_track['trackCode'] == 'None':
                    normalized_track['trackCode'] = str(track.get('unique_code', track.get('id', '')))
                
                normalized_tracks.append(normalized_track)
            
            conn.close()
            logger.info(f"Successfully loaded {len(normalized_tracks)} tracks from database")
            return normalized_tracks
            
        except sqlite3.Error as e:
            logger.error(f"Database error loading tracks: {e}")
            return []
        except Exception as e:
            logger.error(f"Error loading tracks from database {self.db_path}: {e}")
            return []

    def _query_relevant_tracks(self, user_message: str, limit: int = 15) -> list:
        """Query database for tracks relevant to user message using SQL"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Extract keywords from user message
            keywords = user_message.lower().split()
            
            # Build SQL query with LIKE conditions for keyword matching
            # Search in actual database columns: track-title, display-tags, keywords, filter-mood, etc.
            conditions = []
            params = []
            
            for keyword in keywords:
                if len(keyword) > 2:  # Only search for words longer than 2 characters
                    conditions.append("""
                        (LOWER([track-title]) LIKE ? OR 
                         LOWER([display-tags]) LIKE ? OR 
                         LOWER([keywords]) LIKE ? OR
                         LOWER(COALESCE([filter-mood], '')) LIKE ? OR
                         LOWER(COALESCE([filter-genre1], '')) LIKE ? OR
                         LOWER(COALESCE([subFilter-subGenre1], '')) LIKE ? OR
                         LOWER(COALESCE([Use Cases], '')) LIKE ?)
                    """)
                    keyword_pattern = f"%{keyword}%"
                    params.extend([keyword_pattern] * 7)
            
            if not conditions:
                # If no valid keywords, return random tracks (with DISTINCT to avoid duplicates)
                query = "SELECT DISTINCT * FROM audio_tags ORDER BY RANDOM() LIMIT ?"
                cursor.execute(query, (limit,))
            else:
                # Build full query with scoring - prioritize matches in title, then tags, then keywords
                # Use DISTINCT to ensure no duplicate tracks
                query = f"""
                    SELECT DISTINCT *, 
                        (CASE WHEN LOWER([track-title]) LIKE ? THEN 5 ELSE 0 END) +
                        (CASE WHEN LOWER([display-tags]) LIKE ? THEN 3 ELSE 0 END) +
                        (CASE WHEN LOWER([keywords]) LIKE ? THEN 2 ELSE 0 END) +
                        (CASE WHEN LOWER(COALESCE([filter-mood], '')) LIKE ? THEN 2 ELSE 0 END) +
                        (CASE WHEN LOWER(COALESCE([Use Cases], '')) LIKE ? THEN 1 ELSE 0 END) as score
                    FROM audio_tags
                    WHERE {' OR '.join(conditions)}
                    ORDER BY score DESC, [track-title]
                    LIMIT ?
                """
                # Add primary keyword for scoring (first keyword)
                primary_keyword = f"%{keywords[0]}%" if keywords else "%"
                params = [primary_keyword, primary_keyword, primary_keyword, primary_keyword, primary_keyword] + params + [limit]
                cursor.execute(query, params)
            
            rows = cursor.fetchall()
            conn.close()
            
            # Normalize results using same mapping as _load_tracks_from_db
            # Use a set to track seen trackCodes to prevent duplicates
            seen_track_codes = set()
            normalized_tracks = []
            for row in rows:
                track = dict(row)
                
                # Map actual database columns to normalized structure
                normalized_track = {
                    'trackCode': str(track.get('unique_code', track.get('trackCode', track.get('track_code', track.get('id', ''))))),
                    'name': str(track.get('track-title', track.get('name', track.get('title', track.get('track_name', ''))))),
                    'bpm': str(track.get('Track bpm', track.get('bpm', track.get('tempo', '')))),
                    'songKey': str(track.get('track-songKey', track.get('songKey', track.get('song_key', track.get('key', track.get('key_sig', '')))))),
                    'releaseDate': str(track.get('ReleaseDate', track.get('releaseDate', track.get('release_date', '')))),
                    'releaseYear': str(track.get('ReleaseYear', track.get('releaseYear', track.get('release_year', track.get('year', ''))))),
                    'hasVocals': str(track.get('VOCALS', track.get('hasVocals', track.get('has_vocals', track.get('vocals', ''))))),
                    'name_slug': str(track.get('name-slug', track.get('name_slug', track.get('slug', track.get('url_slug', ''))))),
                    'isExplicit': str(track.get('Explicit', track.get('isExplicit', track.get('is_explicit', track.get('explicit', ''))))),
                    'displayTags': str(track.get('display-tags', track.get('displayTags', track.get('tags', track.get('genres', track.get('categories', '')))))),
                    'search_blob': str(track.get('keywords', track.get('search_blob', ''))) or str(track.get('display-tags', '')) or ''
                }
                
                # Combine multiple searchable fields
                search_fields = [
                    track.get('keywords', ''),
                    track.get('display-tags', ''),
                    track.get('filter-mood', ''),
                    track.get('filter-genre1', ''),
                    track.get('subFilter-subGenre1', ''),
                    track.get('Use Cases', ''),
                    track.get('filter-instrument', '')
                ]
                normalized_track['search_blob'] = ' '.join([str(f) for f in search_fields if f])
                
                # If name_slug is empty, generate from name
                if not normalized_track['name_slug'] or normalized_track['name_slug'].lower() == 'none':
                    if normalized_track['name'] and normalized_track['name'].lower() != 'none':
                        normalized_track['name_slug'] = normalized_track['name'].lower().replace(' ', '-').replace('_', '-')
                    else:
                        normalized_track['name_slug'] = f"track-{normalized_track['trackCode']}"
                
                # Use unique_code as trackCode if available
                if not normalized_track['trackCode'] or normalized_track['trackCode'] == 'None':
                    normalized_track['trackCode'] = str(track.get('unique_code', track.get('id', '')))
                
                # Deduplicate by trackCode - only add if we haven't seen this trackCode before
                track_code_key = normalized_track['trackCode'].strip().lower()
                if track_code_key and track_code_key not in seen_track_codes and track_code_key != 'none':
                    seen_track_codes.add(track_code_key)
                    normalized_tracks.append(normalized_track)
            
            logger.info(f"Found {len(normalized_tracks)} unique relevant tracks from database")
            return normalized_tracks
            
        except sqlite3.Error as e:
            logger.error(f"Database error querying tracks: {e}")
            return []
        except Exception as e:
            logger.error(f"Error querying tracks from database: {e}")
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
        """Find tracks relevant to user message using database queries"""
        # Use database query method
        return self._query_relevant_tracks(user_message, limit)

    def _build_tracks_context(self, tracks: list) -> str:
        """Build context string from track data, ensuring no duplicates"""
        if not tracks:
            # Load default tracks from database if no matches
            tracks = self._load_tracks_from_db()[:15]

        # Additional deduplication by trackCode to ensure uniqueness
        seen_track_codes = set()
        unique_tracks = []
        for track in tracks:
            track_code = str(track.get('trackCode', '')).strip().lower()
            if track_code and track_code not in seen_track_codes and track_code != 'none':
                seen_track_codes.add(track_code)
                unique_tracks.append(track)
        
        context = "AVAILABLE TRACKS (UNIQUE - DO NOT REPEAT ANY TRACK):\n"
        for track in unique_tracks:
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
            # Get relevant tracks for recommendations from database
            relevant_tracks = self._get_relevant_tracks(user_message)
            tracks_context = self._build_tracks_context(relevant_tracks)
            
            # Build recommendation prompt using helper function
            prompt = build_recommendation_prompt(
                self.recommendation_prompt,
                tracks_context,
                conversation_context,
                user_message
            )
        
        else:
            # Conversational response without recommendations
            # Build conversation prompt using helper function
            prompt = build_conversation_prompt(
                self.conversation_prompt,
                conversation_context,
                user_message
            )
        
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
        print(" MIRA: Let's start fresh! What can I help you with?")

    def get_stats(self):
        """Get statistics about loaded tracks from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM audio_tags")
            total = cursor.fetchone()[0]
            
            # Get tracks with vocals (using actual column name VOCALS)
            cursor.execute("""
                SELECT COUNT(*) FROM audio_tags 
                WHERE LOWER([VOCALS]) IN ('yes', 'y', 'true', '1', 'has vocals', 'with vocals')
            """)
            with_vocals = cursor.fetchone()[0]
            
            # Get explicit tracks (using actual column name Explicit)
            cursor.execute("""
                SELECT COUNT(*) FROM audio_tags 
                WHERE LOWER([Explicit]) IN ('yes', 'y', 'true', '1')
            """)
            explicit = cursor.fetchone()[0]
            
            conn.close()
            
            return f"📊 Stats: {total} tracks loaded | {with_vocals} with vocals | {explicit} explicit"
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return "Error retrieving statistics"

    def refresh_tracks(self):
        """Reload tracks from database (useful if database is updated)"""
        self.tracks_data = self._load_tracks_from_db()
        logger.info(f"Refreshed tracks: {len(self.tracks_data)} tracks loaded")

