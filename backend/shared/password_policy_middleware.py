import re
import string
from typing import Dict, Any, Set, List
from fastapi import HTTPException, status
import asyncio
from pathlib import Path
from .logger_middleware import get_logger
from .infrastructure_service import infra_service

logger = get_logger(__name__)


class PasswordPolicy:
    def __init__(self):
        self.common_passwords = self._load_common_passwords()
        self.sequential_pattern = re.compile(
            r"(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz|"
            r"123|234|345|456|567|678|789|890|987|876|765|654|543|432|321)",
            re.IGNORECASE
        )
        self.keyboard_pattern = re.compile(
            r"(qwe|wer|ert|rty|tyu|yui|uio|iop|asd|sdf|dfg|fgh|ghj|hjk|jkl|zxc|xcv|vbn|bnm|"
            r"1qaz|2wsx|3edc|4rfv|5tgb|6yhn|7ujm|8ik,|9ol.)",
            re.IGNORECASE
        )
        self.repeated_pattern = re.compile(r"(.)\1\1+")
        self.unicode_special_chars = re.compile(r"[^\w\s]", re.UNICODE)
        self.common_words = self._load_common_words()

    def _load_common_passwords(self) -> Set[str]:
        try:
            pass_file = Path("/etc/security/common_passwords.txt")
            if pass_file.exists():
                return set(pass_file.read_text().splitlines())
        except:
            pass

        return {
            "password", "123456", "123456789", "12345678", "12345", "1234567",
            "qwerty", "abc123", "password1", "admin", "welcome", "login",
            "111111", "123123", "letmein", "football", "iloveyou", "monkey",
            "jesus", "sunshine", "princess", "flower", "master", "hello",
            "freedom", "whatever", "qazwsx", "trustno1", "dragon", "baseball"
        }

    def _load_common_words(self) -> Set[str]:
        return {
            "password", "admin", "welcome", "qwerty", "dragon", "master",
            "sunshine", "princess", "football", "baseball", "monkey"
        }

    async def validate_password(self, password: str, tenant_id: int, user_context: Dict[str, Any] = None) -> Dict[
        str, Any]:
        if not password or len(password.strip()) == 0:
            return {"valid": False, "errors": ["Password cannot be empty"], "score": 0}

        if len(password) > 256:
            return {"valid": False, "errors": ["Password is too long"], "score": 0}

        try:
            async with infra_service.get_db_session() as session:
                result = await session.execute(
                    "SELECT * FROM login_settings WHERE tenant_id = :tid",
                    {"tid": tenant_id}
                )
                policy = result.fetchone()
                if not policy:
                    return self._validate_with_defaults(password, user_context)
                return self._validate_with_policy(password, policy, user_context)
        except Exception as e:
            logger.error(f"Password policy DB error for tenant {tenant_id}: {e}")
            return self._validate_with_defaults(password, user_context)

    def _validate_with_policy(self, password: str, policy: Any, user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        errors = []
        min_length = getattr(policy, "min_password_length", 8) or 8

        if len(password) < min_length:
            errors.append(f"Password must be at least {min_length} characters")

        if getattr(policy, "require_uppercase", True) and not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")

        if getattr(policy, "require_lowercase", True) and not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")

        if getattr(policy, "require_numbers", True) and not re.search(r"\d", password):
            errors.append("Password must contain at least one number")

        if getattr(policy, "require_special_chars", True):
            if not self.unicode_special_chars.search(password):
                errors.append("Password must contain at least one special character")

        lower_pass = password.lower()
        if lower_pass in self.common_passwords:
            errors.append("This password is too common and easily guessed")

        if any(word in lower_pass for word in self.common_words if len(word) > 4):
            errors.append("Password contains common dictionary words")

        if self.sequential_pattern.search(lower_pass):
            errors.append("Password contains sequential characters (e.g., abc, 123)")

        if self.keyboard_pattern.search(lower_pass):
            errors.append("Password contains keyboard patterns (e.g., qwerty, asdf)")

        if self.repeated_pattern.search(password):
            errors.append("Password contains repeated characters (e.g., aaa, 111)")

        if user_context:
            context_errors = self._check_context_violations(password, user_context)
            errors.extend(context_errors)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "score": self._calculate_password_strength(password),
            "strength": self._get_strength_label(password)
        }

    def _validate_with_defaults(self, password: str, user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        errors = []
        if len(password) < 8:
            errors.append("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")
        if not re.search(r"\d", password):
            errors.append("Password must contain at least one number")
        if password.lower() in self.common_passwords:
            errors.append("This password is too common")

        if user_context:
            context_errors = self._check_context_violations(password, user_context)
            errors.extend(context_errors)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "score": self._calculate_password_strength(password),
            "strength": self._get_strength_label(password)
        }

    def _check_context_violations(self, password: str, user_context: Dict[str, Any]) -> List[str]:
        errors = []
        lower_pass = password.lower()

        if user_context.get('email'):
            email_local = user_context['email'].split('@')[0].lower()
            if email_local in lower_pass and len(email_local) > 3:
                errors.append("Password should not contain your email address")

        if user_context.get('first_name'):
            first_name = user_context['first_name'].lower()
            if first_name in lower_pass and len(first_name) > 2:
                errors.append("Password should not contain your first name")

        if user_context.get('last_name'):
            last_name = user_context['last_name'].lower()
            if last_name in lower_pass and len(last_name) > 2:
                errors.append("Password should not contain your last name")

        return errors

    def _calculate_password_strength(self, password: str) -> int:
        score = 0
        length = len(password)
        unique_chars = len(set(password))

        score += min(length * 4, 40)
        score += 12 if re.search(r"[A-Z]", password) else 0
        score += 12 if re.search(r"[a-z]", password) else 0
        score += 15 if re.search(r"\d", password) else 0
        score += 20 if self.unicode_special_chars.search(password) else 0

        if unique_chars >= 12:
            score += 10
        if length >= 16:
            score += 15
        if length >= 20:
            score += 10

        lower_pass = password.lower()
        if lower_pass in self.common_passwords:
            score = 0
        elif self.sequential_pattern.search(lower_pass):
            score = max(0, score - 25)
        elif self.keyboard_pattern.search(lower_pass):
            score = max(0, score - 20)
        elif self.repeated_pattern.search(password):
            score = max(0, score - 20)
        elif any(word in lower_pass for word in self.common_words if len(word) > 4):
            score = max(0, score - 15)

        return max(0, min(100, score))

    def _get_strength_label(self, password: str) -> str:
        score = self._calculate_password_strength(password)
        if score >= 80:
            return "very_strong"
        elif score >= 60:
            return "strong"
        elif score >= 40:
            return "good"
        elif score >= 20:
            return "weak"
        else:
            return "very_weak"


password_policy = PasswordPolicy()