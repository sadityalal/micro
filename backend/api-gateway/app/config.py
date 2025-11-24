from typing import List
from shared.database.config_service import db_config_service
from shared.database.connection import initialize_databases
import os

class Settings:
    def __init__(self, tenant_id: int = 1):
        self.tenant_id = tenant_id
        initialize_databases()

    @property
    def API_GATEWAY_HOST(self) -> str:
        return "0.0.0.0"

    @property
    def API_GATEWAY_PORT(self) -> int:
        return 8080

    @property
    def AUTH_SERVICE_URL(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            return db_config_service.get_service_url(db_session, self.tenant_id, "auth_service")
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def USER_SERVICE_URL(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            return db_config_service.get_service_url(db_session, self.tenant_id, "user_service")
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def PRODUCT_SERVICE_URL(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            return db_config_service.get_service_url(db_session, self.tenant_id, "product_service")
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def ORDER_SERVICE_URL(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            return db_config_service.get_service_url(db_session, self.tenant_id, "order_service")
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def PAYMENT_SERVICE_URL(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            return db_config_service.get_service_url(db_session, self.tenant_id, "payment_service")
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def NOTIFICATION_SERVICE_URL(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            return db_config_service.get_service_url(db_session, self.tenant_id, "notification_service")
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def CORS_ORIGINS(self) -> List[str]:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["security"]["cors_origins"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def RATE_LIMIT_REQUESTS_PER_MINUTE(self) -> int:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["rate_limit"]["requests_per_minute"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

    @property
    def LOG_LEVEL(self) -> str:
        from shared.database.connection import get_db
        db_gen = get_db(self.tenant_id)
        db_session = next(db_gen)
        try:
            config = db_config_service.get_tenant_config(db_session, self.tenant_id)
            return config["logging"]["log_level"]
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass

settings = Settings()
