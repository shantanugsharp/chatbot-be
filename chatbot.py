import json
import sqlite3
import re
from typing import List, Dict, Any, Optional, Tuple
from openai_utils import get_completion
from mylogger import logger
from prompts import RECOMMENDATION_PROMPT, CONVERSATION_PROMPT


def _slugify(s: str) -> str:
    """Convert string to URL-safe slug"""
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def _as_list(x: Any) -> List[str]:
    """Convert various types to string list"""
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i) for i in x]
    if isinstance(x, dict):
        out = []
        for k, v in x.items():
            out.append(str(k))
            if isinstance(v, list):
                out += [str(i) for i in v]
            else:
                out.append(str(v))
        return out
    return [str(x)]


class HooprMusicRecommender:
    """
    Commercial-grade music recommendation chatbot for Hoopr
    
    Features:
    - Intelligent intent detection
    - Database-powered recommendations
    - Professional output formatting
    - Conversation memory
    - Track metadata enrichment
    """
    
    def __init__(
        self, 
        db_path: str,
        bot_name: str = "MIRA - Hoopr Music Intelligence"
    ):
        """
        Initialize the commercial chatbot
        
        Args:
            db_path: Path to audio_tagging.db SQLite database
            bot_name: Bot display name
        """
        self.bot_name = bot_name
        self.conversation = []
        self.db_path = db_path
        
        # Load tracks from database
        self.tracks_data = self._load_tracks_from_db(db_path)
        
        # Build searchable index
        self._build_search_text()
        
        # System prompts
        self.recommendation_prompt = RECOMMENDATION_PROMPT
        self.conversation_prompt = CONVERSATION_PROMPT
        
        logger.info(f"🎵 {self.bot_name} initialized with {len(self.tracks_data)} tracks")

    def _load_tracks_from_db(self, db_path: str) -> List[Dict[str, Any]]:
        """Load tracks from SQLite database with full metadata"""
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            
            rows = cur.execute(
                """
                SELECT 
                    track_code,
                    mp3_url,
                    analysis_result,
                    language,
                    bpm,
                    edit_pacing,
                    mood,
                    genre,
                    themes,
                    instruments_json,
                    brand_archetype_json,
                    category_wise_tags_json,
                    production_style_json,
                    lyrics_tags_json,
                    has_vocals,
                    is_explicit
                FROM audio_analysis
                """
            ).fetchall()
            conn.close()

            def infer_bpm(analysis: Dict) -> Optional[int]:
                v = analysis.get("Approximate BPM")
                try:
                    return int(float(v))
                except Exception:
                    return None

            def infer_has_vocals(analysis: Dict) -> bool:
                lyr = analysis.get("Lyrics In Song") or analysis.get("Full Lyrics In Song") or ""
                text = str(lyr).strip().lower()
                if not text:
                    return False
                if "instrumental" in text and "vocal" not in text:
                    return False
                return True

            def infer_is_explicit(analysis: Dict) -> bool:
                comp = analysis.get("compliance") or []
                if isinstance(comp, list):
                    return not any("no_explicit" in str(x).lower() for x in comp)
                return False

            normalized_tracks = []
            for row in rows:
                # Row unpack with backward compatibility
                if len(row) == 3:
                    track_code, mp3_url, analysis_json = row
                    lang = bpm = edit_pacing = mood = genre = themes = None
                    instruments_json = brand_archetype_json = category_wise_tags_json = None
                    production_style_json = lyrics_tags_json = None
                    has_vocals = is_explicit = None
                else:
                    (
                        track_code,
                        mp3_url,
                        analysis_json,
                        lang,
                        bpm,
                        edit_pacing,
                        mood,
                        genre,
                        themes,
                        instruments_json,
                        brand_archetype_json,
                        category_wise_tags_json,
                        production_style_json,
                        lyrics_tags_json,
                        has_vocals,
                        is_explicit
                    ) = row
                try:
                    analysis = json.loads(analysis_json or "{}")
                except Exception:
                    analysis = {}

                # Get track name using hoopr_data or fallback
                track_name = self._get_track_name(track_code)
                name_slug = f"track-{track_code}"  # Simple slug generation

                # Parse JSON text fields safely
                def parse_json_text(val):
                    if val is None:
                        return None
                    try:
                        return json.loads(val)
                    except Exception:
                        return val

                track = {
                    'trackCode': str(track_code),
                    'name': track_name,
                    'name_slug': name_slug,
                    'mp3_url': mp3_url,
                    'bpm': bpm if bpm else infer_bpm(analysis),
                    'hasVocals': bool(has_vocals) if has_vocals is not None else infer_has_vocals(analysis),
                    'isExplicit': bool(is_explicit) if is_explicit is not None else infer_is_explicit(analysis),
                    'language': lang if lang else analysis.get("Language of song"),
                    'instruments': parse_json_text(instruments_json) or analysis.get("Instruments Used") or [],
                    'brand_archetype': parse_json_text(brand_archetype_json) or analysis.get("brand archetype") or [],
                    'category_wise_tags': parse_json_text(category_wise_tags_json) or analysis.get("category wise tags") or {},
                    'production_style': parse_json_text(production_style_json) or analysis.get("production style") or [],
                    'lyrics_tags': parse_json_text(lyrics_tags_json) or analysis.get("Tags based on Lyrics") or [],
                    'edit_pacing': edit_pacing if edit_pacing else analysis.get("edit_pacing"),
                    'mood': mood if mood else (analysis.get("Mood") or analysis.get("mood")),
                    'genre': genre if genre else (analysis.get("Genre") or analysis.get("genre")),
                    'themes': themes if themes else (analysis.get("Themes") or analysis.get("themes")),
                    'displayTags': '',  # Will build this from other fields
                    '_analysis': analysis
                }
                
                # Build displayTags from structured data
                tags = []
                tags += _as_list(track.get('language'))
                tags += _as_list(track.get('instruments'))
                tags += _as_list(track.get('brand_archetype'))
                tags += _as_list(track.get('production_style'))
                tags += _as_list(track.get('lyrics_tags'))
                tags += _as_list(track.get('category_wise_tags'))
                tags += _as_list(track.get('mood'))
                tags += _as_list(track.get('genre'))
                tags += _as_list(track.get('themes'))
                track['displayTags'] = ', '.join(tags)
                
                normalized_tracks.append(track)

            logger.info(f"✅ Successfully loaded {len(normalized_tracks)} tracks from database")
            return normalized_tracks

        except sqlite3.Error as e:
            logger.error(f"❌ Database error loading {db_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Error loading database {db_path}: {e}")
            return []

    def _get_track_name(self, track_code: str) -> str:
        """
        Get track name from hoopr_data module or generate fallback
        
        Args:
            track_code: Track code (can be numeric or alphanumeric)
            
        Returns:
            Track name or fallback
        """
        # Only try hoopr_data lookup for numeric track codes
        # Alphanumeric track codes (like 'DHbTxI7S_av') are not in hoopr_data
        if track_code and track_code.strip().isdigit():
            try:
                import hoopr_data
                name = hoopr_data.get_track_name(track_code)
                if name:
                    return name
            except ImportError:
                # hoopr_data module not available - use fallback silently
                pass
            except (ValueError, KeyError, TypeError) as e:
                # Expected errors for track codes not in hoopr_data - handle silently
                pass
            except Exception as e:
                # Only log unexpected errors
                logger.debug(f"Unexpected error getting track name for {track_code}: {e}")
        
        # Fallback: generate descriptive name
        return f"Track {track_code}"

    def _build_search_text(self) -> None:
        """Build searchable text for each track from all available metadata"""
        for track in self.tracks_data:
            bag = []
            
            # Add all metadata fields to search text
            bag += _as_list(track.get('language'))
            bag += _as_list(track.get('instruments'))
            bag += _as_list(track.get('brand_archetype'))
            bag += _as_list(track.get('production_style'))
            bag += _as_list(track.get('lyrics_tags'))
            bag += _as_list(track.get('category_wise_tags'))
            bag += _as_list(track.get('mood'))
            bag += _as_list(track.get('genre'))
            bag += _as_list(track.get('themes'))
            
            if track.get('edit_pacing'):
                bag.append(str(track['edit_pacing']))
            
            if track.get('bpm'):
                bag.append(f"bpm_{track['bpm']}")
                # Add BPM range tags
                bpm = track['bpm']
                if bpm < 90:
                    bag.extend(['slow', 'chill', 'relaxed'])
                elif bpm < 120:
                    bag.extend(['moderate', 'mid-tempo'])
                else:
                    bag.extend(['fast', 'energetic', 'upbeat', 'high-energy'])
            
            if track.get('hasVocals'):
                bag.extend(['vocals', 'vocal', 'singing', 'sung'])
            else:
                bag.extend(['instrumental', 'no-vocals', 'background'])
            
            if track.get('isExplicit'):
                bag.append('explicit')
            else:
                bag.extend(['clean', 'safe', 'family-friendly'])
            
            if track.get('name'):
                bag.append(track['name'])
            
            if track.get('displayTags'):
                bag.append(track['displayTags'])
            
            track['search_text'] = ' '.join(map(str, bag)).lower()

    def _detect_recommendation_intent(self, user_message: str) -> bool:
        """
        Detect if user is asking for music recommendations
        
        Args:
            user_message: User's message
            
        Returns:
            True if recommendation request detected
        """
        # Core music keywords
        music_keywords = {
            'music', 'song', 'track', 'audio', 'soundtrack',
            'reel', 'video', 'content', 'background'
        }
        
        # Action keywords
        action_keywords = {
            'recommend', 'suggest', 'need', 'want', 'looking for',
            'find', 'give me', 'show me', 'help me find'
        }
        
        # Context keywords
        context_keywords = {
            'brand', 'campaign', 'ad', 'advertisement', 'commercial',
            'instagram', 'youtube', 'tiktok', 'social media',
            'project', 'video', 'film', 'podcast'
        }
        
        user_lower = user_message.lower()
        
        # Check for music + action combination
        has_music = any(keyword in user_lower for keyword in music_keywords)
        has_action = any(keyword in user_lower for keyword in action_keywords)
        has_context = any(keyword in user_lower for keyword in context_keywords)
        
        # Need either (music + action) or (action + context)
        return (has_music and has_action) or (has_action and has_context)

    def _tokenize(self, query: str) -> List[str]:
        """Tokenize query into searchable terms"""
        query = (query or "").lower()
        query = re.sub(r"[^a-z0-9\s\-\_#]+", " ", query)
        parts = re.split(r"\s+", query.strip())
        return [p for p in parts if p and len(p) > 2]

    def _parse_query_constraints(self, query: str) -> Dict[str, Any]:
        """Extract structured constraints from a free-text query"""
        q = (query or "").lower()
        tokens = set(self._tokenize(q))

        constraints: Dict[str, Any] = {
            'wantsVocals': None,
            'allowExplicit': None,
            'bpmRange': None,  # (min,max)
            'moods': set(),
            'genres': set(),
            'languages': set(),
        }

        # Vocals
        if any(k in q for k in ["no vocals", "instrumental", "background only"]):
            constraints['wantsVocals'] = False
        elif any(k in q for k in ["with vocals", "vocal", "sung", "lyrics"]):
            constraints['wantsVocals'] = True

        # Explicit
        if any(k in q for k in ["clean only", "brand safe", "no explicit", "family friendly"]):
            constraints['allowExplicit'] = False
        elif "explicit ok" in q or "explicit okay" in q or "explicit allowed" in q:
            constraints['allowExplicit'] = True

        # Energy/BPM
        if any(k in tokens for k in ["slow", "chill", "relaxed", "calm", "mellow"]):
            constraints['bpmRange'] = (0, 95)
        elif any(k in tokens for k in ["moderate", "mid-tempo", "midtempo"]):
            constraints['bpmRange'] = (90, 120)
        elif any(k in tokens for k in ["fast", "energetic", "upbeat", "high-energy", "intense"]):
            constraints['bpmRange'] = (110, 999)

        # Simple mood/genre/language dictionary
        known_moods = {"happy", "sad", "romantic", "energetic", "epic", "calm", "chill", "uplifting", "dark"}
        known_genres = {"pop", "rock", "hiphop", "hip-hop", "electronic", "edm", "classical", "indie", "folk", "jazz"}
        known_languages = {"hindi", "english", "punjabi", "tamil", "telugu", "marathi", "bengali", "instrumental"}

        for t in tokens:
            if t in known_moods:
                constraints['moods'].add(t)
            if t in known_genres:
                constraints['genres'].add("hip-hop" if t == "hiphop" else t)
            if t in known_languages:
                constraints['languages'].add(t)

        return constraints

    def _score_track(self, query_tokens: List[str], track: Dict[str, Any], constraints: Optional[Dict[str, Any]] = None) -> float:
        """
        Score track relevance with advanced multi-factor analysis
        
        Args:
            query_tokens: Tokenized search query
            track: Track data
            
        Returns:
            Relevance score
        """
        score = 0.0
        search_text = track.get('search_text', '')
        
        # 1. Keyword matching with position weighting
        for token in query_tokens:
            if token in search_text:
                # Higher weight for name matches
                if token in track.get('name', '').lower():
                    score += 5.0
                # Medium weight for mood/genre
                elif token in str(track.get('mood', '')).lower():
                    score += 3.0
                elif token in str(track.get('genre', '')).lower():
                    score += 3.0
                # Standard weight for other matches
                else:
                    score += 1.5
        
        # 1b. Lyrics keyword boost (lightweight)
        analysis = track.get('_analysis') or {}
        lyrics_text = analysis.get("Full Lyrics In Song") or analysis.get("Lyrics In Song") or ""
        lyrics_text_lc = str(lyrics_text).lower()
        if lyrics_text_lc:
            for token in query_tokens:
                # avoid ultra-short tokens
                if len(token) >= 3 and token in lyrics_text_lc:
                    score += 2.5
                    # modest cap to avoid overpowering
                    break
        
        # 2. Vocal/Instrumental preference
        vocal_keywords = {'vocals', 'vocal', 'singing', 'sung', 'lyrics', 'voice'}
        instrumental_keywords = {'instrumental', 'no-vocals', 'background', 'ambient'}
        
        if any(tok in vocal_keywords for tok in query_tokens):
            score += 3.0 if track.get('hasVocals') else -2.0
        
        if any(tok in instrumental_keywords for tok in query_tokens):
            score += 3.0 if not track.get('hasVocals') else -2.0
        
        # 3. Explicit content handling
        if any(tok in ('explicit', 'uncensored') for tok in query_tokens):
            score += 1.5 if track.get('isExplicit') else -1.0
        
        if any(tok in ('clean', 'safe', 'family-friendly', 'brand-safe') for tok in query_tokens):
            score += 2.0 if not track.get('isExplicit') else -3.0

        # Apply parsed constraints
        if constraints:
            if constraints.get('wantsVocals') is True and not track.get('hasVocals'):
                score -= 4.0
            if constraints.get('wantsVocals') is False and track.get('hasVocals'):
                score -= 4.0

            allow_explicit = constraints.get('allowExplicit')
            if allow_explicit is False and track.get('isExplicit'):
                score -= 5.0
        
        # 4. BPM-based energy matching
        bpm = track.get('bpm')
        if bpm:
            energy_keywords = {
                'fast': (120, 999),
                'energetic': (120, 999),
                'upbeat': (110, 140),
                'high-energy': (130, 999),
                'intense': (140, 999),
                'slow': (0, 90),
                'chill': (0, 95),
                'relaxed': (0, 95),
                'calm': (0, 90),
                'mellow': (0, 95),
                'moderate': (90, 120),
                'mid-tempo': (95, 115)
            }
            
            for keyword, (min_bpm, max_bpm) in energy_keywords.items():
                if keyword in query_tokens and min_bpm <= bpm <= max_bpm:
                    score += 2.5

            # Constraint-based BPM
            if constraints and constraints.get('bpmRange'):
                bmin, bmax = constraints['bpmRange']
                if bmin <= bpm <= bmax:
                    score += 3.0
                else:
                    score -= 1.5
        
        # 5. Brand archetype matching
        brand_keywords = {
            'fitness': ['Hero', 'Explorer'],
            'luxury': ['Lover', 'Ruler'],
            'tech': ['Creator', 'Magician'],
            'sports': ['Hero', 'Challenger'],
            'fashion': ['Lover', 'Creator'],
            'food': ['Caregiver', 'Everyman'],
            'travel': ['Explorer', 'Creator']
        }
        
        track_archetypes = _as_list(track.get('brand_archetype', []))
        for keyword, archetypes in brand_keywords.items():
            if keyword in query_tokens:
                if any(arch in track_archetypes for arch in archetypes):
                    score += 4.0

        # Light matching for mood/genre/language constraints
        if constraints:
            if constraints.get('moods'):
                track_mood = str(track.get('mood', '')).lower()
                if any(m in track_mood for m in constraints['moods']):
                    score += 2.5
            if constraints.get('genres'):
                track_genre = str(track.get('genre', '')).lower()
                if any(g in track_genre for g in constraints['genres']):
                    score += 2.5
            if constraints.get('languages'):
                track_lang = str(track.get('language', '')).lower()
                if track_lang and track_lang in constraints['languages']:
                    score += 2.0
        
        return score

    def _get_relevant_tracks(self, user_message: str, limit: int = 40) -> List[Dict[str, Any]]:
        """
        Find tracks relevant to user message with advanced scoring
        
        Args:
            user_message: User's search query
            limit: Maximum number of tracks to return
            
        Returns:
            List of relevant tracks
        """
        tokens = self._tokenize(user_message)
        constraints = self._parse_query_constraints(user_message)
        relevant_tracks = []

        for track in self.tracks_data:
            score = self._score_track(tokens, track, constraints)
            if score > 0:
                relevant_tracks.append((track, score))

        # Sort by relevance and return top matches
        relevant_tracks.sort(key=lambda x: x[1], reverse=True)
        return [track for track, _ in relevant_tracks[:limit]]

    def _build_tracks_context(self, tracks: List[Dict[str, Any]]) -> str:
        """
        Build rich context string from track data for LLM
        
        Args:
            tracks: List of track dictionaries
            
        Returns:
            Formatted context string
        """
        if not tracks:
            tracks = self.tracks_data[:40]  # Default to first 40

        context_lines = ["AVAILABLE TRACKS (Select 3 most relevant):\n"]
        
        for track in tracks:
            line_parts = [
                f"trackCode: {track['trackCode']}",
                f"name: {track['name']}",
                f"bpm: {track.get('bpm', 'N/A')}",
                f"vocals: {'Yes' if track['hasVocals'] else 'No'}",
                f"explicit: {'Yes' if track['isExplicit'] else 'No'}"
            ]
            
            # Add rich metadata if available
            if track.get('mood'):
                line_parts.append(f"mood: {track['mood']}")
            
            if track.get('brand_archetype'):
                archetypes = _as_list(track['brand_archetype'])[:3]
                line_parts.append(f"archetypes: {', '.join(archetypes)}")
            
            if track.get('instruments'):
                instruments = _as_list(track['instruments'])[:5]
                line_parts.append(f"instruments: {', '.join(instruments)}")
            
            if track.get('genre'):
                line_parts.append(f"genre: {track['genre']}")
            
            context_lines.append(" | ".join(line_parts))
        
        return "\n".join(context_lines)

    def recommend(self, user_message: str, top_n: int = 3) -> str:
        """
        Generate music recommendations based on user request
        
        Args:
            user_message: User's recommendation request
            
        Returns:
            Formatted recommendation response
        """
        logger.info(f"🎯 Recommendation request: {user_message}")
        
        # Get relevant tracks
        relevant_tracks = self._get_relevant_tracks(user_message, limit=max(20, top_n * 10))
        
        if not relevant_tracks:
            return ("I couldn't find tracks matching your exact criteria in our database. "
                   "Could you describe your needs differently? For example, mention the mood, "
                   "genre, or type of content you're creating.")
        
        tracks_context = self._build_tracks_context(relevant_tracks)
        conversation_context = self._build_conversation_context()
        
        prompt = f"""{self.recommendation_prompt}

{tracks_context}

CONVERSATION HISTORY:
{conversation_context}

USER REQUEST: {user_message}

Provide a 2-3 sentence intro explaining your recommendation strategy, then exactly {top_n} track recommendations in the specified format. End with ONE helpful follow-up question."""
        
        try:
            response = get_completion(prompt, is_json=False)
            
            # Store conversation
            self.conversation.append(("User", user_message))
            self.conversation.append(("MIRA", response))
            
            # Keep conversation manageable
            if len(self.conversation) > 20:
                self.conversation = self.conversation[-20:]
                
            logger.info(f"✅ Recommendation generated successfully")
            return response
            
        except Exception as e:
            logger.error(f"❌ Recommendation error: {e}")
            return ("I'm experiencing technical difficulties generating recommendations. "
                   "Please try again in a moment.")

    def chat(self, user_message: str) -> str:
        """
        Main chat interface - routes to recommendation or conversation
        
        Args:
            user_message: User's message
            
        Returns:
            Bot response
        """
        logger.info(f"💬 User message: {user_message}")
        
        # Check if this is a recommendation request
        needs_recommendation = self._detect_recommendation_intent(user_message)
        
        if needs_recommendation:
            return self.recommend(user_message)
        else:
            return self._casual_chat(user_message)

    def _casual_chat(self, user_message: str) -> str:
        """
        Handle casual conversation (non-recommendation)
        
        Args:
            user_message: User's message
            
        Returns:
            Conversational response
        """
        conversation_context = self._build_conversation_context()
        
        prompt = f"""{self.conversation_prompt}

CONVERSATION HISTORY:
{conversation_context}

USER MESSAGE: {user_message}

Respond naturally and helpfully in 2-4 sentences."""
        
        try:
            response = get_completion(prompt, is_json=False)
            
            # Store conversation
            self.conversation.append(("User", user_message))
            self.conversation.append(("MIRA", response))
            
            if len(self.conversation) > 20:
                self.conversation = self.conversation[-20:]
                
            logger.info(f"✅ Casual response generated")
            return response
            
        except Exception as e:
            logger.error(f"❌ Chat error: {e}")
            return "I'm having trouble processing that. Could you rephrase?"

    def _build_conversation_context(self) -> str:
        """Build conversation history for context"""
        if not self.conversation:
            return "This is the start of our conversation."

        context_lines = []
        for role, message in self.conversation[-8:]:  # Last 4 exchanges
            # Truncate long messages
            truncated = message[:200] + "..." if len(message) > 200 else message
            context_lines.append(f"{role}: {truncated}")
        
        return "\n".join(context_lines)

    def reset(self):
        """Clear conversation history"""
        self.conversation = []
        logger.info("🔄 Conversation reset")

    def get_stats(self) -> str:
        """Get statistics about loaded tracks"""
        if not self.tracks_data:
            return "❌ No tracks loaded"

        total = len(self.tracks_data)
        with_vocals = sum(1 for track in self.tracks_data if track.get('hasVocals'))
        explicit = sum(1 for track in self.tracks_data if track.get('isExplicit'))
        
        # BPM distribution
        bpms = [t['bpm'] for t in self.tracks_data if t.get('bpm')]
        avg_bpm = sum(bpms) / len(bpms) if bpms else 0
        
        stats = f"""
📊 Hoopr Music Database Statistics
{'='*50}
Total Tracks:     {total:,}
With Vocals:      {with_vocals:,} ({with_vocals/total*100:.1f}%)
Instrumental:     {total-with_vocals:,} ({(total-with_vocals)/total*100:.1f}%)
Explicit:         {explicit:,} ({explicit/total*100:.1f}%)
Clean:            {total-explicit:,} ({(total-explicit)/total*100:.1f}%)
Average BPM:      {avg_bpm:.0f}
Database:         {self.db_path}
{'='*50}
"""
        return stats


# Example usage and API wrapper
if __name__ == "__main__":
    # Initialize bot
    bot = HooprMusicRecommender(db_path="audio_tagging.db")
    
    print(bot.get_stats())
    print("\n" + "="*50)
    print("MIRA - Hoopr Music Intelligence")
    print("Type 'quit' to exit, 'reset' to clear history, 'stats' for database info")
    print("="*50 + "\n")
    
    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except KeyboardInterrupt:
                print("\n👋 Thanks for using Hoopr Music Intelligence!")
                break
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("👋 Thanks for using Hoopr Music Intelligence!")
                break
            
            if user_input.lower() == 'reset':
                bot.reset()
                print("🔄 Conversation history cleared\n")
                continue
            
            if user_input.lower() == 'stats':
                print(bot.get_stats())
                continue
            
            # Get response
            response = bot.chat(user_input)
            print(f"\nMIRA: {response}\n")
    except KeyboardInterrupt:
        print("\n👋 Thanks for using Hoopr Music Intelligence!")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        print(f"\n❌ An error occurred: {e}")