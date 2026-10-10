from datetime import datetime, timedelta

from config import settings
from google.adk.sessions import InMemorySessionService
from loguru import logger


class SessionStore:
    def __init__(self):
        self.session_service = InMemorySessionService()
        self.user_sessions: dict[str, dict] = {}
        # Maps user_id -> {"session_id": str, "last_access": datetime}
        logger.info("SessionStore initialized")

    async def get_or_create_session(self, user_id: str, app_name: str = "agents") -> str:
        now = datetime.utcnow()

        if user_id in self.user_sessions:
            session_info = self.user_sessions[user_id]
            last_access = session_info["last_access"]

            if now - last_access < timedelta(seconds=settings.session_timeout_seconds):
                session_info["last_access"] = now
                logger.debug(f"Reusing existing session for user {user_id}")
                return session_info["session_id"]
            else:
                logger.info(f"Session expired for user {user_id}, creating new session")

        session_id = f"session-{user_id}-{int(now.timestamp())}"

        await self.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )

        self.user_sessions[user_id] = {
            "session_id": session_id,
            "last_access": now,
        }
        logger.info(f"Created new session {session_id} for user {user_id} with app_name={app_name}")
        return session_id

    def cleanup_expired_sessions(self):
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
        return len(self.user_sessions)
