"""Session management for Agent API."""

import logging
from datetime import datetime, timedelta

from google.adk.sessions import InMemorySessionService

from agent_api.config import settings

logger = logging.getLogger(__name__)


class SessionStore:
    """Manages user sessions and conversation history."""

    def __init__(self):
        """Initialize the session store."""
        self.session_service = InMemorySessionService()
        self.user_sessions: dict[str, dict] = {}
        # Maps user_id -> {"session_id": str, "last_access": datetime}
        logger.info("SessionStore initialized")

    def get_or_create_session(self, user_id: str) -> str:
        """Get existing session or create new one for user.

        Args:
            user_id: User identifier

        Returns:
            Session ID for the user
        """
        now = datetime.utcnow()

        # Check if user has active session
        if user_id in self.user_sessions:
            session_info = self.user_sessions[user_id]
            last_access = session_info["last_access"]

            # Check if session is still valid
            if now - last_access < timedelta(seconds=settings.session_timeout_seconds):
                # Update last access time
                session_info["last_access"] = now
                logger.debug(f"Reusing existing session for user {user_id}")
                return session_info["session_id"]
            else:
                logger.info(f"Session expired for user {user_id}, creating new session")

        # Create new session
        session_id = f"session-{user_id}-{int(now.timestamp())}"
        self.user_sessions[user_id] = {
            "session_id": session_id,
            "last_access": now,
        }
        logger.info(f"Created new session {session_id} for user {user_id}")
        return session_id

    def cleanup_expired_sessions(self):
        """Remove sessions older than timeout.

        This should be called periodically as a background task.
        """
        now = datetime.utcnow()
        expired_users = []

        for user_id, session_info in self.user_sessions.items():
            last_access = session_info["last_access"]
            if now - last_access >= timedelta(seconds=settings.session_timeout_seconds):
                expired_users.append(user_id)

        for user_id in expired_users:
            session_id = self.user_sessions[user_id]["session_id"]
            del self.user_sessions[user_id]
            logger.info(f"Cleaned up expired session {session_id} for user {user_id}")

        if expired_users:
            logger.info(f"Cleaned up {len(expired_users)} expired sessions")

    def get_active_session_count(self) -> int:
        """Get count of active sessions.

        Returns:
            Number of active sessions
        """
        return len(self.user_sessions)
